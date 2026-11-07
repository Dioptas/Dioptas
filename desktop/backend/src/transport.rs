//! Bounded local stdio, compatible with the existing Tauri processor pipe.
//! A single worker owns all reader/engine objects. Progress bypasses that queue.
use crate::{
    Session,
    control::Control,
    protocol::{MAX_REQUEST_BYTES, Reply, Request},
};
use serde_json::json;
use std::{
    io::{BufRead, Read, Write},
    path::PathBuf,
    sync::{
        Arc, Mutex,
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
    let closing = AtomicBool::new(false);
    let active: Mutex<Option<Arc<Control>>> = Mutex::new(None);
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
        let (sender, receiver) = mpsc::sync_channel::<(Request, Arc<Control>)>(16);
        let (ready_sender, ready_receiver) = mpsc::sync_channel(1);
        let worker_write = &write;
        let worker_running = &running;
        let worker_active = &active;
        let worker_closing = &closing;
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
            for (request, control) in receiver {
                // Readout/state requests must not appear to restart a completed
                // calibration while the user moves the mouse over the result.
                worker_running.store(
                    matches!(
                        request.action.as_str(),
                        "calibrate"
                            | "integrate"
                            | "example"
                            | "open_image"
                            | "next_image"
                            | "open_calibration"
                            | "manual_geometry"
                            | "settings"
                            | "integration_settings"
                            | "mask_stroke"
                            | "clear_mask"
                            | "undo_mask"
                            | "redo_mask"
                            | "undo_calibration"
                            | "redo_calibration"
                    ),
                    Ordering::Release,
                );
                if request.action == "calibrate" {
                    *worker_active.lock().unwrap() = Some(control.clone());
                    if worker_closing.load(Ordering::Acquire) {
                        control.cancel();
                    }
                }
                let reply = session.invoke_controlled(&request, control.clone());
                control.finish();
                {
                    let mut active = worker_active.lock().unwrap();
                    if active.as_ref().is_some_and(|c| Arc::ptr_eq(c, &control)) {
                        *active = None;
                    }
                }
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
                    "progress" => {
                        let progress=active.lock().unwrap().as_ref().map(|c|c.progress()).unwrap_or_else(||json!({"running":running.load(Ordering::Acquire),"current":0,"total":1}));
                        write(
                            request.id,
                            Reply::metadata(json!({"ok":true,"progress":progress})),
                            &[],
                        )?;
                    }
                    "cancel_refinement" => {
                        let current = active.lock().unwrap().clone();
                        let reply = if let Some(control) = current {
                            control.cancel();
                            Reply::metadata(json!({"ok":true}))
                        } else if running.load(Ordering::Acquire) {
                            Reply::error(
                                "The current native integration call cannot be interrupted.",
                            )
                        } else {
                            Reply::metadata(json!({"ok":true}))
                        };
                        write(request.id, reply, &[])?;
                    }
                    _ => {
                        let control = Arc::new(Control::default());
                        if request.action == "calibrate" {
                            control.publish(json!({"running":true,"current":0,"total":1,"label":"Waiting for calibration"}));
                            let mut active = active.lock().unwrap();
                            if active.is_none() {
                                *active = Some(control.clone());
                            }
                        }
                        match sender.try_send((request, control)) {
                            Ok(()) => {}
                            Err(mpsc::TrySendError::Full((request, control))) => {
                                let mut active = active.lock().unwrap();
                                if active.as_ref().is_some_and(|c| Arc::ptr_eq(c, &control)) {
                                    *active = None;
                                }
                                drop(active);
                                write(
                                    request.id,
                                    Reply::error("Native processing queue is full."),
                                    &[],
                                )?;
                            }
                            Err(mpsc::TrySendError::Disconnected(_)) => {
                                return Err("Native processing worker disconnected.".into());
                            }
                        }
                    }
                }
            }
            Ok(())
        })();
        closing.store(true, Ordering::Release);
        if let Some(control) = active.lock().unwrap().as_ref() {
            control.cancel();
        }
        drop(sender);
        let finished = worker
            .join()
            .map_err(|_| "Native processing worker panicked.".to_string())?;
        result.and(finished)
    })
}
