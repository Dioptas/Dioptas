//! Archive-scoped, immutable f64 array origins. Weak allocation identities are
//! invalidated by Arc::make_mut (including its weak-only dissociation path), so
//! neither mutable arrays nor file-supplied hashes can authorize dataset reuse.
use super::*;
use std::{collections::HashMap, sync::Weak};

pub(super) struct Origins {
    archive: u64,
    arrays: Vec<Origin>,
}
struct Origin {
    values: Weak<Vec<f64>>,
    path: String,
    shape: Vec<usize>,
    unit: Option<String>,
}
fn axis_unit(dataset: &hdf5::Dataset) -> Option<String> {
    dataset.attr("radial_unit").ok().and_then(|a| {
        a.read_scalar::<hdf5::types::VarLenUnicode>()
            .map(|s| s.as_str().to_owned())
            .or_else(|_| {
                a.read_scalar::<hdf5::types::VarLenAscii>()
                    .map(|s| s.as_str().to_owned())
            })
            .ok()
    })
}
impl Origins {
    pub(super) fn new(file: &hdf5::File) -> Result<Self, String> {
        Ok(Self {
            archive: file.loc_info().native()?.fileno,
            arrays: vec![],
        })
    }
    pub(super) fn record(&mut self, dataset: &hdf5::Dataset, values: &Arc<Vec<f64>>) {
        // HDF5 permits numeric conversion on read; only canonical native f64
        // objects have the same storage contract as the processed-file writer.
        // The owned archive only freezes internal storage. Virtual/external
        // pixels and links into other files can change without changing this
        // Arc, so their loaded Vec must be written as a new owned dataset.
        let frozen_storage = dataset.dcpl().is_ok_and(|p| {
            p.get_layout()
                .is_ok_and(|layout| layout != hdf5::dataset::Layout::Virtual)
                && p.get_external().is_ok_and(|external| external.is_empty())
        });
        if frozen_storage
            && dataset.loc_info().is_ok_and(|i| i.fileno == self.archive)
            && dataset.dtype().is_ok_and(|d| d.is::<f64>())
        {
            self.arrays.push(Origin {
                values: Arc::downgrade(values),
                path: dataset.name(),
                shape: dataset.shape(),
                unit: axis_unit(dataset),
            });
        }
    }
}
#[derive(Hash, PartialEq, Eq)]
struct Key(usize, Vec<usize>, Option<String>);
struct Pinned {
    values: Weak<Vec<f64>>,
    path: String,
}
pub(super) struct Writer {
    pins: hdf5::Group,
    arrays: HashMap<Key, Pinned>,
    control: Arc<Control>,
    next: usize,
}
const PINS: &str = "__native_series_arrays";
impl Writer {
    pub(super) fn new(
        file: &hdf5::File,
        origins: Option<&Origins>,
        control: &Arc<Control>,
    ) -> Result<Self, String> {
        if file.link_exists(PINS) {
            return Err("Reserved project array staging group already exists.".into());
        }
        let mut writer = Self {
            pins: file.create_group(PINS).native()?,
            arrays: HashMap::new(),
            control: control.clone(),
            next: 0,
        };
        // Pin before ANY configuration is reindexed or any native group replaced.
        // A held Dataset alone would not make its old pathname safe to resolve.
        if let Some(origins) = origins {
            for origin in &origins.arrays {
                control.check()?;
                if let Some(values) = origin.values.upgrade() {
                    writer.pin(&origin.path, &values, &origin.shape, origin.unit.as_deref())?;
                }
            }
        }
        Ok(writer)
    }
    fn pin(
        &mut self,
        path: &str,
        values: &Arc<Vec<f64>>,
        shape: &[usize],
        unit: Option<&str>,
    ) -> Result<(), String> {
        let name = self.next.to_string();
        self.next += 1;
        self.pins.link_hard(path, &name).native()?;
        self.arrays.insert(
            Key(
                Arc::as_ptr(values) as usize,
                shape.to_vec(),
                unit.map(str::to_owned),
            ),
            Pinned {
                values: Arc::downgrade(values),
                path: format!("/{PINS}/{name}"),
            },
        );
        Ok(())
    }
    pub(super) fn write(
        &mut self,
        group: &hdf5::Group,
        name: &str,
        shape: &[usize],
        values: &Arc<Vec<f64>>,
        unit: Option<&str>,
    ) -> Result<hdf5::Dataset, String> {
        self.control.check()?;
        let key = Key(
            Arc::as_ptr(values) as usize,
            shape.to_vec(),
            unit.map(str::to_owned),
        );
        if let Some(origin) = self.arrays.get(&key)
            && origin
                .values
                .upgrade()
                .is_some_and(|a| Arc::ptr_eq(&a, values))
        {
            group.link_hard(&origin.path, name).native()?;
            return group.dataset(name).native();
        }
        let dataset = crate::series::write_processed_array(group, name, shape, values, unit)?;
        self.pin(&dataset.name(), values, shape, unit)?;
        Ok(dataset)
    }
    pub(super) fn finish(self, file: &hdf5::File) -> Result<(), String> {
        drop(self);
        file.unlink(PINS).native()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn token(d: &hdf5::Dataset) -> String {
        format!("{:?}", d.loc_info().unwrap().token)
    }
    fn fixture() -> (tempfile::NamedTempFile, hdf5::File, Arc<Vec<f64>>, Origins) {
        let temp = tempfile::NamedTempFile::new().unwrap();
        let file = hdf5::File::create(temp.path()).unwrap();
        let values = Arc::new(vec![1.000000000000001, -0.0, 3.0, 4.0]);
        let dataset =
            crate::series::write_processed_array(&file, "original", &[2, 2], &values, None)
                .unwrap();
        dataset
            .new_attr::<u32>()
            .create("extension_marker")
            .unwrap()
            .write_scalar(&123)
            .unwrap();
        let mut origins = Origins::new(&file).unwrap();
        origins.record(&dataset, &values);
        (temp, file, values, origins)
    }
    #[test]
    fn pins_old_object_before_replacement_and_reuses_it_with_attributes() {
        let (_temp, file, values, origins) = fixture();
        let control = Arc::new(Control::default());
        let mut writer = Writer::new(&file, Some(&origins), &control).unwrap();
        let original = token(&file.dataset("original").unwrap());
        file.unlink("original").unwrap();
        crate::series::write_processed_array(
            &file,
            "original",
            &[2, 2],
            &Arc::new(vec![99.; 4]),
            None,
        )
        .unwrap();
        let reused = writer
            .write(&file, "reused", &[2, 2], &values, None)
            .unwrap();
        assert_eq!(token(&reused), original);
        assert_eq!(
            reused
                .attr("extension_marker")
                .unwrap()
                .read_scalar::<u32>()
                .unwrap(),
            123
        );
        let alias = writer
            .write(&file, "shared", &[2, 2], &values, None)
            .unwrap();
        assert_eq!(token(&alias), original);
        writer.finish(&file).unwrap();
        assert!(!file.link_exists(PINS));
        assert_eq!(
            reused.read_raw::<f64>().unwrap()[0].to_bits(),
            values[0].to_bits()
        );
    }
    #[test]
    fn weak_only_and_shared_mutations_invalidate_origins_and_preserve_f64_bits() {
        for shared in [false, true] {
            let (_temp, file, mut values, origins) = fixture();
            let original = file.dataset("original").unwrap();
            let another = shared.then(|| values.clone());
            assert!(Arc::get_mut(&mut values).is_none());
            Arc::make_mut(&mut values)[0] += 2.0_f64.powi(-48);
            assert_eq!(values[0] as f32, 1.0_f32);
            let control = Arc::new(Control::default());
            let mut writer = Writer::new(&file, Some(&origins), &control).unwrap();
            let changed = writer
                .write(&file, "changed", &[2, 2], &values, None)
                .unwrap();
            assert_ne!(token(&changed), token(&original));
            assert_eq!(
                changed.read_raw::<f64>().unwrap()[0].to_bits(),
                values[0].to_bits()
            );
            assert!(
                !changed
                    .attr_names()
                    .unwrap()
                    .iter()
                    .any(|n| n == "extension_marker")
            );
            assert_eq!(
                original.read_raw::<f64>().unwrap()[0].to_bits(),
                1.000000000000001_f64.to_bits()
            );
            drop(another);
            writer.finish(&file).unwrap();
        }
    }
    #[test]
    fn externally_backed_and_other_archive_datasets_are_materialized_not_reused() {
        let (_temp, file, values, _) = fixture();
        let raw = tempfile::NamedTempFile::new().unwrap();
        let external = file
            .new_dataset::<f64>()
            .shape([4])
            .external(raw.path().to_str().unwrap(), 0, 32)
            .create("external")
            .unwrap();
        external.write_raw(values.as_slice()).unwrap();
        let virtual_array = file
            .new_dataset::<f64>()
            .shape([4])
            .virtual_map(".", "original", [2, 2], (.., ..), [4], ..)
            .create("virtual")
            .unwrap();
        let other_temp = tempfile::NamedTempFile::new().unwrap();
        let other = hdf5::File::create(other_temp.path()).unwrap();
        let outside =
            crate::series::write_processed_array(&other, "outside", &[4], &values, None).unwrap();
        file.link_external(
            other_temp.path().to_str().unwrap(),
            "/outside",
            "external_link",
        )
        .unwrap();
        let linked = file.dataset("external_link").unwrap();
        let mut origins = Origins::new(&file).unwrap();
        for dataset in [&external, &virtual_array, &outside, &linked] {
            origins.record(dataset, &values);
        }
        assert!(origins.arrays.is_empty());
        // An external raw file can change behind the frozen Arc. The save must
        // write owned session values rather than retain that mutable dependency.
        external.write_raw(&[99_f64; 4]).unwrap();
        let control = Arc::new(Control::default());
        let mut writer = Writer::new(&file, Some(&origins), &control).unwrap();
        let saved = writer.write(&file, "owned", &[4], &values, None).unwrap();
        assert_eq!(saved.read_raw::<f64>().unwrap(), *values);
        assert!(saved.dcpl().unwrap().get_external().unwrap().is_empty());
        writer.finish(&file).unwrap();
    }
    #[test]
    fn shape_axis_unit_and_converted_numeric_sources_cannot_authorize_reuse() {
        let (_temp, file, values, origins) = fixture();
        let control = Arc::new(Control::default());
        let mut writer = Writer::new(&file, Some(&origins), &control).unwrap();
        let differently_shaped = writer
            .write(&file, "reshaped", &[4], &values, None)
            .unwrap();
        assert_ne!(
            token(&differently_shaped),
            token(&file.dataset("original").unwrap())
        );
        let axis_a = writer
            .write(&file, "axis_a", &[4], &values, Some("q_A^-1"))
            .unwrap();
        let axis_b = writer
            .write(&file, "axis_b", &[4], &values, Some("2th_deg"))
            .unwrap();
        assert_ne!(token(&axis_a), token(&axis_b));
        writer.finish(&file).unwrap();
        let source = file
            .new_dataset_builder()
            .with_data(&[1_f32, 2., 3., 4.])
            .create("converted")
            .unwrap();
        let mut origins = Origins::new(&file).unwrap();
        origins.record(&source, &values);
        assert!(origins.arrays.is_empty());
        let mut writer = Writer::new(&file, Some(&origins), &control).unwrap();
        let native = writer
            .write(&file, "canonical", &[4], &values, None)
            .unwrap();
        assert!(native.dtype().unwrap().is::<f64>());
        assert_ne!(token(&native), token(&source));
        writer.finish(&file).unwrap();
    }
}
