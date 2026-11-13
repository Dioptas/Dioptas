//! Desktop choices and persisted source identities. HDF5 graph/declaration
//! discovery, exact filename resolution and all decoding belong to dioptrin-io.
use crate::image::FileIdentity;
use dioptrin_io::{
    hdf5::{
        contracts::{FileChoice, FileKind, Requirement, SourceContracts},
        typed,
    },
    wrapped::{Input, Reader},
};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::path::{Path, PathBuf};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Binding {
    owner: PathBuf,
    stored_filename: String,
    actual_file: PathBuf,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Printf {
    owner: PathBuf,
    dataset: String,
    mapping_index: usize,
    stored_filename: String,
    declared_dataset: String,
    blocks: usize,
}
fn resolve(
    path: &Path,
    selection: typed::Selection<'_>,
    options: typed::Options,
    settings: &Value,
    origin: Option<&Path>,
) -> Result<SourceContracts, String> {
    let bindings: Vec<Binding> =
        serde_json::from_value(settings.get("hdf5_bindings").cloned().unwrap_or(json!([])))
            .map_err(|e| e.to_string())?;
    let printf: Vec<Printf> =
        serde_json::from_value(settings.get("hdf5_printf").cloned().unwrap_or(json!([])))
            .map_err(|e| e.to_string())?;
    let choices: Vec<_> = bindings
        .into_iter()
        .map(|b| FileChoice {
            owner: if settings["path"].as_str().is_some_and(|root| {
                Path::new(root).canonicalize().ok() == b.owner.canonicalize().ok()
            }) {
                path.into()
            } else {
                b.owner
            },
            stored_filename: b.stored_filename,
            actual_file: b.actual_file,
        })
        .collect();
    let plans: Vec<_> = printf
        .into_iter()
        .map(|p| typed::PrintfMapping {
            source_file: Some(
                if settings["path"].as_str().is_some_and(|root| {
                    Path::new(root).canonicalize().ok() == p.owner.canonicalize().ok()
                }) {
                    path.into()
                } else {
                    p.owner
                },
            ),
            dataset: p.dataset,
            mapping_index: p.mapping_index,
            stored_filename: p.stored_filename,
            declared_dataset: p.declared_dataset,
            blocks: p.blocks,
        })
        .collect();
    SourceContracts::resolve_snapshot(path, selection, options, &choices, &plans, origin)
        .map_err(|e| e.to_string())
}
pub(crate) fn open_dataset(
    path: &Path,
    dataset: &str,
    options: typed::Options,
    settings: &Value,
) -> Result<typed::Reader, String> {
    check_snapshot(path, settings)?;
    let selection = typed::Selection::Dataset(dataset);
    if let Ok(reader) = typed::Reader::open_snapshot(path, selection, options) {
        return Ok(reader);
    }
    let origin = settings["path"]
        .as_str()
        .and_then(|p| Path::new(p).parent());
    let contracts = resolve(path, selection, options, settings, origin)?;
    contracts.require_complete().map_err(|e| e.to_string())?;
    let reader = typed::Reader::open_snapshot_with_storage(
        path,
        selection,
        options,
        Some(contracts.vds_options(typed::UnmappedRegions::DeclaredFill)),
        Some(contracts.external_raw_options()),
        origin,
    )
    .map_err(|e| e.to_string())?;
    contracts.check_sources().map_err(|e| e.to_string())?;
    Ok(reader)
}
pub(crate) fn open(
    input: Input,
    selection: typed::Selection<'_>,
    options: typed::Options,
    settings: &Value,
) -> Result<Reader, String> {
    let path = input.source_path().map_err(|e| e.to_string())?;
    check_snapshot(path, settings)?;
    if let Ok(reader) = input.clone().read_hdf5(selection, options, None) {
        return Ok(reader);
    }
    let origin = input
        .provenance()
        .map_err(|e| e.to_string())?
        .origin_directory;
    let contracts = resolve(path, selection, options, settings, origin.as_deref())?;
    contracts.require_complete().map_err(|e| e.to_string())?;
    let reader = input
        .read_hdf5_with_contracts(
            selection,
            options,
            &contracts,
            typed::UnmappedRegions::DeclaredFill,
        )
        .map_err(|e| e.to_string())?;
    Ok(reader)
}
pub(crate) fn request(
    path: &Path,
    selection: typed::Selection<'_>,
    options: typed::Options,
    settings: &Value,
) -> Result<Option<Value>, String> {
    check_snapshot(path, settings)?;
    let origin = settings["path"]
        .as_str()
        .and_then(|p| Path::new(p).parent());
    let contracts = resolve(path, selection, options, settings, origin)?;
    if contracts.requirements().is_empty() {
        return Ok(None);
    }
    let requirements: Vec<_> = contracts.requirements().iter().map(|r|match r {
        Requirement::File { kind, owner, stored_filename, expected_file } => json!({"kind":if *kind==FileKind::Virtual {"vds"}else{"raw"},"owner":owner,"stored_filename":stored_filename,"expected_file":expected_file}),
        Requirement::Printf { owner, dataset, mapping_index, stored_filename, declared_dataset } => json!({"kind":"printf","owner":owner,"dataset":dataset,"mapping_index":mapping_index,"stored_filename":stored_filename,"declared_dataset":declared_dataset}),
    }).collect();
    let root = settings["path"]
        .as_str()
        .map(PathBuf::from)
        .unwrap_or_else(|| path.into());
    let physical_root = path.canonicalize().map_err(|e| e.to_string())?;
    let requirements: Vec<_> = requirements
        .into_iter()
        .map(|mut r| {
            if r["owner"] == json!(physical_root) {
                r["owner"] = json!(root);
            }
            r
        })
        .collect();
    let mut files = fingerprint(&root, settings)?.unwrap_or_default();
    for file in std::iter::once(root.clone()).chain(
        contracts
            .source_bindings()
            .iter()
            .flat_map(|b| [b.requested.clone(), b.resolved.clone()])
            .filter(|p| p != path && *p != physical_root),
    ) {
        if !files.iter().any(|(p, _)| *p == file) {
            files.push((file.clone(), FileIdentity::read(&file)?));
        }
    }
    contracts.check_sources().map_err(|e| e.to_string())?;
    let mut settings = settings.clone();
    settings["path"] = json!(root);
    settings["hdf5_snapshot"] = snapshot(&root, files);
    Ok(Some(
        json!({"path":root,"options":settings,"requirements":requirements}),
    ))
}
#[derive(Serialize, Deserialize)]
struct Snapshot {
    root: PathBuf,
    files: Vec<(PathBuf, FileIdentity)>,
}
pub(crate) fn check_snapshot(path: &Path, settings: &Value) -> Result<(), String> {
    fingerprint(path, settings).map(|_| ())
}
pub(crate) fn fingerprint(
    path: &Path,
    settings: &Value,
) -> Result<Option<Vec<(PathBuf, FileIdentity)>>, String> {
    if let Some(v) = settings.get("hdf5_snapshot") {
        let snapshot: Snapshot = serde_json::from_value(v.clone()).map_err(|e| e.to_string())?;
        if snapshot.root == path {
            if snapshot.files.len()
                > (typed::Limits::default().source_files + typed::Limits::default().link_traversals)
                    * 2
                    + 4
            {
                return Err("HDF5 snapshot file limit.".into());
            }
            for (file, identity) in &snapshot.files {
                if FileIdentity::read(file)
                    .map_err(|e| format!("HDF5 companion {}: {e}", file.display()))?
                    != *identity
                {
                    return Err(format!(
                        "HDF5 source changed since it was opened: {}. Open the master again to create a new snapshot.",
                        file.display()
                    ));
                }
            }
            return Ok(Some(snapshot.files));
        }
    }
    Ok(None)
}
pub(crate) fn snapshot(root: &Path, files: Vec<(PathBuf, FileIdentity)>) -> Value {
    serde_json::to_value(Snapshot {
        root: root.into(),
        files,
    })
    .expect("serializable file identities")
}
