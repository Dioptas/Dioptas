use super::*;
use hdf5::{ObjectReference, ObjectReference1};
use std::collections::BTreeSet;

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../..")
}
fn call(s: &mut Session, action: &str, payload: Value) -> Reply {
    let reply = s.invoke(&crate::protocol::Request {
        id: 1,
        action: action.into(),
        payload,
        cached_buffers: vec![],
    });
    assert_eq!(reply.result["ok"], true, "{action}: {}", reply.result);
    reply
}
fn image(path: &Path, offset: f64) -> Vec<f64> {
    let values: Vec<_> = (0..768)
        .map(|i| offset + (i as f64 + 1.).sin().abs())
        .collect();
    let file = hdf5::File::create(path).unwrap();
    file.new_dataset::<f64>()
        .shape([24, 32])
        .create("data")
        .unwrap()
        .write_raw(&values)
        .unwrap();
    values
}
fn pool_names(file: &hdf5::File, name: &str) -> BTreeSet<String> {
    file.group(name)
        .unwrap()
        .member_names()
        .unwrap()
        .into_iter()
        .collect()
}
fn reference_bytes(reference: &ObjectReference1) -> Vec<u8> {
    // ObjectReference1 is a transparent HDF5 hobj_ref_t; read-only comparison
    // verifies that the compatibility path does not rewrite extension addresses.
    unsafe {
        std::slice::from_raw_parts(
            reference.ptr().cast::<u8>(),
            std::mem::size_of::<ObjectReference1>(),
        )
        .to_vec()
    }
}
#[test]
fn unchanged_embedded_batch_reopen_save_cycles_are_bounded_and_exact() {
    let temp = tempfile::tempdir().unwrap();
    let project = temp.path().join("batch.dio");
    let mut session = Session::new(root());
    call(
        &mut session,
        "batch_open",
        json!({"path":root().join("desktop/backend/tests/fixtures/batch_background_input.h5")}),
    );
    let data = session.batch.as_ref().unwrap().data.clone();
    let sigma = session.batch.as_ref().unwrap().sigma.clone();
    session.save_native_project(&project).unwrap();
    let first = std::fs::metadata(&project).unwrap().len();
    let mut sizes = vec![first];
    for _ in 0..8 {
        session.open_native_project(&project).unwrap();
        assert_eq!(session.batch.as_ref().unwrap().data, data);
        assert_eq!(session.batch.as_ref().unwrap().sigma, sigma);
        session.save_native_project(&project).unwrap();
        sizes.push(std::fs::metadata(&project).unwrap().len());
    }
    assert!(
        sizes.iter().all(|size| *size <= first + first / 10 + 4096),
        "{sizes:?}"
    );
}
#[test]
fn changed_images_and_masks_prune_only_unreachable_owned_arrays() {
    let temp = tempfile::tempdir().unwrap();
    let source = temp.path().join("image.h5");
    let project = temp.path().join("image.dio");
    let mut session = Session::new(root());
    let mut sizes = vec![];
    for i in 0..9 {
        image(&source, i as f64);
        call(&mut session, "open_image", json!({"path":source}));
        let expected = session.image.as_ref().unwrap().source_values.clone();
        Arc::make_mut(&mut session.mask)[i] = 1;
        let mask = session.mask.clone();
        session.save_native_project(&project).unwrap();
        {
            let file = hdf5::File::open(&project).unwrap();
            assert_eq!(pool_names(&file, "cache").len(), 1);
            assert_eq!(pool_names(&file, "payloads").len(), 1);
            sizes.push(file.size());
        }
        session.open_native_project(&project).unwrap();
        assert_eq!(
            session.image.as_ref().unwrap().source_values.as_ref(),
            expected.as_ref()
        );
        assert_eq!(session.mask, mask);
    }
    assert!(
        sizes.iter().max().unwrap() - sizes.iter().min().unwrap() < 8192,
        "{sizes:?}"
    );
}
#[test]
fn compacted_detector_cache_retains_exact_nonfinite_and_signed_zero_bits() {
    let temp = tempfile::tempdir().unwrap();
    let source = temp.path().join("nonfinite.h5");
    let target = temp.path().join("nonfinite.dio");
    let mut values = image(&source, 0.);
    values[0] = f64::from_bits(0x7ff8_0000_0000_0042);
    values[3] = f64::NEG_INFINITY;
    values[7] = -0.0;
    {
        let file = hdf5::File::open_rw(&source).unwrap();
        file.dataset("data").unwrap().write_raw(&values).unwrap();
    }
    let mut session = Session::new(root());
    call(&mut session, "open_image", json!({"path":source}));
    let expected: Vec<_> = session
        .image
        .as_ref()
        .unwrap()
        .source_values
        .iter()
        .map(|x| x.to_bits())
        .collect();
    session.save_native_project(&target).unwrap();
    std::fs::remove_file(source).unwrap();
    session.open_native_project(&target).unwrap();
    let actual: Vec<_> = session
        .image
        .as_ref()
        .unwrap()
        .source_values
        .iter()
        .map(|x| x.to_bits())
        .collect();
    assert_eq!(actual, expected);
}
#[test]
fn extensions_root_attributes_aliases_and_indirect_hash_references_survive_compaction() {
    let temp = tempfile::tempdir().unwrap();
    let source = temp.path().join("image.h5");
    let project = temp.path().join("extensions.dio");
    image(&source, 0.);
    let mut session = Session::new(root());
    call(&mut session, "open_image", json!({"path":source}));
    session.save_native_project(&project).unwrap();
    let (json_key, attr_key, text_key, soft_key, fixed_key, stale_key);
    {
        let file = hdf5::File::open_rw(&project).unwrap();
        let cache = file.group("cache").unwrap();
        json_key = put(&cache, &[2], &[1., 2.])
            .unwrap()
            .as_str()
            .unwrap()
            .to_owned();
        attr_key = put(&cache, &[2], &[3., 4.])
            .unwrap()
            .as_str()
            .unwrap()
            .to_owned();
        text_key = put(&cache, &[2], &[5., 6.])
            .unwrap()
            .as_str()
            .unwrap()
            .to_owned();
        soft_key = put(&cache, &[2], &[7., 8.])
            .unwrap()
            .as_str()
            .unwrap()
            .to_owned();
        fixed_key = put(&cache, &[2], &[11., 12.])
            .unwrap()
            .as_str()
            .unwrap()
            .to_owned();
        let value = hdf5::types::FixedAscii::<64>::from_ascii(&fixed_key).unwrap();
        file.new_attr::<hdf5::types::FixedAscii<64>>()
            .shape(())
            .create("fixed_hash")
            .unwrap()
            .write_scalar(&value)
            .unwrap();
        file.new_attr::<hdf5::types::VarLenArray<i32>>()
            .shape(())
            .create("variable_numbers")
            .unwrap()
            .write_scalar(&hdf5::types::VarLenArray::from_slice(&[-4, 8, 16]))
            .unwrap();
        stale_key = put(&cache, &[2], &[9., 10.])
            .unwrap()
            .as_str()
            .unwrap()
            .to_owned();
        let mut document = read_json_dataset(&file, "state").unwrap();
        document["beamline_extension"] = json!({"cache_reference":json_key,"note":"unchanged"});
        write_json_dataset(&file, "state", &document).unwrap();
        write_text_attr(&file, "beamline_reference", &format!("cache/{attr_key}")).unwrap();
        file.new_attr::<i64>()
            .shape([3])
            .create("beamline_numbers")
            .unwrap()
            .write_raw(&[4, -8, 15])
            .unwrap();
        let group = file.create_group("configurations/0/beamline").unwrap();
        group
            .new_dataset::<u16>()
            .shape([3])
            .create("counts")
            .unwrap()
            .write_raw(&[5, 10, 20])
            .unwrap();
        file.link_hard("/configurations/0/beamline/counts", "/counts_alias")
            .unwrap();
        write_json_dataset(&group, "reference", &json!({"array":text_key})).unwrap();
        file.group("configurations")
            .unwrap()
            .new_attr::<i32>()
            .shape(())
            .create("extension_container")
            .unwrap()
            .write_scalar(&12)
            .unwrap();
        file.create_group("configurations/not_a_native_configuration")
            .unwrap();
        file.link_soft(&format!("/cache/{soft_key}"), "/legacy_soft_array")
            .unwrap();
        file.link_soft("/absent/target", "/dangling_soft_link")
            .unwrap();
        file.link_external("missing_extension.h5", "/data", "/external_link")
            .unwrap();
    }
    session.open_native_project(&project).unwrap();
    // Reindexing ordinary configurations must preserve the opaque group and
    // its cross-root alias, not deep-copy it away from the alias.
    call(
        &mut session,
        "configuration",
        json!({"operation":"duplicate"}),
    );
    session.save_native_project(&project).unwrap();
    let file = hdf5::File::open(&project).unwrap();
    let document = read_json_dataset(&file, "state").unwrap();
    assert_eq!(document["beamline_extension"]["note"], "unchanged");
    let keys = pool_names(&file, "cache");
    for key in [json_key, attr_key, text_key, soft_key, fixed_key] {
        assert!(keys.contains(&key), "missing {key}");
    }
    assert!(!keys.contains(&stale_key));
    assert_eq!(
        file.attr("beamline_numbers")
            .unwrap()
            .read_raw::<i64>()
            .unwrap(),
        vec![4, -8, 15]
    );
    assert_eq!(
        file.attr("variable_numbers")
            .unwrap()
            .read_scalar::<hdf5::types::VarLenArray<i32>>()
            .unwrap()
            .as_slice(),
        &[-4, 8, 16]
    );
    assert_eq!(
        file.loc_info_by_name("counts_alias").unwrap().token,
        file.loc_info_by_name("configurations/0/beamline/counts")
            .unwrap()
            .token
    );
    assert_ne!(
        file.loc_info_by_name("counts_alias").unwrap().token,
        file.loc_info_by_name("configurations/1/beamline/counts")
            .unwrap()
            .token
    );
    assert_eq!(
        file.dataset("legacy_soft_array")
            .unwrap()
            .read_raw::<f64>()
            .unwrap(),
        vec![7., 8.]
    );
    assert_eq!(
        file.group("configurations")
            .unwrap()
            .attr("extension_container")
            .unwrap()
            .read_scalar::<i32>()
            .unwrap(),
        12
    );
    assert!(file.link_exists("configurations/not_a_native_configuration"));
    let links = file
        .links(hdf5::IndexType::Name, hdf5::IterationOrder::Increasing)
        .unwrap();
    assert_eq!(
        links
            .iter()
            .find(|(name, _)| name == "dangling_soft_link")
            .unwrap()
            .1
            .link_type,
        hdf5::LinkType::Soft
    );
    assert_eq!(
        links
            .iter()
            .find(|(name, _)| name == "external_link")
            .unwrap()
            .1
            .link_type,
        hdf5::LinkType::External
    );
}
#[test]
fn opaque_reference_extensions_keep_addresses_and_replaced_targets() {
    let temp = tempfile::tempdir().unwrap();
    let source = temp.path().join("image.h5");
    let project = temp.path().join("refs.dio");
    image(&source, 0.);
    let mut session = Session::new(root());
    call(&mut session, "open_image", json!({"path":source}));
    session.batch = Some(
        crate::series::Series::load_processed(
            &root().join("desktop/backend/tests/fixtures/batch_background_input.h5"),
        )
        .unwrap(),
    );
    let batch_data = session.batch.as_ref().unwrap().data.clone();
    session.save_native_project(&project).unwrap();
    let before;
    {
        let file = hdf5::File::open_rw(&project).unwrap();
        let reference = file
            .reference::<ObjectReference1>("/configurations/0")
            .unwrap();
        let batch_reference = file
            .reference::<ObjectReference1>("/configurations/0/native_batch/result/data")
            .unwrap();
        file.new_attr::<ObjectReference1>()
            .shape(())
            .create("batch_data_reference")
            .unwrap()
            .write_scalar(&batch_reference)
            .unwrap();
        before = reference_bytes(&reference);
        file.new_dataset::<ObjectReference1>()
            .shape([1])
            .create("opaque_reference")
            .unwrap()
            .write_raw(&[reference])
            .unwrap();
        let reference = file.reference::<ObjectReference1>("/").unwrap();
        file.new_attr::<ObjectReference1>()
            .shape(())
            .create("root_reference")
            .unwrap()
            .write_scalar(&reference)
            .unwrap();
    }
    session.open_native_project(&project).unwrap();
    Arc::make_mut(&mut session.mask)[0] = 1;
    session.save_native_project(&project).unwrap();
    let file = hdf5::File::open(&project).unwrap();
    let reference = file
        .dataset("opaque_reference")
        .unwrap()
        .read_raw::<ObjectReference1>()
        .unwrap()[0];
    assert_eq!(reference_bytes(&reference), before);
    let hdf5::ReferencedObject::Group(group) = reference.dereference(&file).unwrap() else {
        panic!("wrong reference")
    };
    assert_eq!(
        group.loc_info().unwrap().token,
        file.loc_info_by_name("configurations/0").unwrap().token
    );
    let reference = file
        .attr("root_reference")
        .unwrap()
        .read_scalar::<ObjectReference1>()
        .unwrap();
    let hdf5::ReferencedObject::Group(group) = reference.dereference(&file).unwrap() else {
        panic!("wrong root reference")
    };
    assert_eq!(
        group.loc_info().unwrap().token,
        file.loc_info().unwrap().token
    );
    let reference = file
        .attr("batch_data_reference")
        .unwrap()
        .read_scalar::<ObjectReference1>()
        .unwrap();
    let hdf5::ReferencedObject::Dataset(dataset) = reference.dereference(&file).unwrap() else {
        panic!("lost old Batch target");
    };
    assert_eq!(dataset.read_raw::<f64>().unwrap(), *batch_data);
    drop(dataset);
    drop(group);
    drop(file);
    session.open_native_project(&project).unwrap();
    call(
        &mut session,
        "configuration",
        json!({"operation":"duplicate"}),
    );
    let original = std::fs::read(&project).unwrap();
    assert!(session.save_native_project(&project).is_err());
    assert_eq!(std::fs::read(&project).unwrap(), original);
}
#[test]
fn a_hard_root_cycle_uses_the_lossless_bounded_compatibility_path() {
    let temp = tempfile::tempdir().unwrap();
    let project = temp.path().join("cycle.dio");
    let mut session = Session::new(root());
    session.save_native_project(&project).unwrap();
    {
        let file = hdf5::File::open_rw(&project).unwrap();
        file.link_hard("/", "root_alias").unwrap();
    }
    session.open_native_project(&project).unwrap();
    session.save_native_project(&project).unwrap();
    let file = hdf5::File::open(&project).unwrap();
    assert_eq!(
        file.loc_info().unwrap().token,
        file.loc_info_by_name("root_alias").unwrap().token
    );
}
#[cfg(unix)]
#[test]
fn save_as_uses_retained_handles_after_archive_path_is_unlinked() {
    let temp = tempfile::tempdir().unwrap();
    let source = temp.path().join("image.h5");
    let project = temp.path().join("original.dio");
    let saved = temp.path().join("saved.dio");
    image(&source, 0.);
    let mut session = Session::new(root());
    call(&mut session, "open_image", json!({"path":source}));
    let expected = session.image.as_ref().unwrap().source_values.clone();
    session.save_native_project(&project).unwrap();
    {
        let file = hdf5::File::open_rw(&project).unwrap();
        write_text_attr(&file, "beamline", "preserved").unwrap();
    }
    session.open_native_project(&project).unwrap();
    std::fs::remove_file(session.project.archive.as_ref().unwrap().snapshot.path()).unwrap();
    std::fs::remove_file(&project).unwrap();
    std::fs::remove_file(source).unwrap();
    session.save_native_project(&saved).unwrap();
    session.open_native_project(&saved).unwrap();
    assert_eq!(
        session.image.as_ref().unwrap().source_values.as_ref(),
        expected.as_ref()
    );
    assert_eq!(
        read_text_attr(&hdf5::File::open(&saved).unwrap(), "beamline")
            .unwrap()
            .as_deref(),
        Some("preserved")
    );
}
#[test]
fn publication_bound_and_late_cancellation_preserve_existing_destination_bytes() {
    let temp = tempfile::tempdir().unwrap();
    let target = temp.path().join("original.dio");
    std::fs::write(&target, b"existing project").unwrap();
    let staged = crate::output::StagedOutput::new(&target).unwrap();
    staged.as_file().set_len(32).unwrap();
    assert!(finish_project(staged, &target, &Control::default(), 16).is_err());
    assert_eq!(std::fs::read(&target).unwrap(), b"existing project");
    let staged = crate::output::StagedOutput::new(&target).unwrap();
    staged.as_file().set_len(32).unwrap();
    let control = Control::default();
    control.cancel();
    assert!(finish_project(staged, &target, &control, 64).is_err());
    assert_eq!(std::fs::read(&target).unwrap(), b"existing project");
}
