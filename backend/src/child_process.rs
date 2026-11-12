//! Owned subprocesses inherit their configured stdio, not native library files.
//! In particular, HDF5's sec2 driver can open descriptors without FD_CLOEXEC.
use std::{
    io,
    process::{Child, Command},
};

#[cfg(unix)]
fn descriptor_limit() -> io::Result<libc::c_int> {
    let mut limit = libc::rlimit {
        rlim_cur: 0,
        rlim_max: 0,
    };
    // SAFETY: getrlimit writes only the initialized, correctly sized structure.
    if unsafe { libc::getrlimit(libc::RLIMIT_NOFILE, &mut limit) } != 0 {
        return Err(io::Error::last_os_error());
    }
    // Include the finite hard ceiling when available, so lowering the soft
    // limit does not hide descriptors that were already open above it.
    let mut bound = limit.rlim_cur;
    if limit.rlim_max != libc::RLIM_INFINITY {
        bound = bound.max(limit.rlim_max);
    }
    if bound == libc::RLIM_INFINITY {
        // Read potentially allocating/libc-cached configuration in the parent,
        // never after fork. Refuse an indeterminate ceiling rather than leak.
        let open_max = unsafe { libc::sysconf(libc::_SC_OPEN_MAX) };
        if open_max <= 0 {
            return Err(io::Error::other(
                "No finite subprocess descriptor limit is available.",
            ));
        }
        return libc::c_int::try_from(open_max).map_err(|_| {
            io::Error::other("Subprocess descriptor limit exceeds the descriptor range.")
        });
    }
    libc::c_int::try_from(bound)
        .map_err(|_| io::Error::other("Subprocess descriptor limit exceeds the descriptor range."))
}

#[cfg(unix)]
fn mark_close_on_exec(limit: libc::c_int) -> io::Result<()> {
    #[cfg(target_os = "linux")]
    {
        // SAFETY: raw close_range(CLOEXEC) only changes flags in this forked
        // child's descriptor table. It does not close Rust's exec-error pipe.
        if unsafe {
            libc::syscall(
                libc::SYS_close_range,
                3_u32,
                u32::MAX,
                libc::CLOSE_RANGE_CLOEXEC,
            )
        } == 0
        {
            return Ok(());
        }
        // Older kernels and restricted syscall policies use the same safe
        // fcntl fallback as macOS; no arbitrary descriptor cap is imposed.
    }
    for descriptor in 3..limit {
        let flags = loop {
            // SAFETY: fcntl is async-signal-safe, and does not allocate. Closed
            // descriptors are expected while scanning the parent's ceiling.
            let flags = unsafe { libc::fcntl(descriptor, libc::F_GETFD) };
            if flags >= 0 {
                break flags;
            }
            let error = io::Error::last_os_error();
            match error.raw_os_error() {
                Some(libc::EBADF) => break -1,
                Some(libc::EINTR) => continue,
                _ => return Err(error),
            }
        };
        if flags < 0 || flags & libc::FD_CLOEXEC != 0 {
            continue;
        }
        loop {
            // Mark, rather than close: Rust still needs its internal pipe to
            // report an exec failure before the successful exec closes it.
            if unsafe { libc::fcntl(descriptor, libc::F_SETFD, flags | libc::FD_CLOEXEC) } == 0 {
                break;
            }
            let error = io::Error::last_os_error();
            if error.raw_os_error() != Some(libc::EINTR) {
                return Err(error);
            }
        }
    }
    Ok(())
}

/// Spawn an owned command with explicitly configured stdio. Ownership avoids
/// accidentally accumulating pre_exec hooks when reusing a Command builder.
pub fn spawn(mut command: Command) -> io::Result<Child> {
    #[cfg(unix)]
    {
        use std::os::unix::process::CommandExt;
        let limit = descriptor_limit()?;
        // SAFETY: the closure captures one integer and only calls the bounded,
        // allocation-free fcntl/syscall routine. It touches no Rust/HDF5 locks.
        unsafe {
            command.pre_exec(move || mark_close_on_exec(limit));
        }
        // Only the parent takes this gate. Other HDF5 threads must not close
        // and reopen a file during fork -> exec, before CLOEXEC releases the
        // child's inherited sec2 lock. The child never accesses this mutex.
        hdf5::sync::sync(|| command.spawn())
    }
    #[cfg(not(unix))]
    command.spawn()
}

