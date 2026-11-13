//! Application-wide CPU budget and reusable execution pools. Session commands
//! stay on their owner thread; only Send-safe numerical work enters Rayon.
use rayon::ThreadPool;
use serde_json::{Value, json};
use std::{
    cell::RefCell,
    collections::HashMap,
    sync::{Arc, Mutex, OnceLock, Weak},
};

#[cfg(target_os = "macos")]
fn performance_cores() -> Option<usize> {
    let mut count = 0u32;
    let mut size = std::mem::size_of_val(&count);
    // SAFETY: the name is a terminated constant string; count/size are writable
    // with matching lengths, and null newp makes this a read-only system query.
    let status = unsafe {
        libc::sysctlbyname(
            c"hw.perflevel0.physicalcpu".as_ptr(),
            (&mut count as *mut u32).cast(),
            &mut size,
            std::ptr::null_mut(),
            0,
        )
    };
    (status == 0 && size == std::mem::size_of_val(&count) && count > 0).then_some(count as usize)
}

#[cfg(not(target_os = "macos"))]
fn performance_cores() -> Option<usize> {
    None
}

fn automatic_workers(available: usize, performance: Option<usize>) -> usize {
    performance
        .filter(|&n| n > 0)
        .unwrap_or(available)
        .min(available)
        .saturating_sub(2)
        .max(1)
}

thread_local! {
    static ACTIVE: RefCell<Option<Arc<ThreadPool>>> = const { RefCell::new(None) };
}

pub(crate) fn available() -> usize {
    std::thread::available_parallelism().map_or(1, usize::from)
}
pub(crate) fn initial() -> Option<usize> {
    [
        "DIOPTAS_WORKERS",
        "DIOPTAS_INTEGRATION_THREADS",
        "DIOPTAS_BACKGROUND_WORKERS",
    ]
    .iter()
    .find_map(|name| {
        std::env::var(name)
            .ok()
            .and_then(|s| s.parse::<usize>().ok())
            .filter(|&n| n > 0)
    })
    .map(|n| n.min(available()))
}
pub(crate) fn effective(requested: Option<usize>) -> usize {
    requested
        .unwrap_or_else(|| automatic_workers(available(), performance_cores()))
        .clamp(1, available())
}
pub(crate) fn metadata(requested: Option<usize>) -> Value {
    json!({"requested":requested,"effective":effective(requested),"available":available(),
        "automatic":effective(None)})
}
pub(crate) fn pool(requested: Option<usize>) -> Result<Arc<ThreadPool>, String> {
    static POOLS: OnceLock<Mutex<HashMap<usize, Weak<ThreadPool>>>> = OnceLock::new();
    let threads = effective(requested);
    let mut pools = POOLS.get_or_init(Mutex::default).lock().unwrap();
    if let Some(pool) = pools.get(&threads).and_then(Weak::upgrade) {
        return Ok(pool);
    }
    let pool = Arc::new(
        rayon::ThreadPoolBuilder::new()
            .num_threads(threads)
            .thread_name(|i| format!("dioptas-worker-{i}"))
            .build()
            .map_err(|e| format!("Cannot start processing workers: {e}"))?,
    );
    pools.insert(threads, Arc::downgrade(&pool));
    Ok(pool)
}
pub(crate) fn current() -> Arc<ThreadPool> {
    ACTIVE
        .with(|active| active.borrow().clone())
        .unwrap_or_else(|| {
            static DEFAULT: OnceLock<Arc<ThreadPool>> = OnceLock::new();
            DEFAULT
                .get_or_init(|| pool(initial()).expect("Cannot start processing pool"))
                .clone()
        })
}
pub(crate) fn enter<R>(pool: Arc<ThreadPool>, work: impl FnOnce() -> R) -> R {
    struct Restore(Option<Arc<ThreadPool>>);
    impl Drop for Restore {
        fn drop(&mut self) {
            ACTIVE.with(|active| {
                active.replace(self.0.take());
            });
        }
    }
    let _restore = Restore(ACTIVE.with(|active| active.replace(Some(pool))));
    work()
}
pub(crate) fn install<R: Send>(work: impl FnOnce() -> R + Send) -> R {
    if rayon::current_thread_index().is_some() {
        work()
    } else {
        current().install(work)
    }
}
pub(crate) fn threads() -> usize {
    if rayon::current_thread_index().is_some() {
        rayon::current_num_threads()
    } else {
        current().current_num_threads()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn automatic_workers_respect_hybrid_cpus_and_available_capacity() {
        assert_eq!(automatic_workers(14, Some(10)), 8);
        assert_eq!(automatic_workers(4, Some(10)), 2);
        assert_eq!(automatic_workers(8, None), 6);
        assert_eq!(automatic_workers(1, Some(1)), 1);
        assert_eq!(automatic_workers(1, None), 1);
        assert_eq!(automatic_workers(8, Some(0)), 6);
    }
    #[test]
    fn shared_pool_is_reused_and_nested_work_honors_the_selected_budget() {
        let a = pool(Some(1)).unwrap();
        let b = pool(Some(1)).unwrap();
        assert!(Arc::ptr_eq(&a, &b));
        enter(a, || install(|| assert_eq!(threads(), 1)));
        let count = available().min(4);
        enter(pool(Some(count)).unwrap(), || {
            install(|| assert_eq!(threads(), count))
        });
    }
}
