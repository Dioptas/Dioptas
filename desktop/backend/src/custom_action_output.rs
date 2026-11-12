//! One shared reader drains inherited pipes through EOF without retaining a
//! thread per descendant. Admission bounds active children and retained streams;
//! each invocation owns its output independently of a reusable command ID.
use serde_json::{Value, json};
#[cfg(any(not(unix), test))]
use std::time::Duration;
use std::{
    io::{self, Read},
    process::Child,
    sync::{
        Arc, Mutex, OnceLock,
        atomic::{AtomicUsize, Ordering},
        mpsc,
    },
    thread::{self, JoinHandle},
};
pub(super) type Run = Arc<Mutex<Value>>;
const MAX_CAPTURED_RUNS: usize = 64;

trait OutputPipe: Read + Send {
    fn prepare(&self) -> io::Result<()>;
    fn read_available(&mut self, bytes: &mut [u8]) -> io::Result<usize>;
    #[cfg(unix)]
    fn descriptor(&self) -> std::os::fd::RawFd;
}
#[cfg(unix)]
impl<T: Read + Send + std::os::fd::AsRawFd> OutputPipe for T {
    fn prepare(&self) -> io::Result<()> {
        let descriptor = self.as_raw_fd();
        // SAFETY: these calls only adjust flags on our owned, live pipe reader.
        let flags = unsafe { libc::fcntl(descriptor, libc::F_GETFL) };
        if flags < 0
            || unsafe { libc::fcntl(descriptor, libc::F_SETFL, flags | libc::O_NONBLOCK) } < 0
        {
            return Err(io::Error::last_os_error());
        }
        Ok(())
    }
    fn read_available(&mut self, bytes: &mut [u8]) -> io::Result<usize> {
        self.read(bytes)
    }
    fn descriptor(&self) -> std::os::fd::RawFd {
        self.as_raw_fd()
    }
}
#[cfg(windows)]
impl<T: Read + Send + std::os::windows::io::AsRawHandle> OutputPipe for T {
    fn prepare(&self) -> io::Result<()> {
        Ok(())
    }
    fn read_available(&mut self, bytes: &mut [u8]) -> io::Result<usize> {
        use std::ffi::c_void;
        #[link(name = "kernel32")]
        unsafe extern "system" {
            fn PeekNamedPipe(
                pipe: *mut c_void,
                buffer: *mut c_void,
                size: u32,
                read: *mut u32,
                available: *mut u32,
                left: *mut u32,
            ) -> i32;
        }
        let mut available = 0;
        // SAFETY: the handle is our live anonymous pipe reader; null optional
        // outputs are permitted. No other thread consumes this pipe's bytes.
        if unsafe {
            PeekNamedPipe(
                self.as_raw_handle(),
                std::ptr::null_mut(),
                0,
                std::ptr::null_mut(),
                &mut available,
                std::ptr::null_mut(),
            )
        } == 0
        {
            return Err(io::Error::last_os_error());
        }
        if available == 0 {
            return Err(io::ErrorKind::WouldBlock.into());
        }
        let count = bytes.len().min(available as usize);
        self.read(&mut bytes[..count])
    }
}

#[derive(Clone)]
pub(super) struct Reservation {
    _slot: Arc<Slot>,
}
struct Slot {
    count: Arc<AtomicUsize>,
}
impl Drop for Slot {
    fn drop(&mut self) {
        self.count.fetch_sub(1, Ordering::AcqRel);
    }
}
fn take_slot(count: &Arc<AtomicUsize>) -> Result<Reservation, String> {
    let mut current = count.load(Ordering::Acquire);
    loop {
        if current >= MAX_CAPTURED_RUNS {
            return Err("Too many custom actions still have active processes or output streams. Wait for one to finish before launching another.".into());
        }
        match count.compare_exchange_weak(current, current + 1, Ordering::AcqRel, Ordering::Acquire)
        {
            Ok(_) => {
                return Ok(Reservation {
                    _slot: Arc::new(Slot {
                        count: count.clone(),
                    }),
                });
            }
            Err(updated) => current = updated,
        }
    }
}

