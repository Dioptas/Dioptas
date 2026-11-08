//! Shared-object graph for private development history checkpoints.
//! Binary numeric values retain NaNs/infinities, and shared planes/curves are
//! written once. Reconstructed Arc identity also preserves model comparisons.
use serde::{Deserialize, Deserializer, Serialize, Serializer, de::DeserializeOwned};
use std::sync::Arc;

#[cfg(debug_assertions)]
mod graph {
    use super::*;
    use std::{
        any::{Any, TypeId, type_name},
        cell::RefCell,
        collections::{HashMap, HashSet},
    };

    struct Writer {
        group: hdf5::Group,
        objects: HashMap<(TypeId, usize), u64>,
    }
    struct Reader {
        group: hdf5::Group,
        objects: HashMap<u64, Box<dyn Any>>,
        decoding: HashSet<u64>,
    }
    enum Context {
        Write(Writer),
        Read(Reader),
    }
    thread_local! { static CONTEXT: RefCell<Option<Context>> = const { RefCell::new(None) }; }
    struct Scope;
    impl Drop for Scope {
        fn drop(&mut self) {
            CONTEXT.with(|c| *c.borrow_mut() = None);
        }
    }
    fn scope(context: Context) -> Result<Scope, String> {
        CONTEXT.with(|c| {
            let mut c = c.borrow_mut();
            if c.is_some() {
                return Err("Nested history checkpoint.".into());
            }
            *c = Some(context);
            Ok(Scope)
        })
    }
    pub(super) fn active() -> bool {
        CONTEXT.with(|c| c.borrow().is_some())
    }
    pub(super) fn put_arc<T: Serialize + 'static>(value: &Arc<T>) -> Result<u64, String> {
        let key = (TypeId::of::<T>(), Arc::as_ptr(value) as usize);
        let (id, group, exists) = CONTEXT.with(|context| {
            let mut context = context.borrow_mut();
            let Some(Context::Write(writer)) = context.as_mut() else {
                return Err("Missing history writer.".to_string());
            };
            if let Some(id) = writer.objects.get(&key) {
                return Ok((*id, writer.group.clone(), true));
            }
            let id = writer.objects.len() as u64;
            writer.objects.insert(key, id);
            Ok((id, writer.group.clone(), false))
        })?;
        if exists {
            return Ok(id);
        }
        let bytes = rmp_serde::to_vec_named(value.as_ref()).map_err(|e| e.to_string())?;
        let entry = group
            .create_group(&id.to_string())
            .map_err(|e| e.to_string())?;
        entry
            .new_dataset_builder()
            .with_data(type_name::<T>().as_bytes())
            .create("kind")
            .map_err(|e| e.to_string())?;
        entry
            .new_dataset_builder()
            .with_data(&bytes)
            .deflate(1)
            .create("data")
            .map_err(|e| e.to_string())?;
        Ok(id)
    }
    pub(super) fn get_arc<T: DeserializeOwned + 'static>(id: u64) -> Result<Arc<T>, String> {
        let (cached, group) = CONTEXT.with(|context| {
            let mut context = context.borrow_mut();
            let Some(Context::Read(reader)) = context.as_mut() else {
                return Err("Missing history reader.".to_string());
            };
            if let Some(value) = reader.objects.get(&id) {
                return value
                    .downcast_ref::<Arc<T>>()
                    .cloned()
                    .map(|v| (Some(v), reader.group.clone()))
                    .ok_or("History object type differs.".into());
            }
            if !reader.decoding.insert(id) {
                return Err("Cyclic history checkpoint.".into());
            }
            Ok((None, reader.group.clone()))
        })?;
        if let Some(value) = cached {
            return Ok(value);
        }
        let entry = group.group(&id.to_string()).map_err(|e| e.to_string())?;
        let kind = entry
            .dataset("kind")
            .and_then(|d| d.read_raw::<u8>())
            .map_err(|e| e.to_string())?;
        if kind != type_name::<T>().as_bytes() {
            return Err("History object type differs.".into());
        }
        let bytes = entry
            .dataset("data")
            .and_then(|d| d.read_raw::<u8>())
            .map_err(|e| e.to_string())?;
        let value = Arc::new(rmp_serde::from_slice::<T>(&bytes).map_err(|e| e.to_string())?);
        CONTEXT.with(|context| {
            if let Some(Context::Read(reader)) = context.borrow_mut().as_mut() {
                reader.decoding.remove(&id);
                reader.objects.insert(id, Box::new(value.clone()));
            }
        });
        Ok(value)
    }
    pub(crate) fn save<T: Serialize>(file: &hdf5::File, value: &T) -> Result<(), String> {
        if file.link_exists("development_history") {
            file.unlink("development_history")
                .map_err(|e| e.to_string())?;
        }
        let group = file
            .create_group("development_history")
            .map_err(|e| e.to_string())?;
        let objects = group.create_group("objects").map_err(|e| e.to_string())?;
        let _scope = scope(Context::Write(Writer {
            group: objects,
            objects: HashMap::new(),
        }))?;
        let bytes = rmp_serde::to_vec_named(value).map_err(|e| e.to_string())?;
        group
            .new_dataset_builder()
            .with_data(&bytes)
            .deflate(1)
            .create("root")
            .map_err(|e| e.to_string())?;
        Ok(())
    }
    pub(crate) fn load<T: DeserializeOwned>(file: &hdf5::File) -> Result<T, String> {
        let group = file
            .group("development_history")
            .map_err(|e| e.to_string())?;
        let bytes = group
            .dataset("root")
            .and_then(|d| d.read_raw::<u8>())
            .map_err(|e| e.to_string())?;
        let objects = group.group("objects").map_err(|e| e.to_string())?;
        let _scope = scope(Context::Read(Reader {
            group: objects,
            objects: HashMap::new(),
            decoding: HashSet::new(),
        }))?;
        rmp_serde::from_slice(&bytes).map_err(|e| e.to_string())
    }
}
#[cfg(debug_assertions)]
pub(crate) use graph::{load, save};
pub(crate) mod arc {
    use super::*;
    pub fn serialize<T: Serialize + 'static, S: Serializer>(
        value: &Arc<T>,
        serializer: S,
    ) -> Result<S::Ok, S::Error> {
        #[cfg(debug_assertions)]
        if graph::active() {
            return graph::put_arc(value)
                .map_err(serde::ser::Error::custom)?
                .serialize(serializer);
        }
        value.serialize(serializer)
    }
    pub fn deserialize<'de, T: DeserializeOwned + 'static, D: Deserializer<'de>>(
        deserializer: D,
    ) -> Result<Arc<T>, D::Error> {
        #[cfg(debug_assertions)]
        if graph::active() {
            return graph::get_arc(u64::deserialize(deserializer)?)
                .map_err(serde::de::Error::custom);
        }
        Arc::<T>::deserialize(deserializer)
    }
}
pub(crate) mod optional_arc {
    use super::*;
    pub fn serialize<T: Serialize + 'static, S: Serializer>(
        value: &Option<Arc<T>>,
        serializer: S,
    ) -> Result<S::Ok, S::Error> {
        #[cfg(debug_assertions)]
        if graph::active() {
            return value
                .as_ref()
                .map(graph::put_arc)
                .transpose()
                .map_err(serde::ser::Error::custom)?
                .serialize(serializer);
        }
        value.serialize(serializer)
    }
    pub fn deserialize<'de, T: DeserializeOwned + 'static, D: Deserializer<'de>>(
        deserializer: D,
    ) -> Result<Option<Arc<T>>, D::Error> {
        #[cfg(debug_assertions)]
        if graph::active() {
            return Option::<u64>::deserialize(deserializer)?
                .map(graph::get_arc)
                .transpose()
                .map_err(serde::de::Error::custom);
        }
        Option::<Arc<T>>::deserialize(deserializer)
    }
}
pub(crate) mod vec_arc {
    use super::*;
    pub fn serialize<T: Serialize + 'static, S: Serializer>(
        value: &[Arc<T>],
        serializer: S,
    ) -> Result<S::Ok, S::Error> {
        #[cfg(debug_assertions)]
        if graph::active() {
            return value
                .iter()
                .map(graph::put_arc)
                .collect::<Result<Vec<_>, _>>()
                .map_err(serde::ser::Error::custom)?
                .serialize(serializer);
        }
        value.serialize(serializer)
    }
    pub fn deserialize<'de, T: DeserializeOwned + 'static, D: Deserializer<'de>>(
        deserializer: D,
    ) -> Result<Vec<Arc<T>>, D::Error> {
        #[cfg(debug_assertions)]
        if graph::active() {
            return Vec::<u64>::deserialize(deserializer)?
                .into_iter()
                .map(graph::get_arc)
                .collect::<Result<_, _>>()
                .map_err(serde::de::Error::custom);
        }
        Vec::<Arc<T>>::deserialize(deserializer)
    }
}

