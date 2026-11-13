//! Desktop admission and display records for the native library's image catalog.
use dioptrin_io::hdf5::typed;
use serde::{Deserialize, Serialize};
use std::path::Path;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Source {
    pub dataset: String,
    pub frames: Option<usize>,
    pub shape: Option<[usize; 2]>,
    #[serde(default, skip_serializing_if = "std::ops::Not::not")]
    pub needs_bindings: bool,
}
pub fn discover(
    path: &Path,
    options: typed::Options,
    settings: &serde_json::Value,
) -> Result<Vec<Source>, String> {
    let mut result = vec![];
    let mut failures = vec![];
    let origin = settings["path"]
        .as_str()
        .and_then(|p| Path::new(p).parent());
    for dataset in
        dioptrin_io::hdf5::catalog::image_paths(path, options, origin).map_err(|e| e.to_string())?
    {
        // The same reader used to load pixels admits shape, type, filters and
        // storage. Unsupported arrays never acquire a scientific interpretation.
        let admitted = crate::hdf5_loading::open_dataset(path, &dataset, options, settings);
        if let Ok(reader) = &admitted
            && let Some(m) = reader.metadata(0)
            && !m.shape.contains(&0)
            && m.shape[0]
                .checked_mul(m.shape[1])
                .is_some_and(|n| n <= 64 * 1024 * 1024)
        {
            result.push(Source {
                dataset,
                needs_bindings: false,
                frames: Some(reader.frames()),
                shape: Some(m.shape),
            });
        } else if let Err(error) = admitted {
            if crate::hdf5_loading::request(
                path,
                typed::Selection::Dataset(&dataset),
                options,
                settings,
            )
            .is_ok_and(|r| r.is_some())
            {
                result.push(Source {
                    dataset,
                    frames: None,
                    shape: None,
                    needs_bindings: true,
                });
            } else {
                failures.push(format!("{dataset}: {error}"));
            }
        }
    }
    if result.is_empty()
        && let Some(error) = failures.first()
    {
        return Err(error.clone());
    }
    Ok(result)
}
