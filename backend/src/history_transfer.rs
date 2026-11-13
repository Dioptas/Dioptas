//! Shared-object graph for private session history checkpoints.
//! Binary numeric values retain NaNs/infinities, and shared planes/curves are
//! written once. Reconstructed Arc identity also preserves model comparisons.
use serde::{Deserialize, Deserializer, Serialize, Serializer, de::DeserializeOwned};
use std::sync::Arc;

mod graph {
    use super::*;
    use std::{
        any::{Any, TypeId, type_name},
        cell::RefCell,
        collections::{HashMap, HashSet},
    };

    const LIMIT: &str = "Session history exceeds its recovery budget";
    const MAX_OBJECTS: usize = 16_384;
    struct Budget {
        used: usize,
        maximum: usize,
        control: Arc<crate::control::Control>,
        failure: Option<String>,
    }
    impl Budget {
        fn charge(&mut self, count: usize) -> Result<(), String> {
            if let Err(error) = self.control.check() {
                return Err(self.fail(&error));
            }
            self.used = self
                .used
                .checked_add(count)
                .filter(|n| *n <= self.maximum)
                .ok_or_else(|| self.fail(LIMIT))?;
            Ok(())
        }
        fn fail(&mut self, error: &str) -> String {
            self.failure = Some(error.to_owned());
            error.to_owned()
        }
    }
    fn charge(count: usize) -> Result<(), String> {
        CONTEXT.with(|c| match c.borrow_mut().as_mut() {
            Some(Context::Write(w)) => w.budget.charge(count),
            Some(Context::Read(r)) => r.budget.charge(count),
            None => Err("Missing history budget.".into()),
        })
    }
    #[derive(Default)]
    struct Bytes(Vec<u8>);
    impl std::io::Write for Bytes {
        fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
            charge(bytes.len()).map_err(std::io::Error::other)?;
            self.0.extend_from_slice(bytes);
            Ok(bytes.len())
        }
        fn flush(&mut self) -> std::io::Result<()> {
            Ok(())
        }
    }
    fn encode<T: Serialize>(value: &T) -> Result<Vec<u8>, String> {
        let mut bytes = Bytes::default();
        value
            .serialize(&mut rmp_serde::Serializer::new(&mut bytes).with_struct_map())
            .map_err(|e| {
                CONTEXT.with(|c| match c.borrow().as_ref() {
                    Some(Context::Write(writer)) => writer
                        .budget
                        .failure
                        .clone()
                        .unwrap_or_else(|| e.to_string()),
                    _ => e.to_string(),
                })
            })?;
        Ok(bytes.0)
    }
    fn read_bytes(group: &hdf5::Group, name: &str) -> Result<Vec<u8>, String> {
        let data = group.dataset(name).map_err(|e| e.to_string())?;
        if data.ndim() != 1 || !data.dtype().map_err(|e| e.to_string())?.is::<u8>() {
            return Err("Invalid history byte dataset.".into());
        }
        charge(data.size())?;
        data.read_raw::<u8>().map_err(|e| e.to_string())
    }
    pub(crate) fn is_limit(error: &str) -> bool {
        error.contains(LIMIT)
    }

    struct Writer {
        group: hdf5::Group,
        objects: HashMap<(TypeId, usize), u64>,
        budget: Budget,
    }
    struct Reader {
        group: hdf5::Group,
        objects: HashMap<u64, Box<dyn Any>>,
        decoding: HashSet<u64>,
        budget: Budget,
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
            if writer.objects.len() >= MAX_OBJECTS && writer.budget.maximum != usize::MAX {
                return Err(writer.budget.fail(LIMIT));
            }
            let id = writer.objects.len() as u64;
            writer.objects.insert(key, id);
            Ok((id, writer.group.clone(), false))
        })?;
        if exists {
            return Ok(id);
        }
        let bytes = encode(value.as_ref())?;
        charge(type_name::<T>().len())?;
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
            if (reader.objects.len() >= MAX_OBJECTS && reader.budget.maximum != usize::MAX)
                || reader.decoding.len() >= 64
            {
                return Err(LIMIT.into());
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
        let kind = read_bytes(&entry, "kind")?;
        if kind != type_name::<T>().as_bytes() {
            return Err("History object type differs.".into());
        }
        let bytes = read_bytes(&entry, "data")?;
        let value = Arc::new(rmp_serde::from_slice::<T>(&bytes).map_err(|e| e.to_string())?);
        CONTEXT.with(|context| {
            if let Some(Context::Read(reader)) = context.borrow_mut().as_mut() {
                reader.decoding.remove(&id);
                reader.objects.insert(id, Box::new(value.clone()));
            }
        });
        Ok(value)
    }
    pub(crate) fn save_named<T: Serialize>(
        file: &hdf5::File,
        name: &str,
        value: &T,
        maximum: usize,
        control: Arc<crate::control::Control>,
    ) -> Result<(), String> {
        if file.link_exists(name) {
            file.unlink(name).map_err(|e| e.to_string())?;
        }
        let group = file.create_group(name).map_err(|e| e.to_string())?;
        let objects = group.create_group("objects").map_err(|e| e.to_string())?;
        let _scope = scope(Context::Write(Writer {
            group: objects,
            objects: HashMap::new(),
            budget: Budget {
                used: 0,
                maximum,
                control,
                failure: None,
            },
        }))?;
        let bytes = encode(value)?;
        group
            .new_dataset_builder()
            .with_data(&bytes)
            .deflate(1)
            .create("root")
            .map_err(|e| e.to_string())?;
        Ok(())
    }
    pub(crate) fn load_named<T: DeserializeOwned>(
        file: &hdf5::File,
        name: &str,
        maximum: usize,
        control: Arc<crate::control::Control>,
    ) -> Result<T, String> {
        let group = file.group(name).map_err(|e| e.to_string())?;
        let objects = group.group("objects").map_err(|e| e.to_string())?;
        let _scope = scope(Context::Read(Reader {
            group: objects,
            objects: HashMap::new(),
            decoding: HashSet::new(),
            budget: Budget {
                used: 0,
                maximum,
                control,
                failure: None,
            },
        }))?;
        let bytes = read_bytes(&group, "root")?;
        rmp_serde::from_slice(&bytes).map_err(|e| e.to_string())
    }
    #[cfg(debug_assertions)]
    pub(crate) fn save<T: Serialize>(file: &hdf5::File, value: &T) -> Result<(), String> {
        save_named(
            file,
            "development_history",
            value,
            usize::MAX,
            Arc::default(),
        )
    }
    #[cfg(debug_assertions)]
    pub(crate) fn load<T: DeserializeOwned>(file: &hdf5::File) -> Result<T, String> {
        load_named(file, "development_history", usize::MAX, Arc::default())
    }
}
pub(crate) use graph::{is_limit, load_named, save_named};
#[cfg(debug_assertions)]
pub(crate) use graph::{load, save};
pub(crate) mod arc {
    use super::*;
    pub fn serialize<T: Serialize + 'static, S: Serializer>(
        value: &Arc<T>,
        serializer: S,
    ) -> Result<S::Ok, S::Error> {
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

#[cfg(test)]
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
    fn recovery_graph_enforces_write_read_and_cancellation_budgets() {
        let tmp = tempfile::NamedTempFile::new().unwrap();
        let file = hdf5::File::create(tmp.path()).unwrap();
        let a = Arc::new(vec![1.0; 4096]);
        let value = Shared { a: a.clone(), b: a };
        let error = save_named(&file, "bounded", &value, 64, Arc::default()).unwrap_err();
        assert!(is_limit(&error), "{error}");
        save_named(&file, "bounded", &value, 128 * 1024, Arc::default()).unwrap();
        let error = load_named::<Shared>(&file, "bounded", 64, Arc::default())
            .err()
            .unwrap();
        assert!(is_limit(&error), "{error}");
        let control = Arc::new(crate::control::Control::default());
        control.cancel();
        let error = save_named(&file, "bounded", &value, 128 * 1024, control).unwrap_err();
        assert!(error.contains("Operation cancelled"), "{error}");
        assert!(!is_limit(&error));
        assert!(serde_json::to_value(&value).unwrap()["a"].is_array());
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
        save_named(
            &file,
            "development_history",
            &Shared {
                a: a.clone(),
                b: a.clone(),
            },
            usize::MAX,
            Arc::default(),
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
        let restored: Shared =
            load_named(&file, "development_history", usize::MAX, Arc::default()).unwrap();
        assert!(Arc::ptr_eq(&restored.a, &restored.b));
        assert_eq!(
            a.iter().map(|v| v.to_bits()).collect::<Vec<_>>(),
            restored.a.iter().map(|v| v.to_bits()).collect::<Vec<_>>()
        );
        file.group("development_history/objects/0")
            .unwrap()
            .unlink("kind")
            .unwrap();
        assert!(
            load_named::<Shared>(&file, "development_history", usize::MAX, Arc::default()).is_err()
        );
        // A failed transfer cannot leave later ordinary geometry/project JSON in graph mode.
        let ordinary = serde_json::to_value(Shared {
            a: Arc::new(vec![1.]),
            b: Arc::new(vec![2.]),
        })
        .unwrap();
        assert_eq!(ordinary["a"], serde_json::json!([1.]));
    }
}
