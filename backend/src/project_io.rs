//! Bounded HDF5 helpers for the existing format-2 state/array contract.
use super::*;
use sha2::{Digest, Sha256};
use std::{
    io::{Read, Seek, SeekFrom, Write},
    str::FromStr,
    sync::OnceLock,
};
pub(super) trait Native<T> {
    fn native(self) -> Result<T, String>;
}
impl<T> Native<T> for hdf5::Result<T> {
    fn native(self) -> Result<T, String> {
        self.map_err(|e| e.to_string())
    }
}
pub(super) fn defaults() -> &'static Value {
    static DEFAULTS: OnceLock<Value> = OnceLock::new();
    DEFAULTS.get_or_init(|| {
        serde_json::from_str(include_str!("../resources/project-defaults.json"))
            .expect("checked format-2 defaults")
    })
}
pub(super) fn with_defaults(kind: &str, value: &Value) -> Value {
    let mut v = defaults()[kind].clone();
    merge(&mut v, value);
    v
}
pub(super) fn merge(target: &mut Value, source: &Value) {
    if let (Some(target), Some(source)) = (target.as_object_mut(), source.as_object()) {
        for (key, value) in source {
            target.insert(key.clone(), value.clone());
        }
    }
}
pub(super) fn ensure_group(group: &hdf5::Group, name: &str) -> Result<hdf5::Group, String> {
    if group.link_exists(name) {
        group.group(name)
    } else {
        group.create_group(name)
    }
    .native()
}
pub(super) fn text(value: &Value) -> String {
    value.as_str().unwrap_or("").into()
}
pub(super) fn read_text_dataset(d: &hdf5::Dataset) -> Result<String, String> {
    if d.size() != 1 {
        return Err("Project JSON must be one scalar string.".into());
    }
    if d.dtype().native()?.is::<hdf5::types::VarLenUnicode>() {
        Ok(d.read_scalar::<hdf5::types::VarLenUnicode>()
            .native()?
            .to_string())
    } else {
        Ok(d.read_scalar::<hdf5::types::VarLenAscii>()
            .native()?
            .to_string())
    }
}
pub(super) fn read_json_dataset(group: &hdf5::Group, name: &str) -> Result<Value, String> {
    let d = group.dataset(name).native()?;
    if d.storage_size() > 64 * 1024 * 1024 {
        return Err("Project JSON exceeds 64 MiB.".into());
    }
    let s = read_text_dataset(&d)?;
    if s.len() > 64 * 1024 * 1024 {
        return Err("Project JSON exceeds 64 MiB.".into());
    }
    serde_json::from_str(&s).map_err(|e| format!("Invalid project {name}: {e}"))
}
pub(super) fn read_text_attr(
    location: &hdf5::Location,
    name: &str,
) -> Result<Option<String>, String> {
    if !location.attr_names().native()?.iter().any(|n| n == name) {
        return Ok(None);
    }
    let a = location.attr(name).native()?;
    if a.size() != 1 {
        return Err("Project string attribute must be scalar.".into());
    }
    let s = if a.dtype().native()?.is::<hdf5::types::VarLenUnicode>() {
        a.read_scalar::<hdf5::types::VarLenUnicode>()
            .native()?
            .to_string()
    } else {
        a.read_scalar::<hdf5::types::VarLenAscii>()
            .native()?
            .to_string()
    };
    if s.len() > 64 * 1024 * 1024 {
        return Err("Project metadata exceeds 64 MiB.".into());
    }
    Ok(Some(s))
}
pub(super) fn read_json_attr(
    location: &hdf5::Location,
    name: &str,
) -> Result<Option<Value>, String> {
    read_text_attr(location, name)?
        .map(|s| serde_json::from_str(&s).map_err(|e| e.to_string()))
        .transpose()
}
pub(super) fn write_text_attr(
    location: &hdf5::Location,
    name: &str,
    value: &str,
) -> Result<(), String> {
    if location.attr_names().native()?.iter().any(|n| n == name) {
        location.delete_attr(name).native()?;
    }
    let value = hdf5::types::VarLenUnicode::from_str(value).map_err(|e| e.to_string())?;
    location
        .new_attr::<hdf5::types::VarLenUnicode>()
        .shape(())
        .create(name)
        .native()?
        .write_scalar(&value)
        .native()
}
pub(super) fn write_scalar_attr<T: hdf5::H5Type>(
    location: &hdf5::Location,
    name: &str,
    value: T,
) -> Result<(), String> {
    if location.attr_names().native()?.iter().any(|n| n == name) {
        location.delete_attr(name).native()?;
    }
    location
        .new_attr::<T>()
        .shape(())
        .create(name)
        .native()?
        .write_scalar(&value)
        .native()
}
pub(super) fn replace(group: &hdf5::Group, name: &str) -> Result<(), String> {
    if group.link_exists(name) {
        group.unlink(name).native()?;
    }
    Ok(())
}
pub(super) fn write_json_dataset(
    group: &hdf5::Group,
    name: &str,
    value: &Value,
) -> Result<(), String> {
    replace(group, name)?;
    let value =
        hdf5::types::VarLenUnicode::from_str(&value.to_string()).map_err(|e| e.to_string())?;
    group
        .new_dataset::<hdf5::types::VarLenUnicode>()
        .shape(())
        .create(name)
        .native()?
        .write_scalar(&value)
        .native()
}
pub(super) fn write_array<T: hdf5::H5Type>(
    group: &hdf5::Group,
    name: &str,
    shape: &[usize],
    data: &[T],
) -> Result<(), String> {
    if shape.iter().try_fold(1_usize, |n, d| n.checked_mul(*d)) != Some(data.len()) {
        return Err("Project array dimensions disagree.".into());
    }
    replace(group, name)?;
    let builder = group.new_dataset::<T>().shape(shape);
    let dataset = if data.is_empty() {
        builder.create(name)
    } else {
        builder.shuffle().deflate(1).create(name)
    }
    .native()?;
    dataset.write_raw(data).native()
}
pub(super) fn put(group: &hdf5::Group, shape: &[usize], data: &[f64]) -> Result<Value, String> {
    let mut hash = Sha256::new();
    hash.update(format!("<f8:{shape:?}:"));
    for v in data {
        hash.update(v.to_le_bytes());
    }
    let key = format!("{:x}", hash.finalize());
    if !group.link_exists(&key) {
        write_array(group, &key, shape, data)?;
    }
    Ok(json!(key))
}
pub(super) fn read_array(d: &hdf5::Dataset) -> Result<Vec<f64>, String> {
    if (d.ndim() > 2 && (d.ndim() != 4 || d.shape()[2..] != [4, 3])) || d.size() > 64 * 1024 * 1024
    {
        return Err("Project array exceeds supported dimensions or 64 million samples.".into());
    }
    let dtype = d.dtype().native()?;
    if dtype.is::<bool>() {
        return Ok(d
            .read_raw::<bool>()
            .native()?
            .into_iter()
            .map(|v| u8::from(v) as f64)
            .collect());
    }
    if dtype.is::<u64>() {
        let values = d.read_raw::<u64>().native()?;
        if values.iter().any(|v| *v > 9_007_199_254_740_992) {
            return Err("Project integer counts exceed exact f64 scientific precision.".into());
        }
    }
    if dtype.is::<i64>() {
        let values = d.read_raw::<i64>().native()?;
        if values
            .iter()
            .any(|v| v.unsigned_abs() > 9_007_199_254_740_992)
        {
            return Err("Project integer counts exceed exact f64 scientific precision.".into());
        }
    }
    d.read_raw::<f64>().native()
}
type StoredArray = (Vec<usize>, Vec<f64>);
pub(super) fn array(
    file: &hdf5::File,
    group: &str,
    key: &Value,
) -> Result<Option<StoredArray>, String> {
    if key.is_null() {
        return Ok(None);
    }
    let key = key
        .as_str()
        .filter(|s| !s.is_empty() && s.len() <= 128 && s.bytes().all(|b| b.is_ascii_hexdigit()))
        .ok_or("Invalid project array reference.")?;
    let d = file.dataset(&format!("{group}/{key}")).native()?;
    Ok(Some((d.shape(), read_array(&d)?)))
}
pub(super) fn string_array(group: &hdf5::Group, name: &str) -> Result<Vec<String>, String> {
    let d = group.dataset(name).native()?;
    if d.ndim() != 1 || d.size() > 1_000_000 {
        return Err("Invalid project source list.".into());
    }
    let strings = if d.dtype().native()?.is::<hdf5::types::VarLenUnicode>() {
        d.read_raw::<hdf5::types::VarLenUnicode>()
            .native()?
            .iter()
            .map(ToString::to_string)
            .collect::<Vec<_>>()
    } else {
        d.read_raw::<hdf5::types::VarLenAscii>()
            .native()?
            .iter()
            .map(ToString::to_string)
            .collect()
    };
    if strings.iter().any(|s| s.len() > 65536) {
        return Err("Project source path is too long.".into());
    }
    Ok(strings)
}
pub(super) fn write_strings(
    group: &hdf5::Group,
    name: &str,
    values: &[String],
) -> Result<(), String> {
    let values = values
        .iter()
        .map(|s| hdf5::types::VarLenUnicode::from_str(s).map_err(|e| e.to_string()))
        .collect::<Result<Vec<_>, _>>()?;
    replace(group, name)?;
    group
        .new_dataset_builder()
        .with_data(&values)
        .create(name)
        .native()?;
    Ok(())
}
pub(super) const MAX_PROJECT_BYTES: u64 = 16 * 1024 * 1024 * 1024;
pub(super) fn copy_file(source: &Path, target: &Path, control: &Control) -> Result<(), String> {
    let input = std::fs::File::open(source).map_err(|e| e.to_string())?;
    copy_handle(&input, target, control)
}
pub(super) fn copy_handle(
    source: &std::fs::File,
    target: &Path,
    control: &Control,
) -> Result<(), String> {
    // The retained descriptor remains valid if temporary-file cleanup removes
    // its pathname. Session commands own serialization of this archive.
    let mut input = source.try_clone().map_err(|e| e.to_string())?;
    input.seek(SeekFrom::Start(0)).map_err(|e| e.to_string())?;
    if input.metadata().map_err(|e| e.to_string())?.len() > MAX_PROJECT_BYTES {
        return Err("Project exceeds the 16 GiB file bound.".into());
    }
    let mut output = std::fs::File::create(target).map_err(|e| e.to_string())?;
    let mut buffer = vec![0_u8; 1024 * 1024];
    let mut copied = 0_u64;
    loop {
        control.check()?;
        let n = input.read(&mut buffer).map_err(|e| e.to_string())?;
        if n == 0 {
            break;
        }
        copied += n as u64;
        if copied > MAX_PROJECT_BYTES {
            return Err("Project exceeds the 16 GiB file bound.".into());
        }
        output.write_all(&buffer[..n]).map_err(|e| e.to_string())?;
    }
    output.flush().map_err(|e| e.to_string())?;
    Ok(())
}
pub(super) struct Archive {
    pub(super) series_origins: super::series_arrays::Origins,
    // Close HDF5 before NamedTempFile attempts removal (including on Windows).
    pub(super) file: hdf5::File,
    pub(super) snapshot: tempfile::NamedTempFile,
}
pub(super) fn snapshot_file(path: &Path, control: &Control) -> Result<Archive, String> {
    let before = crate::image::FileIdentity::read(path)?;
    let temp = tempfile::NamedTempFile::new().map_err(|e| e.to_string())?;
    copy_file(path, temp.path(), control)?;
    if before != crate::image::FileIdentity::read(path)? {
        return Err("Project changed while being loaded.".into());
    }
    // Retain an HDF5 handle too: unknown extensions must remain accessible even
    // after the owned snapshot's directory entry is unlinked.
    let file = hdf5::File::open(temp.path()).native()?;
    Ok(Archive {
        series_origins: super::series_arrays::Origins::new(&file)?,
        snapshot: temp,
        file,
    })
}
/// Preflight the total arrays that will be materialized, before loading any
/// configuration. Save uses the same gate so it cannot publish an unreadable file.
pub(super) fn validate_sample_budget(file: &hdf5::File, doc: &Value) -> Result<(), String> {
    let mut samples = 0_usize;
    let mut add = |name: String, required: bool| -> Result<(), String> {
        if !file.link_exists(&name) {
            if required {
                return Err(format!("Project array {name} is missing."));
            }
            return Ok(());
        }
        let n = file.dataset(&name).native()?.size();
        samples = samples
            .checked_add(n)
            .filter(|n| *n <= 256_000_000)
            .ok_or("Project science arrays exceed the 256-million-sample memory bound.")?;
        Ok(())
    };
    let mut reference = |group: &str, key: &Value| -> Result<(), String> {
        if key.is_null() {
            return Ok(());
        }
        let key = key
            .as_str()
            .filter(|s| !s.is_empty() && s.len() <= 128 && s.bytes().all(|c| c.is_ascii_hexdigit()))
            .ok_or("Invalid project array reference.")?;
        add(format!("{group}/{key}"), true)
    };
    let configs = doc["configurations"]
        .as_array()
        .ok_or("Missing project configurations.")?;
    for c in configs {
        for name in [
            "mask_data",
            "pattern_x",
            "pattern_y",
            "pattern_errors",
            "pattern_azimuthal_std",
        ] {
            reference("payloads", &c[name])?;
        }
        for name in ["image_data", "background_data"] {
            reference("cache", &c[name])?;
        }
        reference("cache", &c["native_desktop"]["flat_response"])?;
        for name in ["x", "y"] {
            reference("payloads", &c["anonymous_background"][name])?;
        }
    }
    for overlay in doc["overlays"].as_array().into_iter().flatten() {
        for name in ["x", "y"] {
            reference("payloads", &overlay[name])?;
        }
    }
    for i in 0..configs.len() {
        for prefix in [
            format!("configurations/{i}/native_batch/result"),
            format!("configurations/{i}/map/native_series/result"),
        ] {
            for name in [
                "data",
                "desktop_original",
                "azimuthal_std",
                "desktop_original_spread",
                "desktop_original_background",
            ] {
                add(format!("{prefix}/{name}"), false)?;
            }
        }
        add(
            format!("configurations/{i}/native_batch/process/bkg"),
            false,
        )?;
        if !file.link_exists(&format!("configurations/{i}/map/native_series")) {
            add(format!("configurations/{i}/map/pattern_intensities"), false)?;
        }
    }
    let selected = doc["selected_configuration"].as_u64().unwrap_or(0);
    if !file.link_exists(&format!("configurations/{selected}/native_batch")) {
        for name in [
            "data",
            "bkg",
            "azimuthal_std",
            "normalization_source/data",
            "normalization_source/spread",
            "normalization_source/background",
        ] {
            add(format!("react_desktop_batch/{name}"), false)?;
        }
    }
    if !file.link_exists(&format!("configurations/{selected}/map/native_series")) {
        add("react_map_normalization/original".into(), false)?;
    }
    Ok(())
}

/// Enforce the same physical bound on publication as on opening. Opaque legacy
/// extensions retain their bytes, but cannot publish a project we cannot reopen.
pub(super) fn finish_project(
    temp: crate::output::StagedOutput,
    target: &Path,
    control: &Control,
    maximum_bytes: u64,
) -> Result<(), String> {
    if temp.as_file().metadata().map_err(|e| e.to_string())?.len() > maximum_bytes {
        return Err(
            "Project exceeds the 16 GiB file bound; the previous file was preserved.".into(),
        );
    }
    temp.commit_checked(target, || control.check())
}
