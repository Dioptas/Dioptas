//! Bounded local stdio, compatible with the existing Tauri processor pipe.
//! A single worker owns all reader/engine objects. Progress bypasses that queue.
use crate::{
    Session,
    control::Control,
    protocol::{MAX_REQUEST_BYTES, Reply, Request},
};
use serde_json::json;
use std::{
    backtrace::Backtrace,
    cell::RefCell,
    io::{BufRead, Read, Write},
    path::PathBuf,
    sync::{
        Arc, Mutex, Once,
        atomic::{AtomicBool, Ordering},
        mpsc,
    },
    thread,
};

thread_local! {
    static PANIC_DETAILS: RefCell<Option<String>> = const { RefCell::new(None) };
}
fn install_panic_report() {
    static INSTALL: Once = Once::new();
    INSTALL.call_once(|| {
        let previous = std::panic::take_hook();
        std::panic::set_hook(Box::new(move |info| {
            let _ = PANIC_DETAILS.try_with(|details| {
                *details.borrow_mut() = Some(format!("{info}\n{}", Backtrace::force_capture()));
            });
            previous(info);
        }));
    });
}
// An internal panic is reported, but the possibly inconsistent session is
// never reused. Ordinary Result errors retain the session's existing rollback.
fn guarded(invoke: impl FnOnce() -> Reply) -> Result<Reply, Reply> {
    PANIC_DETAILS.with(|details| details.borrow_mut().take());
    std::panic::catch_unwind(std::panic::AssertUnwindSafe(invoke)).map_err(|panic| {
        let message = panic.downcast_ref::<String>().cloned()
            .or_else(|| panic.downcast_ref::<&str>().map(|s| s.to_string()))
            .unwrap_or_else(|| "Unknown native panic".into());
        let trace = PANIC_DETAILS.with(|details| details.borrow_mut().take());
        Reply::metadata(json!({"ok":false,"fatal":true,"errorKind":"internal",
            "error":format!("The native processor stopped after an internal error. Reopen the application.\n{message}"),
            "errorContext":{"panic":message,"nativeBacktrace":trace}}))
    })
}

pub fn serve(
    input: &mut impl BufRead,
    output: &mut (impl Write + Send),
    root: PathBuf,
    example: bool,
) -> Result<(), String> {
    install_panic_report();
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
                            | "detector_file"
                            | "distortion_file"
                            | "settings"
                            | "integration_settings"
                            | "mask_stroke"
                            | "mask_edit"
                            | "image_transform"
                            | "clear_mask"
                            | "undo_mask"
                            | "redo_mask"
                            | "undo_calibration"
                            | "redo_calibration"
                            | "mask_plugin"
                    ),
                    Ordering::Release,
                );
                if controlled(&request.action) {
                    *worker_active.lock().unwrap() = Some(control.clone());
                    if worker_closing.load(Ordering::Acquire) {
                        control.cancel();
                    }
                }
                let (reply, fatal) =
                    match guarded(|| session.invoke_controlled(&request, control.clone())) {
                        Ok(reply) => (reply, false),
                        Err(reply) => (reply, true),
                    };
                control.finish();
                {
                    let mut active = worker_active.lock().unwrap();
                    if active.as_ref().is_some_and(|c| Arc::ptr_eq(c, &control)) {
                        *active = None;
                    }
                }
                worker_running.store(false, Ordering::Release);
                worker_write(request.id, reply, &request.cached_buffers)?;
                if fatal {
                    return Err("Native processing stopped after an internal error.".into());
                }
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
                        let reply = active.lock().unwrap().as_ref().map(|c|c.progress_reply()).unwrap_or_else(||Reply::metadata(json!({"ok":true,"progress":{"running":running.load(Ordering::Acquire),"current":0,"total":1}})));
                        write(request.id, reply, &[])?;
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
                        if controlled(&request.action) {
                            control.publish(json!({"running":true,"current":0,"total":1,"label":"Waiting for processing"}));
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

fn controlled(action: &str) -> bool {
    matches!(
        action,
        "calibrate"
            | "image_transform"
            | "mask_edit"
            | "mask_plugin"
            | "open_image"
            | "next_image"
            | "integrate"
            | "open_calibration"
            | "manual_geometry"
            | "detector_file"
            | "distortion_file"
            | "settings"
            | "integration_settings"
            | "integration_background"
            | "integration_image_background"
            | "integration_flat_field"
            | "integration_correction"
            | "integration_overlay"
            | "integration_phase"
            | "batch_load"
            | "batch_load_data"
            | "batch_folder"
            | "integration_batch"
            | "batch_folder_step"
            | "map_load"
            | "map_folder"
            | "map_poll"
            | "process_image_batch"
            | "open_project"
            | "save_project"
            | "configuration"
    )
}

#[cfg(test)]
mod panic_tests {
    use super::*;
    #[test]
    fn native_panic_returns_fatal_diagnostics_instead_of_losing_the_pending_reply() {
        install_panic_report();
        let reply = guarded(|| panic!("test native failure")).err().unwrap();
        assert_eq!(reply.result["fatal"], true);
        assert_eq!(reply.result["errorKind"], "internal");
        assert!(
            reply.result["errorContext"]["nativeBacktrace"]
                .as_str()
                .unwrap()
                .contains("test native failure")
        );
        assert!(reply.encode(42, &[]).unwrap().len() > 4);
        assert_eq!(
            guarded(|| Reply::metadata(json!({"ok":true})))
                .ok()
                .unwrap()
                .result["ok"],
            true
        );
    }
}
