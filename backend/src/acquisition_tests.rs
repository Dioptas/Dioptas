//! Real acquisition/decoder/integration regressions, without a UI or background timers.
use super::*;
use crate::protocol::Request;
use std::{fs, io::Write};
fn call(s: &mut Session, action: &str, payload: Value) -> Reply {
    let r = s.invoke(&Request {
        id: 1,
        action: action.into(),
        payload,
        cached_buffers: vec![],
    });
    assert_eq!(r.result["ok"], true, "{action}: {}", r.result);
    r
}
fn image(path: &Path, value: f64) {
    let mut header = "{'descr': '<f8', 'fortran_order': False, 'shape': (24, 32), }".to_string();
    while !(10 + header.len() + 1).is_multiple_of(64) {
        header.push(' ');
    }
    header.push('\n');
    let mut f = fs::File::create(path).unwrap();
    f.write_all(b"\x93NUMPY\x01\x00").unwrap();
    f.write_all(&(header.len() as u16).to_le_bytes()).unwrap();
    f.write_all(header.as_bytes()).unwrap();
    for i in 0..768 {
        f.write_all(&(value + (i % 32) as f64).to_le_bytes())
            .unwrap();
    }
}
fn prepared(directory: &Path) -> Session {
    fs::create_dir_all(directory).unwrap();
    let baseline = directory.join("baseline.npy");
    image(&baseline, 100.);
    let mut s = Session::new(Path::new(env!("CARGO_MANIFEST_DIR")).join(".."));
    call(
        &mut s,
        "manual_geometry",
        json!({"convention":"pyfai","values":{"dist":0.13,"poni1":0.0012,"poni2":0.0016,"pixel1":0.0001,"pixel2":0.0001,"rot1":0,"rot2":0,"rot3":0,"wavelength":5e-11,"polarization_factor":0.965}}),
    );
    call(
        &mut s,
        "integration_settings",
        json!({"bins":32,"cake_bins":8,"trim_zeros":false}),
    );
    call(&mut s, "open_image", json!({"path":baseline}));
    call(
        &mut s,
        "integration_autoprocess",
        json!({"enabled":true,"directory":directory}),
    );
    s
}
fn poll(s: &mut Session) -> Reply {
    call(s, "integration_autoprocess_poll", json!({}))
}
fn polls_until(s: &mut Session, predicate: impl Fn(&Session) -> bool) {
    for _ in 0..20 {
        if predicate(s) {
            return;
        }
        poll(s);
    }
    assert!(
        predicate(s),
        "acquisition did not recover: {}",
        s.files.auto_error
    );
}
#[test]
fn acquisition_output_repair_retries_unchanged_sources_and_preserves_science() {
    let temp = tempfile::tempdir().unwrap();
    let d = temp.path();
    let output = d.join("output");
    fs::create_dir(&output).unwrap();
    let mut s = prepared(d);
    call(
        &mut s,
        "integration_autocreate",
        json!({"enabled":true,"directory":output}),
    );
    let before = s.pattern.clone();
    fs::remove_dir(&output).unwrap();
    fs::write(&output, "blocked output volume").unwrap();
    for i in 0..2 {
        image(&d.join(format!("scan_{i}.npy")), 200. + i as f64);
    }
    let identities: Vec<_> = (0..2)
        .map(|i| s.files.stamp(&d.join(format!("scan_{i}.npy"))))
        .collect();
    for _ in 0..4 {
        poll(&mut s);
    }
    assert_eq!(s.pattern, before);
    assert_eq!(s.files.retry.len(), 2);
    assert!(s.files.failed.is_empty());
    assert!(s.files.auto_error.contains("Automatic output failed"));
    fs::remove_file(&output).unwrap();
    fs::create_dir(&output).unwrap();
    polls_until(&mut s, |s| s.files.retry.is_empty());
    for (i, identity) in identities.iter().enumerate() {
        assert_eq!(&s.files.stamp(&d.join(format!("scan_{i}.npy"))), identity);
        assert!(output.join(format!("scan_{i}.xy")).is_file());
    }
    assert!(s.files.auto_error.is_empty());
    let final_source = s.image.as_ref().unwrap().path.clone();
    let mut reference = prepared(&d.join("reference"));
    call(&mut reference, "open_image", json!({"path":final_source}));
    assert_eq!(s.pattern, reference.pattern);
}
#[test]
fn acquisition_generated_dat_is_excluded_but_replacement_detector_dat_is_admitted() {
    let temp = tempfile::tempdir().unwrap();
    let d = temp.path();
    let mut s = prepared(d);
    call(&mut s, "integration_settings", json!({"formats":[".dat"]}));
    call(&mut s, "integration_autocreate", json!({"enabled":true}));
    image(&d.join("scan.npy"), 200.);
    polls_until(&mut s, |_| d.join("scan.dat").is_file());
    let snapshot = s.pattern.clone();
    for _ in 0..3 {
        assert!(poll(&mut s).result.get("state").is_none());
    }
    assert!(s.files.failed.is_empty());
    assert!(s.files.retry.is_empty());
    assert_eq!(s.pattern, snapshot);
    // Content detection supports a valid detector container with a .dat suffix.
    call(&mut s, "integration_autocreate", json!({"enabled":false}));
    image(&d.join("detector.dat"), 250.);
    polls_until(&mut s, |s| {
        s.image.as_ref().unwrap().path.ends_with("detector.dat")
    });
    image(&d.join("scan.dat"), 300.);
    polls_until(&mut s, |s| {
        s.image.as_ref().unwrap().path.ends_with("scan.dat")
    });
    assert!(!s.files.generated.contains_key(&d.join("scan.dat")));
}
#[test]
fn acquisition_automatic_output_never_replaces_an_existing_detector_source() {
    let temp = tempfile::tempdir().unwrap();
    let d = temp.path();
    image(&d.join("detector.dat"), 300.);
    let original = fs::read(d.join("detector.dat")).unwrap();
    let mut s = prepared(d);
    call(&mut s, "integration_settings", json!({"formats":[".dat"]}));
    call(&mut s, "integration_autocreate", json!({"enabled":true}));
    image(&d.join("detector.npy"), 400.);
    for _ in 0..4 {
        poll(&mut s);
    }
    assert_eq!(fs::read(d.join("detector.dat")).unwrap(), original);
    assert!(s.files.auto_error.contains("replace the detector source"));
    assert_eq!(s.files.retry.len(), 1);
}
fn external_master(path: &Path, data: &Path, raw: bool) {
    let file = hdf5::File::create(path).unwrap();
    if raw {
        file.new_dataset::<u16>()
            .shape((24, 32))
            .external(data.to_str().unwrap(), 0, 24 * 32 * 2)
            .create("counts")
            .unwrap();
    } else {
        file.create_group("entry/data").unwrap();
        file.link_external(data.to_str().unwrap(), "/images", "/entry/data/data_000001")
            .unwrap();
    }
}
#[test]
fn acquisition_missing_external_raw_recovers_without_changing_master_or_opening_dialog() {
    companion_recovery(true);
}
#[test]
fn acquisition_missing_eiger_companion_recovers_without_changing_master_or_stalling_later_files() {
    companion_recovery(false);
}
fn companion_recovery(raw: bool) {
    companion_recovery_from(raw, false);
}
#[test]
fn acquisition_incomplete_raw_companion_recovers_when_existing_file_grows() {
    companion_recovery_from(true, true);
}
#[test]
fn acquisition_existing_hdf5_companion_recovers_when_declared_dataset_arrives() {
    companion_recovery_from(false, true);
}
fn companion_recovery_from(raw: bool, incomplete: bool) {
    companion_recovery_selected(raw, incomplete, None);
}
#[test]
fn acquisition_explicit_selected_external_dataset_recovers_without_master_change() {
    companion_recovery_selected(false, false, Some("/entry/data/data_000001"));
}
#[test]
fn acquisition_selected_soft_alias_to_external_dataset_recovers_without_master_change() {
    companion_recovery_selected(false, false, Some("/selected"));
}
fn companion_recovery_selected(raw: bool, incomplete: bool, selected: Option<&str>) {
    let temp = tempfile::tempdir().unwrap();
    let d = temp.path().join("incoming");
    fs::create_dir(&d).unwrap();
    let mut s = prepared(&d);
    let data = temp.path().join(if raw { "pixels.raw" } else { "data.h5" });
    let master = d.join("master.h5");
    if incomplete {
        if raw {
            fs::write(&data, [0; 8]).unwrap();
        } else {
            hdf5::File::create(&data).unwrap();
        }
    }
    external_master(&master, &data, raw);
    if let Some(selected) = selected {
        if selected == "/selected" {
            hdf5::File::open_rw(&master)
                .unwrap()
                .link_soft("/entry/data/data_000001", "selected")
                .unwrap();
        }
        s.image.as_mut().unwrap().options["dataset"] = json!(selected);
    }
    let original = fs::read(&master).unwrap();
    let stamp = s.files.stamp(&master);
    if raw && !incomplete {
        assert!(
            Image::binding_request(&master, &json!({}))
                .unwrap()
                .is_some(),
            "The raw fixture must exercise an actual HDF5 chooser deferral"
        );
    }
    poll(&mut s);
    let waiting = poll(&mut s);
    assert!(waiting.result.get("hdf5SourceRequest").is_none());
    assert!(waiting.result.get("imageChange").is_none());
    assert_eq!(s.files.retry.len(), 1);
    assert!(s.files.auto_process);
    let attempts = s
        .files
        .decode_attempts
        .load(std::sync::atomic::Ordering::Relaxed);
    let message = s.files.auto_error.clone();
    for _ in 0..3 {
        assert!(poll(&mut s).result.get("state").is_none());
        assert_eq!(s.files.auto_error, message);
    }
    assert_eq!(
        s.files
            .decode_attempts
            .load(std::sync::atomic::Ordering::Relaxed),
        attempts
    );
    let later = if let Some(dataset) = selected {
        let path = d.join("later.h5");
        let file = hdf5::File::create(&path).unwrap();
        if let Some(parent) = Path::new(dataset)
            .parent()
            .and_then(Path::to_str)
            .filter(|parent| *parent != "/")
        {
            file.create_group(parent).unwrap();
        }
        file.new_dataset::<u16>()
            .shape((24, 32))
            .create(dataset)
            .unwrap()
            .write_raw(&vec![230u16; 768])
            .unwrap();
        path
    } else {
        let path = d.join("later.npy");
        image(&path, 230.);
        path
    };
    let later = later.canonicalize().unwrap();
    polls_until(&mut s, |s| s.image.as_ref().unwrap().path == later);
    if raw {
        let bytes: Vec<_> = (0..768u16).flat_map(|v| v.to_le_bytes()).collect();
        fs::write(&data, bytes).unwrap();
    } else {
        let f = hdf5::File::create(&data).unwrap();
        f.new_dataset::<u16>()
            .shape((1, 24, 32))
            .create("images")
            .unwrap()
            .write_raw(&vec![42u16; 768])
            .unwrap();
    }
    polls_until(&mut s, |s| s.files.retry.is_empty());
    assert_eq!(fs::read(&master).unwrap(), original);
    assert_eq!(s.files.stamp(&master), stamp);
    assert_eq!(
        s.image.as_ref().unwrap().path,
        master.canonicalize().unwrap()
    );
    assert!(s.files.auto_error.is_empty());
}
#[test]
fn acquisition_known_files_skip_stats_and_share_unchanged_checkpoint_collections() {
    let temp = tempfile::tempdir().unwrap();
    for i in 0..100 {
        fs::write(temp.path().join(format!("known_{i}.npy")), b"existing").unwrap();
    }
    let mut files = Files {
        image_directory: temp.path().to_string_lossy().into_owned(),
        ..Default::default()
    };
    files.baseline().unwrap();
    let before = files.clone();
    files.stamp_reads.set(0);
    files.poll().unwrap();
    assert_eq!(files.stamp_reads.get(), 0);
    assert!(Arc::ptr_eq(&files.known, &before.known));
    assert!(Arc::ptr_eq(&files.pending, &before.pending));
    let mut serialized = serde_json::to_value(&files).unwrap();
    serialized.as_object_mut().unwrap().remove("retry");
    serialized.as_object_mut().unwrap().remove("generated");
    let restored: Files = serde_json::from_value(serialized).unwrap();
    assert_eq!(restored.known, files.known);
    assert!(restored.retry.is_empty());
}
#[test]
fn acquisition_admission_orders_by_time_then_name_and_drain_preserves_every_export() {
    let temp = tempfile::tempdir().unwrap();
    let d = temp.path();
    let output = d.join("output");
    fs::create_dir(&output).unwrap();
    let mut s = prepared(d);
    call(
        &mut s,
        "integration_autocreate",
        json!({"enabled":true,"directory":output}),
    );
    for i in (0..12).rev() {
        let p = d.join(format!("scan_{i:02}.npy"));
        image(&p, 200. + i as f64);
        fs::File::options()
            .write(true)
            .open(&p)
            .unwrap()
            .set_times(
                fs::FileTimes::new()
                    .set_modified(SystemTime::UNIX_EPOCH + Duration::from_secs(i + 1)),
            )
            .unwrap();
    }
    poll(&mut s);
    let mut scan = s.files.clone();
    scan.poll().unwrap();
    let order: Vec<_> = std::iter::from_fn(|| scan.next())
        .map(|i| i.path.file_name().unwrap().to_string_lossy().into_owned())
        .collect();
    assert_eq!(
        order,
        (0..12)
            .map(|i| format!("scan_{i:02}.npy"))
            .collect::<Vec<_>>()
    );
    poll(&mut s);
    let count = fs::read_dir(&output).unwrap().count();
    assert!(count > 0 && count <= 8);
    let name = format!("scan_{:02}.npy", count - 1);
    assert!(s.image.as_ref().unwrap().path.ends_with(name));
    polls_until(&mut s, |s| s.files.queue.is_empty());
    for i in 0..12 {
        assert!(output.join(format!("scan_{i:02}.xy")).is_file());
    }
    assert!(s.image.as_ref().unwrap().path.ends_with("scan_11.npy"));
}
#[test]
fn acquisition_cancelled_queued_poll_retains_sources_for_the_next_control() {
    let temp = tempfile::tempdir().unwrap();
    let d = temp.path();
    let mut s = prepared(d);
    image(&d.join("next.npy"), 200.);
    poll(&mut s);
    let before = s.pattern.clone();
    s.control.cancel();
    let reply = s.poll_acquisition().unwrap();
    assert_eq!(reply.result["cancelled"], true);
    assert_eq!(s.pattern, before);
    assert_eq!(s.files.queue.len(), 1);
    assert!(s.files.failed.is_empty());
    s.control = Arc::new(Control::default());
    polls_until(&mut s, |s| s.files.queue.is_empty());
    assert!(s.image.as_ref().unwrap().path.ends_with("next.npy"));
}
#[test]
fn acquisition_unchanged_corrupt_non_hdf5_is_not_redecoded() {
    let temp = tempfile::tempdir().unwrap();
    let d = temp.path();
    let mut s = prepared(d);
    fs::write(d.join("broken.npy"), b"incomplete").unwrap();
    poll(&mut s);
    poll(&mut s);
    assert_eq!(s.files.failed.len(), 1);
    assert!(s.files.retry.is_empty());
    for _ in 0..3 {
        assert!(poll(&mut s).result.get("state").is_none());
    }
    image(&d.join("broken.npy"), 250.);
    poll(&mut s);
    poll(&mut s);
    assert!(s.files.failed.is_empty());
    assert!(s.image.as_ref().unwrap().path.ends_with("broken.npy"));
}

