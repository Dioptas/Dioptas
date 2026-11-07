//! Bounded local stdio, compatible with the existing Tauri processor pipe.
//! A single worker owns all reader/engine objects. Progress bypasses that queue.
use crate::{
    Session,
    protocol::{MAX_REQUEST_BYTES, Reply, Request},
};
use serde_json::json;
use std::{
    io::{BufRead, Read, Write},
    path::PathBuf,
    sync::{
        Mutex,
        atomic::{AtomicBool, Ordering},
        mpsc,
    },
    thread,
};

pub fn serve(
    input: &mut impl BufRead,
    output: &mut (impl Write + Send),
    root: PathBuf,
    example: bool,
) -> Result<(), String> {
    let output = Mutex::new(output);
    let running = AtomicBool::new(false);
    let write = |id, reply: Reply, known: &[String]| -> Result<(), String> {
        let packet = reply.encode(id, known)?;
        let mut stream = output
            .lock()
            .map_err(|_| "Processing output lock failed.")?;
        stream
            .write_all(&packet)
            .and_then(|_| stream.flush())
            .map_err(|e| e.to_string())
    };
    thread::scope(|scope| {
        let (sender, receiver) = mpsc::sync_channel::<Request>(16);
        let (ready_sender, ready_receiver) = mpsc::sync_channel(1);
        let worker_write = &write;
        let worker_running = &running;
        let worker = scope.spawn(move || -> Result<(), String> {
            let mut session = Session::new(root);
            if example {
                let request = Request {
                    id: 0,
                    action: "example".into(),
                    payload: json!({}),
                    cached_buffers: vec![],
                };
                let result = session.invoke(&request);
                if result.result["ok"] != true {
                    let error = result.result["error"]
                        .as_str()
                        .unwrap_or("Cannot load example")
                        .to_string();
                    let _ = ready_sender.send(Err(error.clone()));
                    return Err(error);
                }
            }
            let _ = ready_sender.send(Ok(()));
            for request in receiver {
                worker_running.store(true, Ordering::Release);
                let reply = session.invoke(&request);
                worker_running.store(false, Ordering::Release);
                worker_write(request.id, reply, &request.cached_buffers)?;
            }
            Ok(())
        });
        let result = (|| {
            ready_receiver.recv().map_err(|e| e.to_string())??;
            loop {
                let mut line = Vec::new();
                let n = input
                    .take((MAX_REQUEST_BYTES + 1) as u64)
                    .read_until(b'\n', &mut line)
                    .map_err(|e| e.to_string())?;
                if n == 0 {
                    break;
                }
                if n > MAX_REQUEST_BYTES {
                    return Err("Processing request exceeds 16 MiB.".into());
                }
                let request: Request = match serde_json::from_slice(&line) {
                    Ok(request) => request,
                    Err(error) => {
                        let id = serde_json::from_slice::<serde_json::Value>(&line)
                            .ok()
                            .and_then(|v| v["id"].as_u64())
                            .unwrap_or(0);
                        write(id, Reply::error(error), &[])?;
                        continue;
                    }
                };
                if let Err(error) = request.validate() {
                    write(request.id, Reply::error(error), &[])?;
                    continue;
                }
                match request.action.as_str() {
                    "progress" => write(
                        request.id,
                        Reply::metadata(
                            json!({"ok":true,"progress":{"running":running.load(Ordering::Acquire),"current":0,"total":1}}),
                        ),
                        &[],
                    )?,
                    "cancel_refinement" => {
                        let reply = if running.load(Ordering::Acquire) {
                            Reply::error(
                                "The current native integration call cannot be interrupted; calibration refinement has not been migrated yet.",
                            )
                        } else {
                            Reply::metadata(json!({"ok":true}))
                        };
                        write(request.id, reply, &[])?;
                    }
                    _ => match sender.try_send(request) {
                        Ok(()) => {}
                        Err(mpsc::TrySendError::Full(request)) => write(
                            request.id,
                            Reply::error("Native processing queue is full."),
                            &[],
                        )?,
                        Err(mpsc::TrySendError::Disconnected(_)) => {
                            return Err("Native processing worker disconnected.".into());
                        }
                    },
                }
            }
            Ok(())
        })();
        drop(sender);
        let finished = worker
            .join()
            .map_err(|_| "Native processing worker panicked.".to_string())?;
        result.and(finished)
    })
}
