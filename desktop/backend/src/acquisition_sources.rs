//! Availability watches for explicitly declared HDF5 storage only. This never
//! admits pixels, chooses a dataset, or substitutes filenames for the reader.
use crate::image::FileIdentity;
use serde_json::Value;
use std::{
    collections::{BTreeMap, BTreeSet},
    ffi::CString,
    path::{Path, PathBuf},
};

// Supplied by the existing HDF5 dependency (hid_t=int64_t, herr_t=C int).
unsafe extern "C" {
    fn H5Pget_external_count(properties: i64) -> i32;
    fn H5Pget_virtual_count(properties: i64, count: *mut usize) -> i32;
    fn H5Pget_virtual_filename(
        properties: i64,
        index: usize,
        text: *mut std::ffi::c_char,
        bytes: usize,
    ) -> isize;
    fn H5Pget_virtual_dsetname(
        properties: i64,
        index: usize,
        text: *mut std::ffi::c_char,
        bytes: usize,
    ) -> isize;
    fn H5Lget_val(
        group: i64,
        name: *const std::ffi::c_char,
        value: *mut std::ffi::c_void,
        size: usize,
        properties: i64,
    ) -> i32;
}
const MAX_OBJECTS: usize = 4096;
const MAX_FILES: usize = 128;
const MAX_DEPTH: usize = 64;
const MAX_LINK_BYTES: usize = 128 * 1024 + 3;

type VirtualText = unsafe extern "C" fn(i64, usize, *mut std::ffi::c_char, usize) -> isize;
fn virtual_text(properties: i64, index: usize, get: VirtualText) -> Option<String> {
    hdf5::sync::sync(|| {
        // SAFETY: the borrowed property list stays live through both calls;
        // null/zero queries only its required string length. No selection APIs.
        let length = unsafe { get(properties, index, std::ptr::null_mut(), 0) };
        if !(1..=64 * 1024).contains(&length) {
            return None;
        }
        let mut bytes = vec![0; length as usize + 1];
        // SAFETY: the allocation includes the NUL terminator and its length is
        // passed exactly. A changed/oversize length is rejected after the call.
        let actual = unsafe { get(properties, index, bytes.as_mut_ptr().cast(), bytes.len()) };
        if actual != length || bytes[length as usize] != 0 {
            return None;
        }
        String::from_utf8(bytes[..length as usize].to_vec()).ok()
    })
}
fn virtual_sources(properties: &hdf5::plist::DatasetCreate) -> Option<Vec<(String, String)>> {
    let mut count = 0;
    // SAFETY: live property list and writable native size_t under the HDF5 lock.
    let status = hdf5::sync::sync(|| unsafe { H5Pget_virtual_count(properties.id(), &mut count) });
    if status < 0 || count > MAX_FILES {
        return None;
    }
    (0..count)
        .map(|index| {
            Some((
                virtual_text(properties.id(), index, H5Pget_virtual_filename)?,
                virtual_text(properties.id(), index, H5Pget_virtual_dsetname)?,
            ))
        })
        .collect()
}
fn link_value(group: &hdf5::Group, name: &str) -> Option<Vec<u8>> {
    let name = CString::new(name).ok()?;
    let mut bytes = vec![0xff; MAX_LINK_BYTES];
    // SAFETY: the live group and NUL-terminated name remain valid, the bounded
    // buffer is writable, and all raw HDF5 calls hold its shared mutex.
    let status = hdf5::sync::sync(|| unsafe {
        H5Lget_val(
            group.id(),
            name.as_ptr(),
            bytes.as_mut_ptr().cast(),
            bytes.len(),
            0,
        )
    });
    (status >= 0).then_some(bytes)
}
fn external_target(group: &hdf5::Group, name: &str) -> Option<(String, String)> {
    let bytes = link_value(group, name)?;
    if bytes[0] != 0 {
        return None;
    }
    // Version-0 external links contain two NUL-terminated UTF-8 strings. Bound
    // both scans in Rust, including malformed/truncated native link values.
    let first = bytes[1..].iter().position(|&v| v == 0)? + 1;
    let last = bytes[first + 1..].iter().position(|&v| v == 0)? + first + 1;
    let filename = std::str::from_utf8(&bytes[1..first]).ok()?;
    let dataset = std::str::from_utf8(&bytes[first + 1..last]).ok()?;
    (!filename.is_empty() && !dataset.is_empty()).then(|| (filename.into(), dataset.into()))
}
fn target_path(parent: &str, target: &str, suffix: &str) -> String {
    let path = if target.starts_with('/') {
        format!("{target}{suffix}")
    } else {
        format!("{}/{target}{suffix}", parent.trim_end_matches('/'))
    };
    let mut parts = vec![];
    for part in path.split('/') {
        match part {
            "" | "." => {}
            ".." => {
                parts.pop();
            }
            part => parts.push(part),
        }
    }
    format!("/{}", parts.join("/"))
}
fn declared_path(owner: &Path, name: &str, settings: &Value, printf: bool) -> Option<PathBuf> {
    let physical_owner = owner.canonicalize().unwrap_or_else(|_| owner.to_path_buf());
    if let Some(bindings) = settings["hdf5_bindings"].as_array() {
        for binding in bindings {
            if binding["stored_filename"] == name
                && binding["owner"].as_str().is_some_and(|p| {
                    Path::new(p).canonicalize().ok().as_ref() == Some(&physical_owner)
                })
            {
                return binding["actual_file"].as_str().map(PathBuf::from);
            }
        }
    }
    if name == "." {
        return Some(owner.into());
    }
    // A printf pattern needs an explicit finite caller contract, not a wait for
    // a file literally named with a wildcard. Never guess that contract here.
    if printf && name.contains('%') {
        return None;
    }
    let path = Path::new(name);
    Some(if path.is_absolute() {
        path.into()
    } else {
        owner.parent()?.join(path)
    })
}