#[test]
fn acquisition_partial_output_failure_keeps_generated_paths_out_of_the_source_queue() {
    let temp = tempfile::tempdir().unwrap();
    let d = temp.path();
    let mut s = prepared(d);
    call(
        &mut s,
        "integration_settings",
        json!({"formats":[".dat",".xy"]}),
    );
    call(&mut s, "integration_autocreate", json!({"enabled":true}));
    fs::create_dir(d.join("scan.xy")).unwrap();
    image(&d.join("scan.npy"), 200.);
    for _ in 0..4 {
        poll(&mut s);
    }
    assert!(d.join("scan.dat").is_file());
    assert!(
        s.files
            .generated
            .contains_key(&d.join("scan.dat").canonicalize().unwrap())
    );
    assert!(s.files.failed.is_empty());
    assert_eq!(s.files.retry.len(), 1);
    fs::remove_dir(d.join("scan.xy")).unwrap();
    polls_until(&mut s, |s| s.files.retry.is_empty());
    assert!(d.join("scan.xy").is_file());
    assert!(s.image.as_ref().unwrap().path.ends_with("scan.npy"));
}
#[test]
#[cfg(unix)]
fn acquisition_output_alias_cannot_replace_the_active_source() {
    let temp = tempfile::tempdir().unwrap();
    let d = temp.path();
    let mut s = prepared(d);
    call(&mut s, "integration_settings", json!({"formats":[".dat"]}));
    call(&mut s, "integration_autocreate", json!({"enabled":true}));
    let source = d.join("baseline.npy");
    let before = fs::read(&source).unwrap();
    let alias = d.join("baseline.dat");
    std::os::unix::fs::symlink(&source, &alias).unwrap();
    assert!(
        s.auto_save()
            .unwrap_err()
            .contains("replace the detector source")
    );
    assert_eq!(fs::read(&source).unwrap(), before);
    assert!(fs::symlink_metadata(&alias).unwrap().is_symlink());
}