struct Capture {
    pipes: Vec<Box<dyn OutputPipe>>,
    run: Run,
    output: Vec<u8>,
    _reservation: Reservation,
}
impl Capture {
    fn poll(&mut self) -> bool {
        let mut changed = false;
        self.pipes.retain_mut(|pipe| {
            let mut buffer = [0; 4096];
            // Fairness: one chatty action cannot starve the other streams.
            for _ in 0..16 {
                match pipe.read_available(&mut buffer) {
                    Ok(0) => return false,
                    Ok(size) => {
                        self.output.extend_from_slice(&buffer[..size]);
                        if self.output.len() > 16384 {
                            self.output.drain(..self.output.len() - 16384);
                        }
                        changed = true;
                    }
                    Err(error) if error.kind() == io::ErrorKind::Interrupted => {}
                    Err(error) if error.kind() == io::ErrorKind::WouldBlock => break,
                    Err(_) => return false,
                }
            }
            true
        });
        let mut run = self.run.lock().unwrap();
        if changed {
            run["output"] = json!(String::from_utf8_lossy(&self.output));
        }
        run["outputPending"] = json!(!self.pipes.is_empty());
        changed
    }
}
#[cfg(unix)]
fn wait_for_output(captures: &[Arc<Mutex<Capture>>], _progressed: bool) -> bool {
    let mut descriptors = Vec::new();
    for capture in captures {
        let capture = capture.lock().unwrap();
        descriptors.extend(capture.pipes.iter().map(|pipe| libc::pollfd {
            fd: pipe.descriptor(),
            events: libc::POLLIN,
            revents: 0,
        }));
    }
    // Wait for readiness rather than imposing a fixed byte/time rate. A noisy
    // pipe makes poll return immediately, while every sweep still visits all
    // captures with the same bounded per-pipe read budget. The short timeout
    // also admits queued captures while existing descendants remain silent.
    // SAFETY: poll only inspects these descriptor numbers. A concurrent parent
    // completion may close one after collection; POLLNVAL merely wakes us and
    // the next sweep checks actual owned pipes under their capture locks.
    unsafe {
        libc::poll(
            descriptors.as_mut_ptr(),
            descriptors.len() as libc::nfds_t,
            10,
        ) > 0
    }
}
#[cfg(not(unix))]
fn wait_for_output(_captures: &[Arc<Mutex<Capture>>], progressed: bool) -> bool {
    if progressed {
        thread::yield_now();
    } else {
        thread::sleep(Duration::from_millis(1));
    }
    progressed
}
struct OutputService {
    sender: mpsc::SyncSender<Arc<Mutex<Capture>>>,
    count: Arc<AtomicUsize>,
}
fn service() -> &'static OutputService {
    static SERVICE: OnceLock<OutputService> = OnceLock::new();
    SERVICE.get_or_init(|| {
        let (sender, receiver) = mpsc::sync_channel::<Arc<Mutex<Capture>>>(MAX_CAPTURED_RUNS);
        thread::spawn(move || {
            let mut captures = Vec::<Arc<Mutex<Capture>>>::new();
            loop {
                if captures.is_empty() {
                    match receiver.recv() {
                        Ok(capture) => captures.push(capture),
                        Err(_) => return,
                    }
                }
                captures.extend(receiver.try_iter());
                let mut progressed = false;
                for capture in &mut captures {
                    progressed |= capture.lock().unwrap().poll();
                }
                captures.retain(|capture| !capture.lock().unwrap().pipes.is_empty());
                if !captures.is_empty() {
                    wait_for_output(&captures, progressed);
                }
            }
        });
        OutputService {
            sender,
            count: Arc::new(AtomicUsize::new(0)),
        }
    })
}
pub(super) fn reserve() -> Result<Reservation, String> {
    take_slot(&service().count)
}

