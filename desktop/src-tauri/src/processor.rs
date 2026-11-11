use serde_json::{json, Value};
#[path = "../../command_contract.rs"]
pub mod command_contract;
use command_contract::{MAX_REQUEST_BYTES, REQUEST_SIZE_ERROR};
use std::{
    collections::HashMap,
    io::{BufReader, Read, Write},
    path::{Path, PathBuf},
    process::{Child, ChildStdin, Command, Stdio},
    sync::{
        atomic::{AtomicBool, AtomicU64, Ordering},
        mpsc, Arc, Mutex,
    },
    thread,
    time::Duration,
};

#[derive(Debug)]
pub struct Packet {
    #[cfg(test)]
    pub result: Value,
    pub bytes: Vec<u8>,
}

impl Packet {
    pub fn result_value(&self) -> Result<Value, String> {
        let length = u32::from_le_bytes(
            self.bytes
                .get(..4)
                .ok_or("Truncated processing header")?
                .try_into()
                .unwrap(),
        ) as usize;
        let header: Value = serde_json::from_slice(
            self.bytes
                .get(4..4 + length)
                .ok_or("Truncated processing header")?,
        )
        .map_err(|e| e.to_string())?;
        header
            .get("result")
            .cloned()
            .ok_or_else(|| "Missing processing result".into())
    }

    pub fn metadata(result: Value) -> Self {
        let header = json!({"result": result, "buffers": []})
            .to_string()
            .into_bytes();
        let mut bytes = (header.len() as u32).to_le_bytes().to_vec();
        bytes.extend_from_slice(&header);
        Self {
            #[cfg(test)]
            result,
            bytes,
        }
    }
}

type Reply = Result<Packet, String>;