#[test]
#[cfg(unix)]
fn acquisition_replaced_output_is_not_hidden_when_size_and_mtime_are_preserved() {
    let temp = tempfile::tempdir().unwrap();
    let d = temp.path().canonicalize().unwrap();
    let output = d.join("scan.dat");
    fs::write(&output, b"generated").unwrap();
    let mut files = Files {
        image_directory: d.to_string_lossy().into_owned(),
        ..Default::default()
    };
    files.output_written(&output);
    let stamp = files.stamp(&output).unwrap();
    assert!(files.scan().unwrap().is_empty());
    let replacement = d.join("new-source");
    fs::write(&replacement, b"new image").unwrap();
    fs::File::options()
        .write(true)
        .open(&replacement)
        .unwrap()
        .set_times(fs::FileTimes::new().set_modified(stamp.1))
        .unwrap();
    fs::rename(&replacement, &output).unwrap();
    assert_eq!(files.stamp(&output), Some(stamp));
    assert_eq!(files.scan().unwrap(), BTreeSet::from([output]));
}

#[test]
fn acquisition_combined_products_keep_completed_prefix_when_a_later_frame_is_cancelled() {
    let temp = tempfile::tempdir().unwrap();
    let d = temp.path();
    let output = d.join("output");
    fs::create_dir(&output).unwrap();
    let mut s = prepared(d);
    call(&mut s, "configuration", json!({"operation":"duplicate"}));
    call(
        &mut s,
        "combination_settings",
        json!({"patterns":true,"cakes":true}),
    );
    let before_pattern = s.combination.pattern.clone();
    let before_cake = s.combination.cake.as_ref().unwrap().buffer.id.clone();
    call(
        &mut s,
        "integration_autocreate",
        json!({"enabled":true,"directory":output}),
    );
    for i in 1..=3 {
        let source = d.join(format!("scan_{i}.npy"));
        image(&source, 100. + i as f64 * 100.);
        fs::File::options()
            .write(true)
            .open(source)
            .unwrap()
            .set_times(
                fs::FileTimes::new().set_modified(SystemTime::UNIX_EPOCH + Duration::from_secs(i)),
            )
            .unwrap();
    }
    s.files.before_combination = Some(|control, path| {
        if path.ends_with("scan_2.npy") {
            control.cancel();
        }
    });
    poll(&mut s);
    let mut cancelled = None;
    // The time budget may split the drain; the controlled cancellation itself
    // is tied to the second source after its decode/integration, never a timer.
    for _ in 0..4 {
        let reply = poll(&mut s);
        if reply.result["cancelled"] == true {
            cancelled = Some(reply);
            break;
        }
    }
    let reply = cancelled.expect("second source must reach controlled cancellation");
    assert!(s.image.as_ref().unwrap().path.ends_with("scan_1.npy"));
    assert_ne!(s.combination.pattern, before_pattern);
    assert_ne!(s.combination.cake.as_ref().unwrap().buffer.id, before_cake);
    assert_eq!(
        reply.result["pattern"]["y"],
        s.combination.pattern.as_ref().unwrap()["y"]
    );
    assert_eq!(
        reply.result["cake"]["bufferId"],
        s.combination.cake.as_ref().unwrap().buffer.id
    );
    assert_eq!(s.files.queue.len(), 2);
    assert!(output.join("scan_1.xy").is_file());
    assert!(!output.join("scan_2.xy").exists());
    assert!(s.files.failed.is_empty());
    assert!(s.files.retry.is_empty());
    s.files.before_combination = None;
    polls_until(&mut s, |s| s.files.queue.is_empty());
    assert!(s.image.as_ref().unwrap().path.ends_with("scan_3.npy"));
    assert!(output.join("scan_2.xy").is_file());
    assert!(output.join("scan_3.xy").is_file());
}

