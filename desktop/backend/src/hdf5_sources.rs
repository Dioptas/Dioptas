//! Metadata-only image-source discovery. The native NeXus snapshot owns exact
//! link resolution/admission; HDF5's external-file search is never invoked here.
use dioptrin_io::hdf5::{nexus, typed};
use hdf5::{File, LinkType, LocationToken, LocationType};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Source {
    pub dataset: String,
    pub frames: usize,
    pub shape: [usize; 2],
}
pub fn discover(path: &Path, options: typed::Options) -> Result<Vec<Source>, String> {
    let snapshot = nexus::Reader::open_snapshot(path, options).map_err(|e| e.to_string())?;
    let mut scan = Scan {
        snapshot,
        options,
        paths: vec![],
        ancestors: vec![],
        visited: 0,
    };
    let root = path.canonicalize().map_err(|e| e.to_string())?;
    scan.visit(&root, "/", "/", 0)?;
    scan.paths.sort();
    scan.paths.dedup();
    let mut result = vec![];
    for dataset in &scan.paths {
        // The same reader used to load pixels admits shape, type, filters and
        // storage. Unsupported arrays never acquire a scientific interpretation.
        if let Ok(reader) =
            typed::Reader::open_snapshot(path, typed::Selection::Dataset(dataset), options)
            && let Some(m) = reader.metadata(0)
            && !m.shape.contains(&0)
            && m.shape[0]
                .checked_mul(m.shape[1])
                .is_some_and(|n| n <= 64 * 1024 * 1024)
        {
            result.push(Source {
                dataset: dataset.clone(),
                frames: reader.frames(),
                shape: m.shape,
            });
        }
    }
    scan.snapshot.check_sources().map_err(|e| e.to_string())?;
    Ok(result)
}
struct Scan {
    snapshot: nexus::Reader,
    options: typed::Options,
    paths: Vec<String>,
    ancestors: Vec<(PathBuf, LocationToken)>,
    visited: usize,
}
impl Scan {
    /// Expand only links already resolved and frozen by the native reader. This
    /// maps a master-file alias to a concrete path without native link following.
    fn resolve(
        &self,
        file: &Path,
        target: &str,
        depth: usize,
    ) -> Result<(PathBuf, String), String> {
        if depth >= self.options.limits.link_traversals {
            return Err("HDF5 source link traversal limit.".into());
        }
        let parts: Vec<_> = target
            .split('/')
            .filter(|p| !p.is_empty() && *p != ".")
            .collect();
        let mut path = String::new();
        for (index, part) in parts.iter().enumerate() {
            path.push('/');
            path.push_str(part);
            if let Some(link) = self
                .snapshot
                .links()
                .iter()
                .find(|l| l.source == file && l.path == path)
            {
                let (next_file, next_path) = if link.external {
                    let mut strings = link.raw_value[1..].split(|b| *b == 0);
                    let filename = std::str::from_utf8(strings.next().unwrap_or_default())
                        .map_err(|e| e.to_string())?;
                    let next = std::str::from_utf8(strings.next().unwrap_or_default())
                        .map_err(|e| e.to_string())?
                        .to_owned();
                    (
                        file.parent()
                            .unwrap()
                            .join(filename)
                            .canonicalize()
                            .map_err(|e| e.to_string())?,
                        next,
                    )
                } else {
                    let next = std::str::from_utf8(
                        link.raw_value
                            .strip_suffix(&[0])
                            .ok_or("Invalid native soft-link manifest.")?,
                    )
                    .map_err(|e| e.to_string())?;
                    (
                        file.to_path_buf(),
                        if next.starts_with('/') {
                            next.into()
                        } else {
                            format!("{}/{next}", path.rsplit_once('/').unwrap().0)
                        },
                    )
                };
                return self.resolve(
                    &next_file,
                    &format!("{next_path}/{}", parts[index + 1..].join("/")),
                    depth + 1,
                );
            }
        }
        Ok((file.into(), if path.is_empty() { "/".into() } else { path }))
    }
    fn visit(
        &mut self,
        file: &Path,
        path: &str,
        requested: &str,
        depth: usize,
    ) -> Result<(), String> {
        self.visited += 1;
        if depth >= 128
            || self.visited > self.options.limits.group_members
            || requested.len() > self.options.limits.text_bytes
        {
            return Err("HDF5 image-source discovery exceeds traversal limits.".into());
        }
        if !self.snapshot.sources().iter().any(|s| s.path == file) {
            return Err("HDF5 source is outside the native snapshot.".into());
        }
        let h5 = File::open(file).map_err(|e| e.to_string())?;
        let info = h5.loc_info_by_name(path).map_err(|e| e.to_string())?;
        match info.loc_type {
            LocationType::Dataset => {
                if matches!(h5.dataset(path).map_err(|e| e.to_string())?.ndim(), 2 | 3) {
                    if self.paths.len() >= self.options.limits.datasets {
                        return Err("HDF5 image-source count exceeds limit.".into());
                    }
                    self.paths.push(requested.into());
                }
            }
            LocationType::Group => {
                if self
                    .ancestors
                    .iter()
                    .any(|(f, t)| f == file && *t == info.token)
                {
                    return Ok(()); // group cycle; keep other aliases
                }
                self.ancestors.push((file.into(), info.token));
                let group = h5.group(path).map_err(|e| e.to_string())?;
                let mut members = vec![];
                group
                    .iter_visit_default(|name, info| {
                        if members.len() >= self.options.limits.group_members {
                            return Err(hdf5::Error::from("HDF5 group member limit"));
                        }
                        members.push((name.to_owned(), info.link_type));
                        Ok(())
                    })
                    .map_err(|e| e.to_string())?;
                for (name, kind) in members {
                    let child = format!("{}/{name}", path.trim_end_matches('/'));
                    let alias = format!("{}/{name}", requested.trim_end_matches('/'));
                    if kind == LinkType::Hard {
                        self.visit(file, &child, &alias, depth + 1)?;
                    } else {
                        let (target_file, target) = self.resolve(file, &child, 0)?;
                        self.visit(&target_file, &target, &alias, depth + 1)?;
                    }
                }
                self.ancestors.pop();
            }
            _ => {}
        }
        Ok(())
    }
}
