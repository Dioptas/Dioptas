//! Shared host/processor execution policy. Scientific payloads remain owned by
//! the processor; adding a command that can load or recalculate data belongs in
//! this registry so progress, cancellation and host serialization stay aligned.

/// Includes the terminating newline of the JSON request frame.
pub const MAX_REQUEST_BYTES: usize = 16 * 1024 * 1024;
pub const REQUEST_SIZE_ERROR: &str =
    "Processing request exceeds 16 MiB. Reduce the export size or number of files and try again.";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CommandExecution {
    /// Must bypass ordinary scientific work, including a pending worker swap.
    OutOfBand,
    /// Owns a Control for the entire command, including queued cancellation.
    Cancellable,
    /// Short metadata/readout work must not restart the progress indicator.
    Ordinary,
}

pub fn execution(action: &str) -> CommandExecution {
    match action {
        "progress" | "cancel_refinement" => CommandExecution::OutOfBand,
        "calibrate"
        | "pick_peak"
        | "calibration_setup"
        | "image_transform"
        | "mask_edit"
        | "mask_stroke"
        | "clear_mask"
        | "undo_mask"
        | "redo_mask"
        | "mask_plugin"
        | "example"
        | "open_image"
        | "next_image"
        | "select_image_source"
        | "integrate"
        | "open_calibration"
        | "reset_calibration"
        | "manual_geometry"
        | "detector_file"
        | "distortion_file"
        | "settings"
        | "integration_settings"
        | "integration_navigation"
        | "integration_autoprocess_poll"
        | "integration_roi"
        | "integration_background"
        | "integration_clear_background"
        | "undo_calibration"
        | "redo_calibration"
        | "batch_unit"
        | "integration_image_background"
        | "integration_flat_field"
        | "integration_transfer"
        | "integration_correction"
        | "integration_correction_preview"
        | "integration_overlay"
        | "integration_open_pattern"
        | "integration_pattern_navigation"
        | "integration_phase"
        | "integration_phase_files"
        | "integration_phase_list"
        | "batch_load"
        | "batch_load_data"
        | "batch_open"
        | "batch_select"
        | "batch_background_extract"
        | "batch_background_from_pattern"
        | "batch_folder"
        | "integration_batch"
        | "batch_folder_step"
        | "map_load"
        | "map_folder"
        | "map_batch"
        | "map_select"
        | "map_mask"
        | "map_poll"
        | "process_image_batch"
        | "open_project"
        | "save_project"
        | "recovery_checkpoint"
        | "recovery_restore"
        | "configuration"
        | "configuration_select"
        | "configuration_navigation"
        | "combination_settings"
        | "save_combined_pattern"
        | "display_products" => CommandExecution::Cancellable,
        _ => CommandExecution::Ordinary,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn loading_and_processing_entry_points_share_cancellation_policy() {
        for action in [
            "integration_transfer",
            "integration_flat_field",
            "select_image_source",
            "integration_navigation",
            "integration_autoprocess_poll",
            "configuration_navigation",
            "configuration_select",
            "combination_settings",
            "mask_stroke",
            "map_select",
            "batch_select",
        ] {
            assert_eq!(execution(action), CommandExecution::Cancellable, "{action}");
        }
        for action in [
            "state",
            "pixel",
            "batch_snapshot",
            "map_snapshot",
            "unknown",
        ] {
            assert_eq!(execution(action), CommandExecution::Ordinary, "{action}");
        }
        for action in ["progress", "cancel_refinement"] {
            assert_eq!(execution(action), CommandExecution::OutOfBand, "{action}");
        }
    }
}