pub(super) fn monitor(
    mut child: Child,
    run: Run,
    reservation: Reservation,
) -> Result<JoinHandle<()>, String> {
    let stdout = child.stdout.take().expect("piped action stdout");
    let stderr = child.stderr.take().expect("piped action stderr");
    if let Err(error) = stdout.prepare().and_then(|_| stderr.prepare()) {
        let _ = child.kill();
        let _ = child.wait();
        return Err(error.to_string());
    }
    let capture = Arc::new(Mutex::new(Capture {
        pipes: vec![Box::new(stdout), Box::new(stderr)],
        run: run.clone(),
        output: Vec::new(),
        _reservation: reservation.clone(),
    }));
    if service().sender.try_send(capture.clone()).is_err() {
        let _ = child.kill();
        let _ = child.wait();
        return Err("Custom action output service is unavailable.".into());
    }
    Ok(thread::spawn(move || {
        let status = child.wait();
        // Preserve ordinary completion snapshots: collect bytes already written
        // by the direct child before publishing its exit, without waiting for
        // descendants to close their inherited writers.
        capture.lock().unwrap().poll();
        let mut state = run.lock().unwrap();
        state["running"] = json!(false);
        state["exitCode"] = json!(status.ok().and_then(|s| s.code()));
        drop(reservation);
    }))
}