fn write_navigation_trace(value: Value) {
    // Host and worker share the stderr pipe. Write each preformatted line in
    // one operation so their optional timing records cannot interleave.
    let line = format!("DIOPTAS_NATIVE_TRACE {value}\n");
    let _ = std::io::stderr().lock().write_all(line.as_bytes());
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Backend {
    Python,
    Rust,
}

impl Backend {
    pub fn requested(args: &[String], environment: Option<&str>) -> Result<Self, String> {
        let choices: Vec<_> = args
            .iter()
            .filter_map(|arg| arg.strip_prefix("--backend="))
            .collect();
        if choices.len() > 1 || args.iter().any(|arg| arg == "--backend") {
            return Err("Specify the processor once as --backend=rust or --backend=python.".into());
        }
        match choices.first().copied().or(environment).unwrap_or("rust") {
            "python" => Ok(Self::Python),
            "rust" => Ok(Self::Rust),
            _ => Err(
                "Choose --backend=rust or --backend=python. No fallback processor was started."
                    .into(),
            ),
        }
    }
}

// The child is local and trusted, but reject broken framing before allocating.
// Map retains the established numeric indices/values contract for up to four
// million cells. Detector and series rasters remain separate binary buffers.
const MAX_HEADER: usize = 256 * 1024 * 1024;
const MAX_BUFFERS: usize = 1024 * 1024 * 1024;
#[derive(serde::Deserialize)]
struct WireBuffer {
    length: u64,
}
#[derive(serde::Deserialize)]
struct WireHeader {
    id: u64,
    buffers: Vec<WireBuffer>,
    #[serde(rename = "result")]
    _result: serde::de::IgnoredAny,
}
fn read_packet(reader: &mut impl Read) -> Result<(u64, Packet), String> {
    let mut prefix = [0u8; 4];
    reader.read_exact(&mut prefix).map_err(|e| e.to_string())?;
    let length = u32::from_le_bytes(prefix) as usize;
    if length > MAX_HEADER {
        return Err("Oversized processing header".into());
    }
    let mut header = vec![0; length];
    reader.read_exact(&mut header).map_err(|e| e.to_string())?;
    let trace = std::env::var_os("DIOPTAS_TRACE_NATIVE_NAV").is_some();
    let parse_started = std::time::Instant::now();
    // The host routes and bounds the packet; JavaScript consumes its metadata.
    // Validate the complete JSON without allocating a second scientific tree.
    let value: WireHeader = serde_json::from_slice(&header).map_err(|e| e.to_string())?;
    let parsed = std::time::Instant::now();
    let id = value.id;
    let total = value.buffers.iter().try_fold(0usize, |size, buffer| {
        let n = usize::try_from(buffer.length).map_err(|_| "Invalid binary buffer length")?;
        size.checked_add(n)
            .filter(|v| *v <= MAX_BUFFERS)
            .ok_or("Oversized processing buffers")
    })?;
    // Allocate initialized bytes directly. Growing a nonempty Vec with resize
    // uses an element-by-element fill in unoptimized host builds (tens of ms
    // per detector). Zeroed allocation keeps this safe read target inexpensive.
    let mut bytes = vec![0; 4 + length + total];
    bytes[..4].copy_from_slice(&prefix);
    bytes[4..4 + length].copy_from_slice(&header);
    let allocated = std::time::Instant::now();
    reader
        .read_exact(&mut bytes[4 + length..])
        .map_err(|e| e.to_string())?;
    if trace {
        write_navigation_trace(
            json!({"stage":"read-packet","id":id,"headerBytes":length,"pixelBytes":total,"headerDecodeMs":parsed.duration_since(parse_started).as_secs_f64()*1000.,"allocationMs":allocated.duration_since(parsed).as_secs_f64()*1000.,"payloadReadMs":allocated.elapsed().as_secs_f64()*1000.,"assemblyAndReadMs":parsed.elapsed().as_secs_f64()*1000.}),
        );
    }
    #[cfg(test)]
    let result = serde_json::from_slice::<Value>(&header)
        .map_err(|e| e.to_string())?
        .get("result")
        .ok_or("Missing processing result")?
        .clone();
    Ok((
        id,
        Packet {
            #[cfg(test)]
            result,
            bytes,
        },
    ))
}

#[derive(Default)]
struct Replies {
    failed: Option<String>,
    waiting: HashMap<u64, mpsc::Sender<Reply>>,
}

/// A local, multiplexed pipe. Never hold the writer lock while awaiting a fit:
/// the progress and cancellation requests must be able to pass it.
pub struct Processor {
    child: Mutex<Child>,
    input: Mutex<Option<ChildStdin>>,
    replies: Arc<Mutex<Replies>>,
    next_id: AtomicU64,
    closed: AtomicBool,
}

impl Processor {
    pub fn source_root() -> PathBuf {
        std::env::var_os("DIOPTAS_SOURCE_ROOT")
            .map(PathBuf::from)
            .unwrap_or_else(|| {
                Path::new(env!("CARGO_MANIFEST_DIR"))
                    .parent()
                    .unwrap()
                    .parent()
                    .unwrap()
                    .into()
            })
    }

    #[cfg(test)]
    pub fn start(example: bool) -> Result<Self, String> {
        Self::start_backend(
            example,
            Backend::requested(&[], std::env::var("DIOPTAS_BACKEND").ok().as_deref())?,
        )
    }

    #[cfg(test)]
    pub fn start_backend(example: bool, backend: Backend) -> Result<Self, String> {
        Self::start_backend_at(example, backend, None)
    }

    pub fn start_backend_at(
        example: bool,
        backend: Backend,
        resources: Option<&Path>,
    ) -> Result<Self, String> {
        Self::start_backend_binary(example, backend, resources, None)
    }

    pub(super) fn start_backend_binary(
        example: bool,
        backend: Backend,
        resources: Option<&Path>,
        binary: Option<&Path>,
    ) -> Result<Self, String> {
        let mut command = match backend {
            Backend::Python => {
                let root = Self::source_root();
                let python = std::env::var_os("DIOPTAS_PYTHON")
                    .map(PathBuf::from)
                    .unwrap_or_else(|| {
                        root.join(if cfg!(windows) {
                            ".venv/Scripts/python.exe"
                        } else {
                            ".venv/bin/python"
                        })
                    });
                if !python.is_file() {
                    return Err(format!("The local Python environment is missing at {}. Run uv sync --python 3.13 in the Dioptas checkout, then restart.", python.display()));
                }
                let mut command = Command::new(python);
                command
                    .args(["-u", "-m", "dioptas.desktop.stdio"])
                    .current_dir(root)
                    .env("PYTHONUNBUFFERED", "1");
                command
            }
            Backend::Rust => {
                let filename = if cfg!(windows) {
                    "dioptas-processor.exe"
                } else {
                    "dioptas-processor"
                };
                let native = binary
                    .map(Path::to_path_buf)
                    .or_else(|| std::env::var_os("DIOPTAS_NATIVE_PROCESSOR").map(PathBuf::from))
                    .unwrap_or_else(|| {
                        let sibling = std::env::current_exe()
                            .ok()
                            .and_then(|p| p.parent().map(|p| p.join(filename)));
                        sibling.filter(|p| p.is_file()).unwrap_or_else(|| {
                            #[cfg(debug_assertions)]
                            let root = Self::source_root().join("desktop/backend/target");
                            #[cfg(not(debug_assertions))]
                            let root = std::env::current_exe()
                                .unwrap_or_default()
                                .parent()
                                .unwrap_or(Path::new("."))
                                .to_path_buf();
                            root
                                // Development keeps the source-build fallback. Packaged release
                                // hosts never search a build machine's checkout.
                                .join(if cfg!(debug_assertions) { "debug" } else { "" })
                                .join(filename)
                        })
                    });
                if !native.is_file() {
                    return Err(format!("The native processor is missing at {}. Run npm run backend:prepare in desktop (add -- --release for a release host), then restart. Python was not started.", native.display()));
                }
                let mut command = Command::new(native);
                if let Some(resources) = resources {
                    if !resources.join("RESOURCE_MANIFEST.json").is_file() {
                        return Err(format!("Application resources are missing at {}. Rebuild or reinstall the complete application.", resources.display()));
                    }
                    command.arg("--resource-dir").arg(resources);
                } else {
                    #[cfg(debug_assertions)]
                    command.arg("--source-root").arg(Self::source_root());
                }
                command
            }
        };
        command
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit());
        if example {
            command.arg("--example");
        }
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000); // CREATE_NO_WINDOW
        }
        let mut child = command
            .spawn()
            .map_err(|e| format!("Cannot start local processing: {e}"))?;
        let input = child.stdin.take().expect("piped stdin");
        let output = child.stdout.take().expect("piped stdout");
        let replies = Arc::new(Mutex::new(Replies::default()));
        let reader_replies = replies.clone();
        thread::spawn(move || {
            let failure;
            let mut reader = BufReader::new(output);
            loop {
                match read_packet(&mut reader) {
                    Ok((id, packet)) => {
                        if let Some(waiter) = reader_replies.lock().unwrap().waiting.remove(&id) {
                            let _ = waiter.send(Ok(packet));
                        }
                    }
                    Err(error) => {
                        failure = format!("Cannot read local processing: {error}");
                        break;
                    }
                }
            }
            let mut replies = reader_replies.lock().unwrap();
            replies.failed = Some(failure.clone());
            for (_, waiter) in replies.waiting.drain() {
                let _ = waiter.send(Err(failure.clone()));
            }
        });
        Ok(Self {
            child: Mutex::new(child),
            input: Mutex::new(Some(input)),
            replies,
            next_id: AtomicU64::new(1),
            closed: AtomicBool::new(false),
        })
    }

    #[cfg(test)]
    pub fn request(&self, action: &str, payload: Value) -> Result<Value, String> {
        self.request_packet(action, payload, vec![])
            .map(|p| p.result)
    }

    pub fn request_packet(&self, action: &str, payload: Value, cached: Vec<String>) -> Reply {
        if self.closed.load(Ordering::SeqCst) {
            return Err("The desktop session is closed.".into());
        }
        let id = self.next_id.fetch_add(1, Ordering::Relaxed);
        let started = std::time::Instant::now();
        let encoded =
            json!({"id": id, "action": action, "payload": payload, "cachedBuffers": cached})
                .to_string()
                + "\n";
        // Reject before registering a reply or sending any bytes. The scientific
        // child and unsaved session remain usable after a large export fails.
        if encoded.len() > MAX_REQUEST_BYTES {
            return Err(REQUEST_SIZE_ERROR.into());
        }
        let (sender, receiver) = mpsc::channel();
        {
            let mut replies = self.replies.lock().unwrap();
            if let Some(error) = &replies.failed {
                return Err(error.clone());
            }
            replies.waiting.insert(id, sender);
        }
        let sent = {
            let mut input = self.input.lock().unwrap();
            match input.as_mut() {
                Some(pipe) => pipe
                    .write_all(encoded.as_bytes())
                    .and_then(|_| pipe.flush())
                    .map_err(|e| e.to_string()),
                None => Err("The desktop session is closed.".into()),
            }
        };
        if let Err(error) = sent {
            self.replies.lock().unwrap().waiting.remove(&id);
            return Err(format!("Cannot send local processing command: {error}"));
        }
        let reply = receiver
            .recv()
            .map_err(|_| "Local processing disconnected.".to_string())?;
        if std::env::var_os("DIOPTAS_TRACE_NATIVE_NAV").is_some() {
            write_navigation_trace(
                json!({"stage":"request","id":id,"action":action,"elapsedMs":started.elapsed().as_secs_f64()*1000.}),
            );
        }
        reply
    }

    pub fn shutdown(&self) {
        if self.closed.swap(true, Ordering::SeqCst) {
            return;
        }
        // EOF asks the processor to drain commands and release thread-affine
        // models. Bound shutdown if a native library cannot respond to cancel.
        self.input.lock().unwrap().take();
        let mut child = self.child.lock().unwrap();
        for _ in 0..100 {
            if matches!(child.try_wait(), Ok(Some(_))) {
                return;
            }
            thread::sleep(Duration::from_millis(20));
        }
        let _ = child.kill();
        let _ = child.wait();
    }
}

