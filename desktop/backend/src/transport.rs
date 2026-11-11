//! Bounded local stdio, compatible with the existing Tauri processor pipe.
//! One command worker owns the mutable session. Bulk jobs lend immutable reader/
//! plan snapshots to scoped frame workers. Progress bypasses the command queue.
use crate::{
    Session,
    control::Control,
    protocol::{
        MAX_REQUEST_BYTES, Reply, Request,
        command_contract::{CommandExecution, REQUEST_SIZE_ERROR, execution},
    },
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

/// Recover routing metadata without parsing/allocating an oversized payload.
/// Host requests put their id before payload. Other clients that omit an early
/// top-level id receive an uncorrelated id-0 rejection; the session still lives.
fn oversized_request_id(prefix: &[u8]) -> u64 {
    use serde::Deserializer;
    use serde::de::{IgnoredAny, MapAccess, Visitor};
    struct IdVisitor<'a>(&'a mut Option<u64>);
    impl<'de> Visitor<'de> for IdVisitor<'_> {
        type Value = ();
        fn expecting(&self, formatter: &mut std::fmt::Formatter) -> std::fmt::Result {
            formatter.write_str("a request object with an early id")
        }
        fn visit_map<M: MapAccess<'de>>(self, mut map: M) -> Result<(), M::Error> {
            while let Some(key) = map.next_key::<String>()? {
                if key == "id" {
                    *self.0 = Some(map.next_value::<u64>()?);
                    return Ok(());
                }
                map.next_value::<IgnoredAny>()?;
            }
            Ok(())
        }
    }
    let mut id = None;
    let bounded = &prefix[..prefix.len().min(64 * 1024)];
    // Parsing may stop in a truncated payload. Only a structurally parsed
    // top-level id is retained; strings containing `"id":` cannot spoof it.
    let _ = serde_json::Deserializer::from_slice(bounded).deserialize_map(IdVisitor(&mut id));
    id.unwrap_or(0)
}

fn drain_request_line(input: &mut impl BufRead) -> std::io::Result<()> {
    loop {
        let bytes = input.fill_buf()?;
        let end = bytes.iter().position(|&b| b == b'\n');
        let consumed = end.map_or(bytes.len(), |index| index + 1);
        input.consume(consumed);
        if consumed == 0 || end.is_some() {
            return Ok(());
        }
    }
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
        let mut trace = crate::frame_trace::FrameTrace::new("packet", id);
        let packet = reply.packet_parts(id, known)?;
        trace.mark("encode response");
        let mut stream = output
            .lock()
            .map_err(|_| "Processing output lock failed.")?;
        let result = packet
            .write_to(&mut *stream)
            .and_then(|_| stream.flush())
            .map_err(|e| e.to_string());
        trace.mark("write and flush");
        result
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
                let cancellable = execution(&request.action) == CommandExecution::Cancellable;
                worker_running.store(cancellable, Ordering::Release);
                if cancellable {
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
                    // Discard only this newline-delimited frame, never the
                    // scientific session. Keep memory bounded while draining.
                    let id = oversized_request_id(&line);
                    if line.last() != Some(&b'\n') {
                        drain_request_line(input).map_err(|e| e.to_string())?;
                    }
                    write(id, Reply::error(REQUEST_SIZE_ERROR), &[])?;
                    continue;
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
                            Reply::success()
                        } else if running.load(Ordering::Acquire) {
                            Reply::error(
                                "The current native integration call cannot be interrupted.",
                            )
                        } else {
                            Reply::success()
                        };
                        write(request.id, reply, &[])?;
                    }
                    _ => {
                        let control = Arc::new(Control::default());
                        if execution(&request.action) == CommandExecution::Cancellable {
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
        assert_eq!(guarded(Reply::success).ok().unwrap().result["ok"], true);
    }
}

#[cfg(test)]
mod request_tests {
    use super::*;
    use serde_json::Value;
    use std::{collections::HashMap, io::Cursor};

    #[test]
    fn oversized_frame_rejection_preserves_the_unsaved_session_and_next_request() {
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
        let mut input = serde_json::to_vec(&json!({"id":1,"action":"configuration",
            "payload":{"operation":"rename","name":"Unsaved configuration"}}))
        .unwrap();
        input.extend_from_slice(
            b"\n{\"id\":2,\"action\":\"integration_save_pattern\",\"payload\":{\"svg_data\":\"",
        );
        input.resize(input.len() + MAX_REQUEST_BYTES, b'x');
        input.extend_from_slice(b"\"}}\n{\"id\":3,\"action\":\"state\"}\n");
        let mut output = Vec::new();
        serve(&mut Cursor::new(input), &mut output, root, false).unwrap();
        let mut packets = HashMap::<u64, Value>::new();
        let mut offset = 0;
        while offset < output.len() {
            let length =
                u32::from_le_bytes(output[offset..offset + 4].try_into().unwrap()) as usize;
            offset += 4;
            let header: Value = serde_json::from_slice(&output[offset..offset + length]).unwrap();
            offset += length;
            offset += header["buffers"]
                .as_array()
                .unwrap()
                .iter()
                .map(|buffer| buffer["length"].as_u64().unwrap() as usize)
                .sum::<usize>();
            packets.insert(header["id"].as_u64().unwrap(), header["result"].clone());
        }
        assert_eq!(packets.len(), 3);
        assert_eq!(packets[&1]["ok"], true);
        assert_eq!(packets[&2]["ok"], false);
        assert_eq!(packets[&2]["error"], REQUEST_SIZE_ERROR);
        assert_eq!(packets[&3]["ok"], true);
        assert_eq!(packets[&3]["state"], packets[&1]["state"]);
        assert_eq!(
            packets[&3]["state"]["configurationLabels"][0],
            "Unsaved configuration"
        );
    }

    #[test]
    fn oversized_id_recovery_is_structural_and_bounded() {
        assert_eq!(
            oversized_request_id(br#"{"id":17,"payload":{"text":"unfinished"#),
            17
        );
        assert_eq!(
            oversized_request_id(br#"{"payload":{"id":42},"id":18,"extra":"unfinished"#),
            18
        );
        assert_eq!(
            oversized_request_id(br#"{"payload":{"text":"\"id\":42"},"id":19,"extra":"unfinished"#),
            19
        );
        assert_eq!(oversized_request_id(br#"{"payload":{"id":42}"#), 0);
        assert_eq!(oversized_request_id(br#"{"id":-1,"payload":{}"#), 0);
        let mut late = br#"{"padding":""#.to_vec();
        late.resize(late.len() + 64 * 1024, b'x');
        late.extend_from_slice(br#"","id":20}"#);
        assert_eq!(oversized_request_id(&late), 0);
    }

    #[test]
    fn draining_a_frame_does_not_consume_the_next_one() {
        let mut input = std::io::BufReader::with_capacity(3, Cursor::new(b"tail\nnext\n"));
        drain_request_line(&mut input).unwrap();
        let mut next = String::new();
        input.read_line(&mut next).unwrap();
        assert_eq!(next, "next\n");
        drain_request_line(&mut Cursor::new(b"unterminated")).unwrap();
    }
}
