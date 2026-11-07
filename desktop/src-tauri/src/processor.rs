use serde_json::{json, Value};
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
fn read_packet(reader: &mut impl Read) -> Result<(u64, Packet), String> {
    let mut prefix = [0u8; 4];
    reader.read_exact(&mut prefix).map_err(|e| e.to_string())?;
    let length = u32::from_le_bytes(prefix) as usize;
    if length > MAX_HEADER {
        return Err("Oversized processing header".into());
    }
    let mut header = vec![0; length];
    reader.read_exact(&mut header).map_err(|e| e.to_string())?;
    let value: Value = serde_json::from_slice(&header).map_err(|e| e.to_string())?;
    let id = value["id"]
        .as_u64()
        .ok_or("Missing processing request id")?;
    let buffers = value["buffers"]
        .as_array()
        .ok_or("Missing binary buffer table")?;
    let total = buffers.iter().try_fold(0usize, |size, buffer| {
        let n = buffer["length"]
            .as_u64()
            .and_then(|v| usize::try_from(v).ok())
            .ok_or("Invalid binary buffer length")?;
        size.checked_add(n)
            .filter(|v| *v <= MAX_BUFFERS)
            .ok_or("Oversized processing buffers")
    })?;
    let mut bytes = Vec::with_capacity(4 + length + total);
    bytes.extend_from_slice(&prefix);
    bytes.extend_from_slice(&header);
    bytes.resize(4 + length + total, 0);
    reader
        .read_exact(&mut bytes[4 + length..])
        .map_err(|e| e.to_string())?;
    #[cfg(test)]
    let result = value
        .get("result")
        .ok_or("Missing processing result")?
        .clone();
    if value.get("result").is_none() {
        return Err("Missing processing result".into());
    }
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

    pub fn start_backend(example: bool, backend: Backend) -> Result<Self, String> {
        let root = Self::source_root();
        let mut command = match backend {
            Backend::Python => {
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
                    .env("PYTHONUNBUFFERED", "1");
                command
            }
            Backend::Rust => {
                let filename = if cfg!(windows) {
                    "dioptas-processor.exe"
                } else {
                    "dioptas-processor"
                };
                let native = std::env::var_os("DIOPTAS_NATIVE_PROCESSOR")
                    .map(PathBuf::from)
                    .unwrap_or_else(|| {
                        let sibling = std::env::current_exe()
                            .ok()
                            .and_then(|p| p.parent().map(|p| p.join(filename)));
                        sibling.filter(|p| p.is_file()).unwrap_or_else(|| {
                            root.join("desktop/backend/target")
                                .join(if cfg!(debug_assertions) {
                                    "debug"
                                } else {
                                    "release"
                                })
                                .join(filename)
                        })
                    });
                if !native.is_file() {
                    return Err(format!("The native processor is missing at {}. Run npm run backend:prepare in desktop (add -- --release for a release host), then restart. Python was not started.", native.display()));
                }
                let mut command = Command::new(native);
                command.arg("--source-root").arg(&root);
                command
            }
        };
        command
            .current_dir(root)
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
        let (sender, receiver) = mpsc::channel();
        {
            let mut replies = self.replies.lock().unwrap();
            if let Some(error) = &replies.failed {
                return Err(error.clone());
            }
            replies.waiting.insert(id, sender);
        }
        let encoded =
            json!({"id": id, "action": action, "payload": payload, "cachedBuffers": cached})
                .to_string()
                + "\n";
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
        receiver
            .recv()
            .map_err(|_| "Local processing disconnected.".to_string())?
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
    fn child_exit_rejects_pending_and_future_commands() {
        let processor = Processor::start(false).unwrap();
        processor.child.lock().unwrap().kill().unwrap();
        assert!(processor.request("state", json!({})).is_err());
        assert!(processor.request("state", json!({})).is_err());
        processor.shutdown();
    }
}