impl Drop for Processor {
    fn drop(&mut self) {
        self.shutdown();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn backend_selection_is_explicit_and_never_silently_falls_back() {
        assert_eq!(Backend::requested(&[], None).unwrap(), Backend::Rust);
        assert_eq!(
            Backend::requested(&[], Some("rust")).unwrap(),
            Backend::Rust
        );
        assert_eq!(
            Backend::requested(&["--backend=rust".into()], Some("python")).unwrap(),
            Backend::Rust
        );
        assert_eq!(
            Backend::requested(&[], Some("python")).unwrap(),
            Backend::Python
        );
        assert_eq!(
            Backend::requested(&["--backend=python".into()], Some("rust")).unwrap(),
            Backend::Python
        );
        assert!(Backend::requested(&[], Some("unknown")).is_err());
        assert!(Backend::requested(&["--backend=unknown".into()], None).is_err());
        assert!(Backend::requested(&["--backend".into(), "rust".into()], None).is_err());
        assert!(
            Backend::requested(&["--backend=rust".into(), "--backend=python".into()], None)
                .is_err()
        );
    }

    #[test]
    fn default_processor_uses_rust_and_releases_its_child() {
        let processor = Processor::start(false).unwrap();
        let host = processor.request("__host__", json!({})).unwrap();
        assert_eq!(host["runtime"], "rust");
        assert_eq!(host["protocol"], 2);
        let image = processor.request("example", json!({})).unwrap();
        assert_eq!(image["ok"], true);
        assert_eq!(image["image"]["width"], 981);
        assert_eq!(image["image"]["height"], 1043);
        assert_eq!(
            processor
                .request("open_project", json!({"path":"not-migrated.dio"}))
                .unwrap()["ok"],
            false
        );
        processor.shutdown();
        assert!(processor
            .child
            .lock()
            .unwrap()
            .try_wait()
            .unwrap()
            .is_some());
        assert!(processor.request("state", json!({})).is_err());
    }

    #[test]
    fn incomplete_packaged_resources_fail_before_starting_a_processor() {
        let error = Processor::start_backend_at(
            false,
            Backend::Rust,
            Some(Path::new("/nonexistent/dioptas-resources")),
        )
        .err()
        .expect("Incomplete resources must fail");
        assert!(error.contains("Application resources are missing"));
    }

    #[test]
    fn real_session_multiplexes_responses_and_closes_its_child() {
        let processor = Arc::new(Processor::start(false).unwrap());
        let pid = processor.request("__host__", json!({})).unwrap();
        assert_eq!(pid["transport"], "stdio");
        assert_eq!(pid["qtApplication"], false);
        let image_job = {
            let p = processor.clone();
            thread::spawn(move || p.request("example", json!({})))
        };
        let progress_job = {
            let p = processor.clone();
            thread::spawn(move || p.request("progress", json!({})))
        };
        assert_eq!(progress_job.join().unwrap().unwrap()["ok"], true);
        let image = image_job.join().unwrap().unwrap();
        assert_eq!(image["ok"], true);
        assert_eq!(image["image"]["step"], 1);
        assert_eq!(image["image"]["width"], image["image"]["fullWidth"]);
        assert_eq!(image["state"]["calibrated"], false);
        assert_eq!(
            processor.request("not_a_command", json!({})).unwrap()["ok"],
            false
        );
        assert_eq!(processor.request("state", json!({})).unwrap()["ok"], true);
        processor.shutdown();
        assert!(processor
            .child
            .lock()
            .unwrap()
            .try_wait()
            .unwrap()
            .is_some());
        assert!(processor.request("state", json!({})).is_err());
    }

    #[test]
    fn raw_buffers_roundtrip_and_cached_images_are_not_resent() {
        let processor = Processor::start(false).unwrap();
        let path = Processor::source_root().join("dioptas/tests/data/image_001.tif");
        let first = processor
            .request_packet("open_image", json!({"path": path}), vec![])
            .unwrap();
        let table = |p: &Packet| -> Value {
            let n = u32::from_le_bytes(p.bytes[..4].try_into().unwrap()) as usize;
            serde_json::from_slice::<Value>(&p.bytes[4..4 + n]).unwrap()["buffers"].clone()
        };
        let known = |p: &Packet| -> Vec<String> {
            ["image", "mask"]
                .iter()
                .map(|key| p.result[key]["bufferId"].as_str().unwrap().to_string())
                .collect()
        };
        assert_eq!(first.result["image"]["step"], 1);
        assert!(first.result["image"].get("data").is_none());
        assert_eq!(table(&first).as_array().unwrap().len(), 2);
        let mut cached = known(&first);
        let second = processor
            .request_packet("next_image", json!({"direction":1}), cached.clone())
            .unwrap();
        assert_eq!(table(&second).as_array().unwrap().len(), 1); // unchanged mask omitted
        cached.extend(known(&second));
        cached.sort();
        cached.dedup();
        let warm = processor
            .request_packet("next_image", json!({"direction":-1}), cached)
            .unwrap();
        assert_eq!(
            warm.result["image"]["bufferId"],
            first.result["image"]["bufferId"]
        );
        assert_eq!(table(&warm), json!([]));
        assert!(warm.bytes.len() < 100_000);
        assert!(first.bytes.len() > 20_000_000);
        processor.shutdown();
    }

    #[test]
    fn frames_preserve_arbitrary_binary_bytes_and_reject_truncation() {
        let header =
            json!({"id":9,"result":{"ok":true},"buffers":[{"id":"pixels","length":5}]}).to_string();
        let mut bytes = (header.len() as u32).to_le_bytes().to_vec();
        bytes.extend_from_slice(header.as_bytes());
        bytes.extend_from_slice(&[0, 255, 10, 13, 42]);
        let (id, p) = read_packet(&mut bytes.as_slice()).unwrap();
        assert_eq!(id, 9);
        assert_eq!(&p.bytes[p.bytes.len() - 5..], &[0, 255, 10, 13, 42]);
        assert!(read_packet(&mut &bytes[..bytes.len() - 1]).is_err());
        assert!(read_packet(&mut &(MAX_HEADER as u32 + 1).to_le_bytes()[..]).is_err());
    }

    #[test]
    fn routing_header_requires_valid_fields_and_forwards_metadata_bytes_unchanged() {
        let packet = |header: &[u8]| {
            let mut bytes = (header.len() as u32).to_le_bytes().to_vec();
            bytes.extend_from_slice(header);
            bytes
        };
        let raw = br#"{ "result": {"nested":[1.2345678901234567,1e-200,{"text":"escaped\\text"}]}, "buffers": [], "id": 17 }"#;
        let bytes = packet(raw);
        let (id, parsed) = read_packet(&mut bytes.as_slice()).unwrap();
        assert_eq!(id, 17);
        assert_eq!(parsed.bytes, bytes);
        for raw in [
            r#"{"result":{},"buffers":[]}"#,
            r#"{"id":1,"buffers":[]}"#,
            r#"{"id":1,"result":{}}"#,
            r#"{"id":-1,"result":{},"buffers":[]}"#,
            r#"{"id":1,"result":{},"buffers":[{"length":-1}]}"#,
            r#"{"id":1,"result":{},"buffers":[{"length":1.5}]}"#,
            r#"{"id":1,"result":{},"buffers":[{"length":1073741825}]}"#,
            r#"{"id":1,"result":{"bad":[1,]},"buffers":[]}"#,
        ] {
            assert!(
                read_packet(&mut packet(raw.as_bytes()).as_slice()).is_err(),
                "{raw}"
            );
        }
    }

    #[test]
    fn child_exit_rejects_pending_and_future_commands() {
        let processor = Processor::start(false).unwrap();
        processor.child.lock().unwrap().kill().unwrap();
        assert!(processor.request("state", json!({})).is_err());
        assert!(processor.request("state", json!({})).is_err());
        processor.shutdown();
    }

    #[test]
    fn oversized_commands_preserve_the_child_and_unsaved_configuration() {
        let processor = Processor::start(false).unwrap();
        let identity = processor.request("__host__", json!({})).unwrap();
        let renamed = processor
            .request(
                "configuration",
                json!({"operation":"rename","name":"Unsaved session"}),
            )
            .unwrap();
        assert_eq!(renamed["ok"], true);
        let before = processor.request("state", json!({})).unwrap();
        let error = processor
            .request_packet(
                "integration_save_pattern",
                json!({"format":"svg","svg_data":"x".repeat(MAX_REQUEST_BYTES)}),
                vec![],
            )
            .unwrap_err();
        assert_eq!(error, REQUEST_SIZE_ERROR);
        assert!(processor.replies.lock().unwrap().waiting.is_empty());
        assert_eq!(processor.request("state", json!({})).unwrap(), before);
        assert_eq!(
            processor.request("__host__", json!({})).unwrap()["pid"],
            identity["pid"]
        );
        processor.shutdown();
    }

    #[test]
    fn transfer_processing_exposes_progress_and_cancel_restores_its_session() {
        let processor = Arc::new(Processor::start(false).unwrap());
        let requested = json!({"cake":false,"rings":false});
        for (action, payload) in [
            (
                "open_image",
                json!({"path":Processor::source_root().join("dioptas/tests/data/image_001.tif"),"requested_products":requested}),
            ),
            (
                "manual_geometry",
                json!({"convention":"pyfai","values":{"dist":0.13,"poni1":0.1,"poni2":0.1,"rot1":0.,"rot2":0.,"rot3":0.,"pixel1":0.0001,"pixel2":0.0001,"wavelength":5e-11,"polarization_factor":0.965},"requested_products":requested}),
            ),
        ] {
            let result = processor.request(action, payload).unwrap();
            assert_eq!(result["ok"], true, "{action}: {result}");
        }
        let before = processor.request("state", json!({})).unwrap();
        let other = processor.clone();
        // A cold cake makes this a real scientific calculation rather than a
        // metadata-only toggle, reproducing the omitted transfer policy.
        let job = thread::spawn(move || {
            other.request(
                "integration_transfer",
                json!({
                    "enabled":false,"requested_products":{"cake":true,"rings":false}
                }),
            )
        });
        let started = std::time::Instant::now();
        loop {
            let progress = processor.request("progress", json!({})).unwrap();
            if progress["progress"]["running"] == true {
                break;
            }
            assert!(
                !job.is_finished(),
                "Transfer completed without publishing running progress"
            );
            assert!(started.elapsed() < Duration::from_secs(5));
            thread::sleep(Duration::from_millis(1));
        }
        assert_eq!(
            processor.request("cancel_refinement", json!({})).unwrap()["ok"],
            true
        );
        let result = job.join().unwrap().unwrap();
        assert!(
            result["cancelled"] == true
                || result["error"]
                    .as_str()
                    .is_some_and(|error| error.to_lowercase().contains("cancelled")),
            "{result}"
        );
        assert_eq!(processor.request("state", json!({})).unwrap(), before);
        processor.shutdown();
    }
}
