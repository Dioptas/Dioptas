// Generated from command_payload_schema.json; do not edit by hand.

use serde::Deserialize;
use serde_json::Value;

use super::PayloadCoverage;

#[derive(Clone, Copy, Debug, Deserialize, serde::Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
#[allow(dead_code)]
pub enum FileOrder {
    Number,
    Time,
}

#[derive(Clone, Copy, Debug, Deserialize, serde::Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
#[allow(dead_code)]
pub enum TransferSource {
    Original,
    Response,
}

#[derive(Clone, Copy, Debug, Deserialize, serde::Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
#[allow(dead_code)]
pub enum ConfigurationTarget {
    File,
    Folder,
}

#[derive(Clone, Copy, Debug, Deserialize, serde::Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
#[allow(dead_code)]
pub enum ConfigurationScope {
    Active,
    All,
}

#[derive(Clone, Copy, Debug, Deserialize, serde::Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
#[allow(dead_code)]
pub enum ResponseDisposition {
    Applied,
    Cancelled,
    Deferred,
    Failed,
}

#[derive(Clone, Copy, Debug, Deserialize, serde::Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
#[allow(dead_code)]
pub enum DecisionKind {
    Hdf5Source,
    ImageChange,
    CalibrationChange,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
#[allow(dead_code)]
pub struct RequestedProducts {
    pub cake: bool,
    pub rings: Option<bool>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct NativeTransportMetadataFields {
    pub requested_products: Option<RequestedProducts>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct PixelPayloadFields {
    pub x: Option<f64>,
    pub y: Option<f64>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct PickPeakPayloadFields {
    pub x: Option<f64>,
    pub y: Option<f64>,
    pub ring: Option<f64>,
    pub automatic: Option<bool>,
    pub search_size: Option<f64>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct ImageSourcePayloadFields<'a> {
    pub dataset: Option<&'a str>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct FrameNavigationPayloadFields {
    pub frame: Option<f64>,
    pub direction: Option<f64>,
    pub step: Option<f64>,
    pub mode: Option<FileOrder>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct TransferPayloadFields<'a> {
    pub source: Option<TransferSource>,
    pub path: Option<&'a str>,
    pub enabled: Option<bool>,
    pub reset: Option<bool>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct FlatFieldPayloadFields<'a> {
    pub path: Option<&'a str>,
    pub enabled: Option<bool>,
    pub reset: Option<bool>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct ImageBackgroundPayloadFields<'a> {
    pub path: Option<&'a str>,
    pub reset: Option<bool>,
    pub scale: Option<f64>,
    pub offset: Option<f64>,
    pub poisson: Option<bool>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct CombinationPayloadFields {
    pub patterns: Option<bool>,
    pub cakes: Option<bool>,
    pub factor: Option<f64>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct ConfigurationSelectPayloadFields {
    pub index: Option<f64>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct ConfigurationRenamePayloadFields<'a> {
    pub name: Option<&'a str>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct ConfigurationRemovePayloadFields {
    pub index: Option<f64>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct EmptyPayloadFields {}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct ConfigurationNavigationPayloadFields {
    pub target: Option<ConfigurationTarget>,
    pub direction: Option<f64>,
    pub step: Option<f64>,
    pub number_position: Option<f64>,
    pub mec: Option<bool>,
    pub scope: Option<ConfigurationScope>,
    pub folder_number_position: Option<f64>,
    pub folder_filename_position: Option<f64>,
    pub folder_filename_step: Option<f64>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct ProcessingWorkersPayloadFields {
    pub workers: Option<f64>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct CakeProfilePayloadFields<'a> {
    pub two_theta: Option<f64>,
    pub bins: Option<f64>,
    pub shift: Option<f64>,
    pub path: Option<&'a str>,
    pub directory: Option<&'a str>,
    pub suggested_name: Option<&'a str>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct Hdf5CompanionPayloadFields<'a> {
    pub directory: Option<&'a str>,
}

fn fields<'a, T: Deserialize<'a>>(payload: &'a Value) -> Result<(), String> {
    T::deserialize(payload)
        .map(|_| ())
        .map_err(|error| error.to_string())
}

pub fn validate_fields(action: &str, payload: &Value) -> Result<PayloadCoverage, String> {
    match action {
        "pixel" => fields::<PixelPayloadFields>(payload)?,
        "pick_peak" => fields::<PickPeakPayloadFields>(payload)?,
        "select_image_source" => fields::<ImageSourcePayloadFields<'_>>(payload)?,
        "integration_navigation" => fields::<FrameNavigationPayloadFields>(payload)?,
        "integration_transfer" => fields::<TransferPayloadFields<'_>>(payload)?,
        "integration_flat_field" => fields::<FlatFieldPayloadFields<'_>>(payload)?,
        "integration_image_background" => fields::<ImageBackgroundPayloadFields<'_>>(payload)?,
        "combination_settings" => fields::<CombinationPayloadFields>(payload)?,
        "configuration_select" => fields::<ConfigurationSelectPayloadFields>(payload)?,
        "configuration_navigation" => fields::<ConfigurationNavigationPayloadFields>(payload)?,
        "processing_workers" => fields::<ProcessingWorkersPayloadFields>(payload)?,
        "cake_profile" => fields::<CakeProfilePayloadFields<'_>>(payload)?,
        "save_cake_profile" => fields::<CakeProfilePayloadFields<'_>>(payload)?,
        "choose_hdf5_companion" => fields::<Hdf5CompanionPayloadFields<'_>>(payload)?,
        "configuration" => {
            match payload["operation"].as_str().unwrap_or("select") {
                "select" => fields::<ConfigurationSelectPayloadFields>(payload)?,
                "add" => fields::<EmptyPayloadFields>(payload)?,
                "duplicate" => fields::<EmptyPayloadFields>(payload)?,
                "rename" => fields::<ConfigurationRenamePayloadFields<'_>>(payload)?,
                "remove" => fields::<ConfigurationRemovePayloadFields>(payload)?,
                _ => (), // Preserve the handler's unsupported-operation error.
            }
        }
        _ => return Ok(PayloadCoverage::Legacy),
    }
    Ok(PayloadCoverage::TypedFields)
}