#[test]
fn acquisition_non_image_hdf5_is_failed_once_and_later_polls_are_quiet() {
    let temp = tempfile::tempdir().unwrap();
    let mut s = prepared(temp.path());
    let file = hdf5::File::create(temp.path().join("analysis.h5")).unwrap();
    file.new_dataset::<f64>()
        .shape(4)
        .create("metadata")
        .unwrap()
        .write_raw(&[1., 2., 3., 4.])
        .unwrap();
    drop(file);
    poll(&mut s);
    poll(&mut s);
    assert_eq!(s.files.failed.len(), 1);
    assert!(s.files.retry.is_empty());
    let attempts = s
        .files
        .decode_attempts
        .load(std::sync::atomic::Ordering::Relaxed);
    for _ in 0..3 {
        assert!(poll(&mut s).result.get("state").is_none());
    }
    assert_eq!(
        s.files
            .decode_attempts
            .load(std::sync::atomic::Ordering::Relaxed),
        attempts
    );
    assert_eq!(attempts, 1);
}
#[test]
fn acquisition_output_retry_becoming_corrupt_is_failed_without_retry_or_redecode() {
    let temp = tempfile::tempdir().unwrap();
    let output = temp.path().join("output");
    fs::create_dir(&output).unwrap();
    let mut s = prepared(temp.path());
    call(
        &mut s,
        "integration_autocreate",
        json!({"enabled":true,"directory":output}),
    );
    fs::remove_dir(&output).unwrap();
    fs::write(&output, b"blocked").unwrap();
    let path = temp.path().join("incoming.npy");
    image(&path, 220.);
    poll(&mut s);
    poll(&mut s);
    assert_eq!(s.files.retry.len(), 1);
    assert!(
        poll(&mut s).result.get("state").is_none(),
        "Unchanged output failures must remain quiet"
    );
    fs::write(&path, b"corrupt source").unwrap();
    poll(&mut s);
    assert_eq!(s.files.failed.len(), 1);
    assert!(s.files.retry.is_empty());
    let attempts = s
        .files
        .decode_attempts
        .load(std::sync::atomic::Ordering::Relaxed);
    for _ in 0..3 {
        assert!(poll(&mut s).result.get("state").is_none());
    }
    assert_eq!(
        s.files
            .decode_attempts
            .load(std::sync::atomic::Ordering::Relaxed),
        attempts
    );
}
#[test]
fn acquisition_generated_identity_work_is_bounded_deleted_names_pruned_and_inplace_replacement_found()
 {
    let temp = tempfile::tempdir().unwrap();
    let d = temp.path().canonicalize().unwrap();
    let mut files = Files {
        image_directory: d.to_string_lossy().into_owned(),
        ..Default::default()
    };
    for i in 0..100 {
        let path = d.join(format!("output_{i:03}.dat"));
        fs::write(&path, b"generated").unwrap();
        files.output_written(&path);
    }
    files.identity_reads.set(0);
    assert!(files.scan().unwrap().is_empty());
    assert_eq!(files.identity_reads.get(), GENERATED_PROBES);
    for i in 0..10 {
        fs::remove_file(d.join(format!("output_{i:03}.dat"))).unwrap();
    }
    let replacement = d.join("output_099.dat");
    #[cfg(unix)]
    let inode = crate::image::FileIdentity::read(&replacement)
        .unwrap()
        .inode();
    let old_stamp = files.stamp(&replacement).unwrap();
    fs::write(&replacement, b"new image").unwrap();
    fs::File::options()
        .write(true)
        .open(&replacement)
        .unwrap()
        .set_times(fs::FileTimes::new().set_modified(old_stamp.1 + Duration::from_secs(1)))
        .unwrap();
    assert_eq!(files.stamp(&replacement).unwrap().0, old_stamp.0);
    #[cfg(unix)]
    assert_eq!(
        crate::image::FileIdentity::read(&replacement)
            .unwrap()
            .inode(),
        inode
    );
    let mut found = false;
    // Every retained identity is verified within ceil(N/budget) directory polls.
    for _ in 0..100usize.div_ceil(GENERATED_PROBES) {
        files.identity_reads.set(0);
        found |= files.scan().unwrap().contains(&replacement);
        assert!(files.identity_reads.get() <= GENERATED_PROBES);
    }
    assert!(found);
    assert_eq!(files.generated.len(), 90);
}
#[test]
fn acquisition_autosave_checks_replaced_generated_identity_before_rotating_scan() {
    let temp = tempfile::tempdir().unwrap();
    let mut s = prepared(temp.path());
    call(&mut s, "integration_settings", json!({"formats":[".dat"]}));
    call(&mut s, "integration_autocreate", json!({"enabled":true}));
    s.auto_save().unwrap();
    let target = temp.path().join("baseline.dat");
    fs::write(&target, b"new detector source").unwrap();
    assert!(
        s.auto_save()
            .unwrap_err()
            .contains("replace the detector source")
    );
    assert_eq!(fs::read(&target).unwrap(), b"new detector source");
    // A deleted generated file is safe to recreate, even before another scan.
    fs::remove_file(&target).unwrap();
    s.auto_save().unwrap();
    assert!(target.is_file());
}
#[test]
fn acquisition_old_retry_checkpoints_reclassify_and_never_override_failed_sources() {
    let temp = tempfile::tempdir().unwrap();
    let d = temp.path().canonicalize().unwrap();
    let path = d.join("broken.npy");
    fs::write(&path, b"corrupt").unwrap();
    let mut files = Files {
        image_directory: d.to_string_lossy().into_owned(),
        ..Default::default()
    };
    files.baseline().unwrap();
    let stamp = files.stamp(&path).unwrap();
    let mut value = serde_json::to_value(&files).unwrap();
    value["retry"] = json!({path.to_str().unwrap():{"stamp":stamp,"reason":"WaitingSource","message":"old wait"}});
    let mut restored: Files = serde_json::from_value(value.clone()).unwrap();
    assert!(restored.retry[&path].dependencies.is_empty());
    restored.poll().unwrap();
    assert_eq!(restored.queue.len(), 1);
    value["failed"] = json!({path.to_str().unwrap():stamp});
    let mut restored: Files = serde_json::from_value(value).unwrap();
    restored.poll().unwrap();
    assert!(restored.queue.is_empty());
    assert!(restored.retry.is_empty());
}