pub(super) fn unavailable(
    path: &Path,
    settings: &Value,
) -> BTreeMap<PathBuf, Option<FileIdentity>> {
    let mut missing = BTreeMap::new();
    let Ok(root) = path.canonicalize() else {
        return missing;
    };
    let Ok(file) = hdf5::File::open(&root) else {
        return missing;
    };
    let selection = settings["dataset"]
        .as_str()
        .filter(|path| *path != "/")
        .map(|path| format!("/{}", path.trim_start_matches('/')));
    let mut files = BTreeMap::from([(root.clone(), file)]);
    let mut stack = vec![(root, "/".to_owned(), false, 0usize, selection)];
    let mut seen = BTreeSet::new();
    let mut visits = 0;
    while let Some((owner, object, declared, depth, selection)) = stack.pop() {
        visits += 1;
        if depth >= MAX_DEPTH || visits > MAX_OBJECTS || files.len() > MAX_FILES {
            break;
        }
        if !files.contains_key(&owner) {
            match hdf5::File::open(&owner) {
                Ok(file) => {
                    files.insert(owner.clone(), file);
                }
                Err(_) => {
                    missing.insert(owner.clone(), FileIdentity::read(&owner).ok());
                    continue;
                }
            }
        }
        let file = &files[&owner];
        let Ok(info) = file.loc_info_by_name(&object) else {
            if declared {
                missing.insert(owner.clone(), FileIdentity::read(&owner).ok());
            }
            continue;
        };
        let selection = selection.filter(|selected| selected != &object);
        if !seen.insert((
            owner.clone(),
            format!("{:?}", info.token),
            selection.clone(),
        )) {
            continue;
        }
        if info.loc_type == hdf5::LocationType::Group {
            let Ok(group) = file.group(&object) else {
                continue;
            };
            let mut links = vec![];
            let _ = group.iter_visit_default(|name, info| {
                if links.len() >= MAX_OBJECTS.saturating_sub(visits + stack.len()) {
                    return Err("Acquisition dependency traversal limit".into());
                }
                links.push((name.to_owned(), info));
                Ok(())
            });
            let mut matched = false;
            for (name, link) in links {
                let child = format!("{}/{name}", object.trim_end_matches('/'));
                if selection.as_ref().is_some_and(|selected| {
                    selected != &child && !selected.starts_with(&format!("{child}/"))
                }) {
                    continue;
                }
                matched = true;
                if link.link_type == hdf5::LinkType::External {
                    if settings["follow_external_links"] == false {
                        continue;
                    }
                    if let Some((filename, target)) = external_target(&group, &name)
                        && let Some(path) = declared_path(&owner, &filename, &Value::Null, false)
                    {
                        let suffix = selection
                            .as_ref()
                            .and_then(|selected| selected.strip_prefix(&child))
                            .unwrap_or("");
                        let selected = target_path("/", &target, suffix);
                        stack.push((path, "/".into(), true, depth + 1, Some(selected)));
                    }
                } else if link.link_type == hdf5::LinkType::Soft {
                    if let Some(bytes) = link_value(&group, &name)
                        && let Some(end) = bytes.iter().position(|&v| v == 0)
                        && let Ok(target) = std::str::from_utf8(&bytes[..end])
                    {
                        let suffix = selection
                            .as_ref()
                            .and_then(|selected| selected.strip_prefix(&child))
                            .unwrap_or("");
                        stack.push((
                            owner.clone(),
                            "/".into(),
                            declared,
                            depth + 1,
                            Some(target_path(&object, target, suffix)),
                        ));
                    }
                } else if link.link_type == hdf5::LinkType::Hard {
                    stack.push((owner.clone(), child, declared, depth + 1, selection.clone()));
                }
            }
            if !matched && declared && selection.is_some() {
                missing.insert(owner.clone(), FileIdentity::read(&owner).ok());
            }
        } else if info.loc_type == hdf5::LocationType::Dataset {
            let Ok(dataset) = file.dataset(&object) else {
                continue;
            };
            if !matches!(dataset.ndim(), 2 | 3) {
                continue;
            }
            let Ok(properties) = dataset.dcpl() else {
                continue;
            };
            // The convenience API eagerly collects every external declaration.
            // Bound its native count first; off_t stays with its portable binding.
            let external_count =
                hdf5::sync::sync(|| unsafe { H5Pget_external_count(properties.id()) });
            if (0..=MAX_FILES as i32).contains(&external_count)
                && let Ok(external) = properties.get_external()
            {
                let mut remaining = dataset
                    .size()
                    .saturating_mul(dataset.dtype().map_or(0, |t| t.size()));
                for source in external.into_iter().take(MAX_FILES) {
                    let bytes = if source.size == 0 {
                        remaining
                    } else {
                        source.size
                    };
                    remaining = remaining.saturating_sub(bytes);
                    if let Some(path) = declared_path(&owner, &source.name, settings, false)
                        && std::fs::metadata(&path).ok().is_none_or(|m| {
                            !m.is_file() || m.len() < source.offset.saturating_add(bytes) as u64
                        })
                    {
                        missing.insert(path.clone(), FileIdentity::read(&path).ok());
                    }
                }
            }
            if dataset.layout() == hdf5::dataset::Layout::Virtual
                && let Some(mappings) = virtual_sources(&properties)
            {
                for (filename, source_dataset) in mappings {
                    if let Some(path) = declared_path(&owner, &filename, settings, true) {
                        stack.push((
                            path,
                            "/".into(),
                            true,
                            depth + 1,
                            Some(format!("/{}", source_dataset.trim_start_matches('/'))),
                        ));
                    }
                }
            }
        }
        if missing.len() >= MAX_FILES {
            break;
        }
    }
    missing
}
