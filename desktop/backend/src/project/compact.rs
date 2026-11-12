//! Compact ordinary format-2 archives without interpreting extension objects.
//! Reference-bearing archives retain their object addresses in a bounded byte
//! copy instead: HDF5 object/region references cannot be blindly relocated.
use super::*;
use std::collections::BTreeSet;

// These APIs are supplied by the already linked HDF5 library. Keeping this
// adapter here avoids exposing raw HDF5 buffers to scientific/project owners.
// hid_t is the HDF5 ABI's int64_t; herr_t/htri_t are C int on every target.
unsafe extern "C" {
    fn H5Tdetect_class(dtype: i64, class: i32) -> i32;
    fn H5Aread(attribute: i64, dtype: i64, buffer: *mut std::ffi::c_void) -> i32;
    fn H5Awrite(attribute: i64, dtype: i64, buffer: *const std::ffi::c_void) -> i32;
    fn H5Dread(
        dataset: i64,
        dtype: i64,
        memory_space: i64,
        file_space: i64,
        properties: i64,
        buffer: *mut std::ffi::c_void,
    ) -> i32;
    fn H5Dvlen_reclaim(
        dtype: i64,
        space: i64,
        properties: i64,
        buffer: *mut std::ffi::c_void,
    ) -> i32;
}
fn has_references(dtype: &hdf5::Datatype) -> Result<bool, String> {
    // H5T_REFERENCE also detects references nested in compound/array/VLEN types.
    let result = hdf5::sync::sync(|| unsafe { H5Tdetect_class(dtype.id(), 7) });
    if result < 0 {
        Err("Cannot inspect an extension datatype safely.".into())
    } else {
        Ok(result > 0)
    }
}
struct Node {
    path: String,
    object: hdf5::Location,
}
fn token(object: &hdf5::Location) -> Result<String, String> {
    Ok(format!("{:?}", object.loc_info().native()?.token))
}
fn objects(file: &hdf5::File, control: &Control) -> Result<(Vec<Node>, bool, Vec<String>), String> {
    let root = file.as_location().native()?;
    let root_token = token(&root)?;
    let mut seen = BTreeSet::from([root_token.clone()]);
    let mut nodes = vec![Node {
        path: "/".into(),
        object: root,
    }];
    let mut groups = vec![file.group("/").native()?];
    let mut root_cycle = false;
    let mut soft_targets = vec![];
    while let Some(group) = groups.pop() {
        control.check()?;
        for (name, link) in group
            .links(hdf5::IndexType::Name, hdf5::IterationOrder::Increasing)
            .native()?
        {
            if link.link_type != hdf5::LinkType::Hard {
                if link.link_type == hdf5::LinkType::Soft
                    && let Ok(info) = group.loc_info_by_name(&name)
                {
                    soft_targets.push(format!("{:?}", info.token));
                }
                continue; // H5Ocopy preserves symbolic/external links verbatim.
            }
            let info = group.loc_info_by_name(&name).native()?;
            let key = format!("{:?}", info.token);
            root_cycle |= key == root_token;
            if !seen.insert(key) {
                continue;
            }
            let path = format!("{}/{}", group.name().trim_end_matches('/'), name);
            let object = file.open_by_token(info.token).native()?;
            if info.loc_type == hdf5::LocationType::Group {
                groups.push(object.as_group().native()?);
            }
            nodes.push(Node { path, object });
        }
    }
    Ok((nodes, root_cycle, soft_targets))
}
/// True means a fresh object copy can preserve every extension's meaning.
/// User blocks, external storage, references and root cycles use the conservative
/// byte-preserving path, not a partial copy or an address/reference remapper.
pub(super) fn can_compact(file: &hdf5::File, control: &Control) -> Result<bool, String> {
    if file.fcpl().native()?.userblock() != 0 {
        return Ok(false);
    }
    let (nodes, root_cycle, _) = objects(file, control)?;
    if root_cycle {
        return Ok(false);
    }
    for node in nodes {
        control.check()?;
        for name in node.object.attr_names().native()? {
            if has_references(&node.object.attr(&name).native()?.dtype().native()?)? {
                return Ok(false);
            }
        }
        match node.object.loc_type().native()? {
            hdf5::LocationType::Dataset => {
                let dataset = node.object.as_dataset().native()?;
                if has_references(&dataset.dtype().native()?)? {
                    return Ok(false);
                }
                let dcpl = dataset.dcpl().native()?;
                if !dcpl.get_external().native()?.is_empty()
                    || dcpl.layout() == hdf5::dataset::Layout::Virtual
                {
                    return Ok(false);
                }
            }
            hdf5::LocationType::NamedDatatype
                if has_references(&node.object.as_datatype().native()?)? =>
            {
                return Ok(false);
            }
            _ => {}
        }
    }
    Ok(true)
}
/// Retain every old object in opaque archives, including objects that native
/// writers replace. Existing extension reference bytes therefore stay valid.
/// This compatibility path can grow; publication still enforces the file bound.
pub(super) fn retain_opaque_objects(file: &hdf5::File, control: &Control) -> Result<(), String> {
    let (nodes, _, _) = objects(file, control)?;
    let keep = ensure_group(file, "__native_opaque_objects")?;
    let mut retained = BTreeSet::new();
    for name in keep.member_names().native()? {
        retained.insert(format!(
            "{:?}",
            keep.loc_info_by_name(&name).native()?.token
        ));
    }
    let mut index = keep.len();
    for node in nodes.into_iter().filter(|n| n.path != "/") {
        control.check()?;
        if node.path == keep.name() || !retained.insert(token(&node.object)?) {
            continue;
        }
        while keep.link_exists(&index.to_string()) {
            index += 1;
        }
        keep.link_hard(&node.path, &index.to_string()).native()?;
        index += 1;
    }
    Ok(())
}
fn collect_hashes(bytes: &[u8], candidates: &BTreeSet<String>, references: &mut BTreeSet<String>) {
    for run in bytes
        .split(|c| !c.is_ascii_hexdigit())
        .filter(|r| r.len() >= 64)
    {
        for window in run.windows(64) {
            // ASCII hexadecimal is always UTF-8. Only retain existing pool keys,
            // rather than allocating a key for every window in extension text.
            if let Ok(key) = std::str::from_utf8(window)
                && candidates.contains(key)
            {
                references.insert(key.into());
            }
        }
    }
}
fn json_hashes(value: &Value, candidates: &BTreeSet<String>, references: &mut BTreeSet<String>) {
    match value {
        Value::String(s) => collect_hashes(s.as_bytes(), candidates, references),
        Value::Array(items) => {
            for item in items {
                json_hashes(item, candidates, references);
            }
        }
        Value::Object(items) => {
            for item in items.values() {
                json_hashes(item, candidates, references);
            }
        }
        _ => {}
    }
}
/// Unknown string metadata is allowed to retain pool objects too. Compound/VLEN
/// extension text that cannot be inspected in bounded memory conservatively
/// retains the pools, rather than guessing that its references are absent.
fn text_hashes(
    container: &hdf5::Container,
    candidates: &BTreeSet<String>,
    references: &mut BTreeSet<String>,
) -> Result<bool, String> {
    use hdf5::types::{TypeDescriptor as T, VarLenAscii, VarLenUnicode};
    let dtype = container.dtype().native()?;
    let Ok(description) = dtype.to_descriptor() else {
        // Do not infer absence of references from an opaque extension type.
        return Ok(true);
    };
    let ascii = matches!(description, T::VarLenAscii | T::FixedAscii(_));
    let unicode = matches!(description, T::VarLenUnicode | T::FixedUnicode(_));
    if !ascii && !unicode {
        fn nested_text(t: &T) -> bool {
            match t {
                T::VarLenAscii | T::FixedAscii(_) | T::VarLenUnicode | T::FixedUnicode(_) => true,
                T::Compound(c) => c.fields.iter().any(|f| nested_text(&f.ty)),
                T::FixedArray(t, _) | T::VarLenArray(t) => nested_text(t),
                _ => false,
            }
        }
        return Ok(nested_text(&description));
    }
    if container.storage_size() > 64 * 1024 * 1024 || container.size() > 1_000_000 {
        return Ok(true);
    }
    if matches!(description, T::FixedAscii(_) | T::FixedUnicode(_)) {
        let Some(bytes) = dtype
            .size()
            .checked_mul(container.size())
            .filter(|n| *n <= 64 * 1024 * 1024)
        else {
            return Ok(true);
        };
        let mut buffer = vec![0_u8; bytes.max(1)];
        let read = hdf5::sync::sync(|| unsafe {
            if let Ok(attribute) = container.as_attr() {
                H5Aread(attribute.id(), dtype.id(), buffer.as_mut_ptr().cast())
            } else {
                H5Dread(
                    container.id(),
                    dtype.id(),
                    0,
                    0,
                    0,
                    buffer.as_mut_ptr().cast(),
                )
            }
        });
        if read < 0 {
            return Err("Cannot inspect a fixed-string extension safely.".into());
        }
        collect_hashes(&buffer[..bytes], candidates, references);
        return Ok(false);
    }
    if ascii {
        let Ok(values) = container.read_raw::<VarLenAscii>() else {
            return Ok(true);
        };
        for value in values {
            collect_hashes(value.as_bytes(), candidates, references);
        }
    } else {
        let Ok(values) = container.read_raw::<VarLenUnicode>() else {
            return Ok(true);
        };
        for value in values {
            collect_hashes(value.as_bytes(), candidates, references);
        }
    }
    Ok(false)
}
pub(super) fn prune_pools(
    file: &hdf5::File,
    document: &Value,
    control: &Control,
) -> Result<(), String> {
    let mut candidates = BTreeSet::new();
    let mut pools = vec![];
    for name in ["payloads", "cache"] {
        let group = file.group(name).native()?;
        // A hard alias to the entire pool is an opaque extension view of all
        // its members. Preserve that view, not just the known native fields.
        if group.loc_info().native()?.num_links > 1 {
            return Ok(());
        }
        for name in group.member_names().native()? {
            if name.len() == 64
                && name.bytes().all(|b| b.is_ascii_hexdigit())
                && let Ok(dataset) = group.dataset(&name)
                && dataset.dtype().native()?.is::<f64>()
            {
                candidates.insert(name.clone());
                pools.push((
                    group.clone(),
                    name,
                    format!("{:?}", dataset.loc_info().native()?.token),
                ));
            }
        }
    }
    let mut references = BTreeSet::new();
    json_hashes(document, &candidates, &mut references);
    let (nodes, _, soft_targets) = objects(file, control)?;
    // A soft alias to a pool (or its root ancestor) exposes the same complete
    // member view as a hard alias. Its group token is not a dataset token.
    for name in ["/", "/cache", "/payloads"] {
        let group = file.group(name).native()?;
        if soft_targets.contains(&token(&group)?) {
            return Ok(());
        }
    }
    for node in nodes {
        control.check()?;
        for name in node.object.attr_names().native()? {
            let attribute = node.object.attr(&name).native()?;
            if text_hashes(&attribute, &candidates, &mut references)? {
                return Ok(());
            }
        }
        if node.object.loc_type().native()? == hdf5::LocationType::Dataset {
            let dataset = node.object.as_dataset().native()?;
            if text_hashes(&dataset, &candidates, &mut references)? {
                return Ok(());
            }
        }
    }
    for (group, name, token) in pools {
        control.check()?;
        if !references.contains(&name) && !soft_targets.contains(&token) {
            group.unlink(&name).native()?;
        }
    }
    Ok(())
}
/// Transfer attributes within ONE file, so even unusual fixed/compound/VLEN
/// types keep their exact datatype and values. HDF5 owns any VLEN allocation;
/// it is reclaimed with the same datatype/dataspace on both success and error.
#[allow(deprecated)] // Preserve legacy HDF5 comments as well as attributes.
fn copy_root_attributes(source: &hdf5::Group, target: &hdf5::File) -> Result<(), String> {
    for name in source.attr_names().native()? {
        let attribute = source.attr(&name).native()?;
        let dtype = attribute.dtype().native()?;
        let space = attribute.space().native()?;
        let target_attribute = target
            .new_attr_builder()
            .empty_as(&dtype)
            .shape(space.extents().native()?)
            .create(name.as_str())
            .native()?;
        let bytes = dtype
            .size()
            .checked_mul(attribute.size())
            .ok_or("Project attribute dimensions overflow.")?;
        let mut buffer = Vec::<u64>::new();
        buffer
            .try_reserve_exact(bytes.div_ceil(8))
            .map_err(|e| e.to_string())?;
        buffer.resize(bytes.div_ceil(8).max(1), 0);
        hdf5::sync::sync(|| unsafe {
            let pointer = buffer.as_mut_ptr().cast();
            let read = H5Aread(attribute.id(), dtype.id(), pointer);
            // Failed HDF5 reads leave unspecified contents. Reclaim only a
            // successfully populated buffer, never potentially invalid pointers.
            if read < 0 {
                return Err(format!("Cannot read project root attribute {name}."));
            }
            let written = H5Awrite(target_attribute.id(), dtype.id(), pointer);
            let reclaimed = H5Dvlen_reclaim(dtype.id(), space.id(), 0, pointer);
            if written < 0 || reclaimed < 0 {
                Err(format!("Cannot preserve project root attribute {name}."))
            } else {
                Ok(())
            }
        })?;
    }
    if let Some(comment) = source.comment() {
        target.set_comment(&comment).native()?;
    }
    Ok(())
}
pub(super) fn write_fresh(
    source: &hdf5::File,
    target: &Path,
    control: &Control,
) -> Result<(), String> {
    control.check()?;
    let output = hdf5::File::create(target).native()?;
    let mut index = 0_u64;
    let name = loop {
        let name = format!("__native_compact_root_{index}");
        if !source.link_exists(&name) {
            break name;
        }
        index += 1;
    };
    // A single H5Ocopy preserves shared hard-link identity across extensions.
    // No reference-bearing datatype or root cycle reaches this path.
    source.copy_to(&output, &name).native()?;
    let copied = output.group(&name).native()?;
    copy_root_attributes(&copied, &output)?;
    for child in copied.member_names().native()? {
        control.check()?;
        output.relink(&format!("{name}/{child}"), &child).native()?;
    }
    output.unlink(&name).native()?;
    drop(copied);
    output.flush().native()?;
    control.check()?;
    Ok(())
}