#[test]
fn acquisition_missing_vds_companion_recovers_without_master_change() {
    let temp = tempfile::tempdir().unwrap();
    let d = temp.path().join("incoming");
    let mut s = prepared(&d);
    let data = temp.path().join("pixels.h5");
    let master = d.join("virtual.h5");
    let file = hdf5::File::create(&master).unwrap();
    file.new_dataset::<u16>()
        .shape((1, 24, 32))
        .virtual_map(
            data.to_str().unwrap(),
            "/images",
            (1, 24, 32),
            (.., .., ..),
            (1, 24, 32),
            (.., .., ..),
        )
        .create("counts")
        .unwrap();
    drop(file);
    let original = fs::read(&master).unwrap();
    poll(&mut s);
    poll(&mut s);
    assert_eq!(s.files.retry.len(), 1);
    let attempts = s
        .files
        .decode_attempts
        .load(std::sync::atomic::Ordering::Relaxed);
    for _ in 0..3 {
        assert!(poll(&mut s).result.get("state").is_none());
    }
    assert_eq!(
        s.files
            .decode_attempts
            .load(std::sync::atomic::Ordering::Relaxed),
        attempts
    );
    let file = hdf5::File::create(&data).unwrap();
    file.new_dataset::<u16>()
        .shape((1, 24, 32))
        .create("images")
        .unwrap()
        .write_raw(&vec![42u16; 768])
        .unwrap();
    drop(file);
    polls_until(&mut s, |s| s.files.retry.is_empty());
    assert_eq!(fs::read(&master).unwrap(), original);
    assert_eq!(
        s.image.as_ref().unwrap().path,
        master.canonicalize().unwrap()
    );
}
#[test]
fn acquisition_declared_dependency_watch_respects_selection_policy_and_cycles() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path().join("selected.h5");
    let missing = temp.path().join("absent.h5");
    let file = hdf5::File::create(&path).unwrap();
    file.new_dataset::<u16>()
        .shape((24, 32))
        .create("counts")
        .unwrap();
    file.link_external(missing.to_str().unwrap(), "/images", "missing")
        .unwrap();
    file.link_hard("/", "cycle").unwrap();
    file.link_soft("/cycle2", "cycle1").unwrap();
    file.link_soft("/cycle1", "cycle2").unwrap();
    drop(file);
    assert_eq!(
        sources::unavailable(&path, &json!({}))
            .keys()
            .collect::<Vec<_>>(),
        vec![&missing]
    );
    assert!(sources::unavailable(&path, &json!({"dataset":"counts"})).is_empty());
    assert!(sources::unavailable(&path, &json!({"follow_external_links":false})).is_empty());
    assert!(sources::unavailable(&path, &json!({"dataset":"/cycle1"})).is_empty());
}