#[cfg(all(test, unix))]
mod tests {
    use super::*;
    use std::os::fd::{AsRawFd, FromRawFd, OwnedFd};
    #[test]
    fn descriptor_probe_child() {
        let Ok(descriptor) = std::env::var("DIOPTAS_FD_PROBE") else {
            return;
        };
        let descriptor: i32 = descriptor.parse().unwrap();
        assert_eq!(unsafe { libc::fcntl(descriptor, libc::F_GETFD) }, -1);
        assert_eq!(io::Error::last_os_error().raw_os_error(), Some(libc::EBADF));
    }
    #[test]
    fn inheritable_native_descriptor_is_absent_after_exec_and_unchanged_in_parent() {
        let file = tempfile::tempfile().unwrap();
        let mut limits = libc::rlimit {
            rlim_cur: 0,
            rlim_max: 0,
        };
        // The production close scan includes the hard ceiling, but creating a
        // probe descriptor must respect this runner's current soft limit.
        assert_eq!(
            unsafe { libc::getrlimit(libc::RLIMIT_NOFILE, &mut limits) },
            0
        );
        let minimum = (limits.rlim_cur / 2).clamp(3, 4096) as libc::c_int;
        // F_DUPFD deliberately produces a non-CLOEXEC descriptor, like sec2.
        let descriptor = unsafe { libc::fcntl(file.as_raw_fd(), libc::F_DUPFD, minimum) };
        assert!(descriptor >= minimum);
        let owned = unsafe { OwnedFd::from_raw_fd(descriptor) };
        assert_eq!(
            unsafe { libc::fcntl(owned.as_raw_fd(), libc::F_GETFD) } & libc::FD_CLOEXEC,
            0
        );
        let mut command = Command::new(std::env::current_exe().unwrap());
        command
            .args(["--exact", "child_process::tests::descriptor_probe_child"])
            .env("DIOPTAS_FD_PROBE", descriptor.to_string());
        assert!(spawn(command).unwrap().wait().unwrap().success());
        assert_eq!(
            unsafe { libc::fcntl(owned.as_raw_fd(), libc::F_GETFD) } & libc::FD_CLOEXEC,
            0
        );
    }
    #[test]
    fn exec_errors_and_configured_stdio_survive_the_boundary() {
        let error = spawn(Command::new("/nonexistent/dioptas-fake-child")).unwrap_err();
        assert_eq!(error.kind(), io::ErrorKind::NotFound);
        let mut command = Command::new("/bin/sh");
        command
            .args(["-c", "printf output; printf error >&2; exit 7"])
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped());
        let result = spawn(command).unwrap().wait_with_output().unwrap();
        assert_eq!(result.status.code(), Some(7));
        assert_eq!(result.stdout, b"output");
        assert_eq!(result.stderr, b"error");
    }
    #[test]
    fn concurrent_hdf_close_and_reopen_waits_until_child_exec() {
        use std::{
            io::{Read, Write},
            os::unix::{net::UnixStream, process::CommandExt},
            sync::mpsc,
            time::Duration,
        };
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("owned.h5");
        let file = hdf5::File::create(&path).unwrap();
        let (mut parent_gate, child_gate) = UnixStream::pair().unwrap();
        let descriptor = child_gate.as_raw_fd();
        let spawner = std::thread::spawn(move || {
            let _gate = child_gate;
            let mut command = Command::new("/bin/sh");
            command.args(["-c", "exit 0"]);
            // Test-only fork handshake: hold the child before exec so the HDF
            // closer runs during that exact window, rather than racing a sleep.
            // SAFETY: read/write on our live socket are async-signal-safe. The
            // closure captures only its descriptor, with no locks/allocation.
            unsafe {
                command.pre_exec(move || {
                    let mut byte = 1_u8;
                    if libc::write(descriptor, (&byte as *const u8).cast(), 1) != 1 {
                        return Err(io::Error::last_os_error());
                    }
                    loop {
                        if libc::read(descriptor, (&mut byte as *mut u8).cast(), 1) == 1 {
                            return Ok(());
                        }
                        let error = io::Error::last_os_error();
                        if error.raw_os_error() != Some(libc::EINTR) {
                            return Err(error);
                        }
                    }
                });
            }
            spawn(command).unwrap().wait().unwrap()
        });
        let mut ready = [0];
        parent_gate.read_exact(&mut ready).unwrap();
        let (started_tx, started_rx) = mpsc::channel();
        let (done_tx, done_rx) = mpsc::channel();
        let closer = std::thread::spawn(move || {
            started_tx.send(()).unwrap();
            let result = hdf5::sync::sync(|| {
                drop(file);
                hdf5::File::open_rw(&path)
                    .map(|_| ())
                    .map_err(|e| e.to_string())
            });
            done_tx.send(result).unwrap();
        });
        started_rx.recv().unwrap();
        let before_exec = done_rx.recv_timeout(Duration::from_millis(50));
        // Always release the fixture child, including the negative-control
        // failure path, before asserting or waiting for any HDF operation.
        parent_gate.write_all(&[1]).unwrap();
        assert!(spawner.join().unwrap().success());
        closer.join().unwrap();
        assert!(matches!(before_exec, Err(mpsc::RecvTimeoutError::Timeout)));
        done_rx.recv().unwrap().unwrap();
    }
}