#[cfg(all(test, debug_assertions))]
mod tests {
    use super::*;
    #[derive(Serialize, Deserialize)]
    struct Shared {
        #[serde(with = "super::arc")]
        a: Arc<Vec<f64>>,
        #[serde(with = "super::arc")]
        b: Arc<Vec<f64>>,
    }
    #[test]
    fn shared_arrays_are_stored_once_and_retain_all_float_bits_and_arc_identity() {
        let tmp = tempfile::NamedTempFile::new().unwrap();
        let file = hdf5::File::create(tmp.path()).unwrap();
        let a = Arc::new(vec![
            f64::NAN,
            f64::INFINITY,
            f64::NEG_INFINITY,
            -0.0,
            1.2345678901234567,
        ]);
        save(
            &file,
            &Shared {
                a: a.clone(),
                b: a.clone(),
            },
        )
        .unwrap();
        assert_eq!(
            file.group("development_history/objects")
                .unwrap()
                .member_names()
                .unwrap()
                .len(),
            1
        );
        let restored: Shared = load(&file).unwrap();
        assert!(Arc::ptr_eq(&restored.a, &restored.b));
        assert_eq!(
            a.iter().map(|v| v.to_bits()).collect::<Vec<_>>(),
            restored.a.iter().map(|v| v.to_bits()).collect::<Vec<_>>()
        );
        file.group("development_history/objects/0")
            .unwrap()
            .unlink("kind")
            .unwrap();
        assert!(load::<Shared>(&file).is_err());
        // A failed transfer cannot leave later ordinary geometry/project JSON in graph mode.
        let ordinary = serde_json::to_value(Shared {
            a: Arc::new(vec![1.]),
            b: Arc::new(vec![2.]),
        })
        .unwrap();
        assert_eq!(ordinary["a"], serde_json::json!([1.]));
    }
}