#[test]
fn acquisition_selected_external_dataset_and_group_ancestors_watch_the_declared_companion() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path().join("selected.h5");
    let data = temp.path().join("companion.h5");
    let file = hdf5::File::create(&path).unwrap();
    file.create_group("entry/data").unwrap();
    file.link_external(data.to_str().unwrap(), "/images", "entry/data/data_000001")
        .unwrap();
    file.link_external(data.to_str().unwrap(), "/", "source_group")
        .unwrap();
    file.link_external("unrelated.h5", "/images", "unrelated")
        .unwrap();
    drop(file);
    hdf5::File::open_rw(&path)
        .unwrap()
        .link_soft("/entry/data/data_000001", "selected")
        .unwrap();
    hdf5::File::open_rw(&path)
        .unwrap()
        .link_soft("/source_group", "selected_group")
        .unwrap();
    for selected in [
        "/entry/data/data_000001",
        "/source_group/images",
        "/selected",
        "/selected_group/images",
    ] {
        let missing = sources::unavailable(&path, &json!({"dataset":selected}));
        assert_eq!(
            missing.keys().collect::<Vec<_>>(),
            vec![&data],
            "{selected}"
        );
    }
}

#[test]
fn acquisition_declared_binding_matches_canonical_subordinate_owner() {
    let temp = tempfile::tempdir().unwrap();
    let incoming = temp.path().join("incoming");
    fs::create_dir(&incoming).unwrap();
    let nested = temp.path().join("nested.h5");
    let data = temp.path().join("chosen.raw");
    let file = hdf5::File::create(&nested).unwrap();
    file.new_dataset::<u16>()
        .shape((24, 32))
        .external("stored.raw", 0, 1536)
        .create("images")
        .unwrap();
    drop(file);
    let master = incoming.join("master.h5");
    let file = hdf5::File::create(&master).unwrap();
    file.link_external("../nested.h5", "/images", "counts")
        .unwrap();
    drop(file);
    let settings = json!({"dataset":"/counts","hdf5_bindings":[{"owner":nested.canonicalize().unwrap(), "stored_filename":"stored.raw", "actual_file":data}]});
    assert_eq!(
        sources::unavailable(&master, &settings)
            .keys()
            .collect::<Vec<_>>(),
        vec![&data]
    );
}

