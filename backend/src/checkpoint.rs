//! Atomic command rollback. Immutable detector/products/history are shared;
//! capturing a command does not copy full detector frames or lookup plans.
use super::*;
macro_rules! checkpoint {
    ($($(#[$meta:meta])* $name:ident:$kind:ty),* $(,)?)=>{
        #[derive(Clone)]
        pub(super) struct Checkpoint { $($(#[$meta])* pub(super) $name:$kind),* }
        impl Session {
            pub(super) fn checkpoint(&self)->Checkpoint {Checkpoint{$($(#[$meta])* $name:self.$name.clone()),*}}
            pub(super) fn restore_checkpoint(&mut self,c:Checkpoint){$($(#[$meta])* {self.$name=c.$name;})*}
        }
    }
}
checkpoint! {
    combination:combination::State,
    settings:Settings,image:Option<Image>,image_raster:Option<Raster>,mask:Arc<Vec<u8>>,
    mask_filename:Option<String>, mask_mode:bool,
    processed_raster:Option<Raster>,processed_values:Option<Arc<Vec<f64>>>,scientific_generation:u64,processing:crate::processing::Processing,
    patterns:crate::pattern::Patterns,
    phases:crate::phases::Phases,
    batch:Option<crate::series::Series>,image_batch_mode:String,
    scan:Option<crate::scan::Scan>,
    files:file_workflow::Files,
    integration_history:integration_history::IntegrationHistory,
    inspection:Option<linked::Inspection>,
    effective_mask:Arc<Vec<u8>>,plugins:Plugins,image_generation:u64,mask_raster:Option<Raster>,
    undo:Vec<MaskSnapshot>,redo:Vec<MaskSnapshot>,revision:u64,elapsed_ms:Option<f64>,
    pattern:Option<Arc<Value>>,cake:Option<Raster>,cake_values:Option<Arc<Vec<f64>>>,
    calibration:Calibration,workflow:Workflow,calibration_history:History,
    #[cfg(feature="dioptrin")]ring_cache:std::cell::RefCell<Option<calibration::RingCache>>,
    #[cfg(feature="dioptrin")]sigma:Option<Vec<f64>>,
    #[cfg(feature="dioptrin")]prepared:Option<crate::integration::Prepared>,
}
