//! The boundary shared by the Tauri host and the native processor: which
//! commands may run out of band or be cancelled, and the structural types of
//! the JSON metadata that crosses the stdio connection.
pub mod command_contract;
pub mod wire_contract;
