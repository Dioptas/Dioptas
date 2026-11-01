use serde_json::{json, Value};
use std::{
    collections::HashMap,
    io::{BufRead, BufReader, Write},
    path::{Path, PathBuf},
    process::{Child, ChildStdin, Command, Stdio},
    sync::{
        atomic::{AtomicBool, AtomicU64, Ordering},
        mpsc, Arc, Mutex,
    },
    thread,
    time::Duration,
};

type Reply = Result<Value, String>;

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

    pub fn start(example: bool) -> Result<Self, String> {
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
            .env("PYTHONUNBUFFERED", "1")
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
            let mut failure =
                "Local processing stopped. Restart this preview to open a new session.".to_string();
            for line in BufReader::new(output).lines() {
                let response = match line {
                    Ok(line) => serde_json::from_str::<Value>(&line).map_err(|e| e.to_string()),
                    Err(e) => Err(e.to_string()),
                };
                match response {
                    Ok(value) => {
                        if let (Some(id), Some(result)) =
                            (value["id"].as_u64(), value.get("result"))
                        {
                            if let Some(waiter) = reader_replies.lock().unwrap().waiting.remove(&id)
                            {
                                let _ = waiter.send(Ok(result.clone()));
                            }
                        } else {
                            failure = "Local processing returned an invalid response.".into();
                            break;
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

    pub fn request(&self, action: &str, payload: Value) -> Reply {
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
        let encoded = json!({"id": id, "action": action, "payload": payload}).to_string() + "\n";
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
        // EOF asks Python to cancel, drain commands, and release thread-affine
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
    fn child_exit_rejects_pending_and_future_commands() {
        let processor = Processor::start(false).unwrap();
        processor.child.lock().unwrap().kill().unwrap();
        assert!(processor.request("state", json!({})).is_err());
        assert!(processor.request("state", json!({})).is_err());
        processor.shutdown();
    }
}