#[test]
fn acquisition_availability_inspection_caps_vds_mapping_count_before_reading_metadata() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path().join("excessive.h5");
    let file = hdf5::File::create(&path).unwrap();
    let mut builder = file.new_dataset::<u16>().shape((129, 1, 1));
    for i in 0..129 {
        builder = builder.virtual_map(
            format!("missing_{i}.h5"),
            "/images",
            (1, 1, 1),
            (.., .., ..),
            (129, 1, 1),
            (i..i + 1, .., ..),
        );
    }
    builder.create("counts").unwrap();
    drop(file);
    assert!(sources::unavailable(&path, &json!({})).is_empty());
}

#[test]
fn acquisition_soft_alias_keeps_literal_hdf5_dotdot_group_names() {
    let temp = tempfile::tempdir().unwrap();
    let master = temp.path().join("literal-components.h5");
    let missing = temp.path().join("missing.h5");
    let file = hdf5::File::create(&master).unwrap();
    let group = file.create_group("a/..").unwrap();
    group
        .link_external(missing.to_str().unwrap(), "/images", "external")
        .unwrap();
    file.link_soft("/a/../external", "selected").unwrap();
    drop(group);
    drop(file);
    assert_eq!(
        sources::unavailable(&master, &json!({"dataset":"/selected"}))
            .keys()
            .collect::<Vec<_>>(),
        vec![&missing],
    );
}