#[cfg(all(test, unix))]
mod tests {
    use super::*;
    use std::{
        process::{Command, Stdio},
        time::Instant,
    };
    fn launch(script: &str, args: &[&std::path::Path], run: Run) -> JoinHandle<()> {
        let reservation = reserve().unwrap();
        let mut command = Command::new("/bin/sh");
        command
            .args(["-c", script, "action-test"])
            .args(args)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        let child = crate::child_process::spawn(command).unwrap();
        monitor(child, run, reservation).unwrap()
    }
    fn state() -> Run {
        Arc::new(Mutex::new(
            json!({"running":true,"exitCode":null,"output":""}),
        ))
    }
    fn until(mut predicate: impl FnMut() -> bool) {
        let deadline = Instant::now() + Duration::from_secs(3);
        while !predicate() {
            assert!(Instant::now() < deadline);
            thread::sleep(Duration::from_millis(5));
        }
    }
    #[test]
    fn completed_launcher_preserves_late_descendant_writes_through_eof() {
        let directory = tempfile::tempdir().unwrap();
        let gate = directory.path().join("gate");
        let result = directory.path().join("result");
        let run = state();
        let monitor = launch(
            "(i=0; while [ ! -f \"$1\" ] && [ \"$i\" -lt 300 ]; do i=$((i+1)); /bin/sleep 0.01; done; printf late && printf 0 > \"$2\") & exit 7",
            &[&gate, &result],
            run.clone(),
        );
        until(|| run.lock().unwrap()["running"] == false);
        monitor.join().unwrap();
        assert_eq!(run.lock().unwrap()["exitCode"], 7);
        assert_eq!(run.lock().unwrap()["outputPending"], true);
        assert!(!result.exists());
        thread::sleep(Duration::from_millis(350));
        std::fs::write(&gate, b"release").unwrap();
        until(|| std::fs::read_to_string(&result).is_ok_and(|result| result == "0"));
        until(|| {
            let run = run.lock().unwrap();
            run["output"] == "late" && run["outputPending"] == false
        });
    }
    #[test]
    fn deleting_and_reusing_an_identifier_cannot_mix_invocation_output() {
        let mut runs = std::collections::BTreeMap::new();
        let old = state();
        runs.insert("action", old.clone());
        let first = launch("(/bin/sleep 0.1; printf old) & exit 0", &[], old.clone());
        first.join().unwrap();
        runs.remove("action");
        let new = state();
        runs.insert("action", new.clone());
        let second = launch("printf new; exit 3", &[], new.clone());
        second.join().unwrap();
        until(|| old.lock().unwrap()["output"] == "old" && new.lock().unwrap()["output"] == "new");
        assert_eq!(new.lock().unwrap()["exitCode"], 3);
    }
    #[test]
    fn direct_child_output_is_available_in_its_completion_snapshot() {
        let run = state();
        launch("printf result; exit 0", &[], run.clone())
            .join()
            .unwrap();
        let run = run.lock().unwrap();
        assert_eq!(run["running"], false);
        assert_eq!(run["exitCode"], 0);
        assert_eq!(run["output"], "result");
        assert_eq!(run["outputPending"], false);
    }
    #[test]
    fn chatty_child_does_not_acquire_a_fixed_drain_rate_or_starve_another_action() {
        let run = state();
        let started = Instant::now();
        // The old 64 KiB/10 ms throttle requires at least ten seconds for this
        // real pipe transfer. No large data is retained or written to disk.
        let chatty = launch(
            "/bin/dd if=/dev/zero bs=65536 count=1024 2>/dev/null && printf chatty-tail",
            &[],
            run.clone(),
        );
        until(|| !run.lock().unwrap()["output"].as_str().unwrap().is_empty());
        let quiet = state();
        launch("printf quiet; exit 0", &[], quiet.clone())
            .join()
            .unwrap();
        assert_eq!(quiet.lock().unwrap()["output"], "quiet");
        assert!(
            started.elapsed() < Duration::from_secs(8),
            "chatty output starved another action"
        );
        chatty.join().unwrap();
        until(|| run.lock().unwrap()["outputPending"] == false);
        let elapsed = started.elapsed();
        let run = run.lock().unwrap();
        assert_eq!(run["exitCode"], 0);
        let output = run["output"].as_str().unwrap();
        assert!(output.ends_with("chatty-tail"));
        assert_eq!(output.len(), 16384);
        assert!(
            elapsed < Duration::from_secs(8),
            "64 MiB output was throttled: {elapsed:?}"
        );
    }
    #[test]
    fn readiness_wait_observes_live_data_and_eof_without_a_byte_rate_timer() {
        use std::{io::Write, os::unix::net::UnixStream};
        let (reader, mut writer) = UnixStream::pair().unwrap();
        reader.prepare().unwrap();
        let run = state();
        let capture = Arc::new(Mutex::new(Capture {
            pipes: vec![Box::new(reader)],
            run: run.clone(),
            output: Vec::new(),
            _reservation: take_slot(&Arc::new(AtomicUsize::new(0))).unwrap(),
        }));
        let captures = [capture];
        assert!(
            !wait_for_output(&captures, false),
            "silent live pipe must idle"
        );
        writer.write_all(b"ready").unwrap();
        assert!(
            wait_for_output(&captures, true),
            "readable pipe must be ready without a per-chunk sleep"
        );
        assert!(captures[0].lock().unwrap().poll());
        assert_eq!(run.lock().unwrap()["output"], "ready");
        assert_eq!(run.lock().unwrap()["outputPending"], true);
        // Explicitly end this socket's write direction: another parallel
        // fixture may be between fork and exec with a temporary fd duplicate.
        writer.shutdown(std::net::Shutdown::Write).unwrap();
        drop(writer);
        assert!(
            wait_for_output(&captures, false),
            "EOF must wake the reader too"
        );
        captures[0].lock().unwrap().poll();
        assert_eq!(run.lock().unwrap()["outputPending"], false);
    }
    #[test]
    fn admission_is_bounded_until_both_process_and_capture_release() {
        let count = Arc::new(AtomicUsize::new(0));
        let mut slots = (0..MAX_CAPTURED_RUNS)
            .map(|_| take_slot(&count).unwrap())
            .collect::<Vec<_>>();
        assert!(take_slot(&count).is_err());
        let capture = slots[0].clone();
        slots.remove(0);
        assert!(
            take_slot(&count).is_err(),
            "inherited streams must retain admission"
        );
        drop(capture);
        let replacement = take_slot(&count).unwrap();
        drop(slots);
        drop(replacement);
        assert_eq!(count.load(Ordering::Acquire), 0);
    }
}
