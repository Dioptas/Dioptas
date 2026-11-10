//! Stateless display adapter. No preview enters processing, history or projects.
use crate::{
    control::Control,
    display::{self, Raster},
    geometry::Geometry,
    image::Image,
    processing::Processing,
    protocol::Reply,
};
use serde_json::{Value, json};

pub(crate) fn preview(
    processing: &Processing,
    image: &Image,
    geometry: &Geometry,
    control: &Control,
    args: &Value,
) -> Result<Reply, String> {
    let kind = args["kind"]
        .as_str()
        .ok_or("Choose a correction to plot.")?;
    let (label, units) = match kind {
        "flat" => ("Mean-normalized flat-field response", "dimensionless"),
        "transfer" => ("Transfer response / original", "dimensionless"),
        "cbn" => ("cBN seat transmission", "dimensionless"),
        "oiadac" => ("Relative detector absorption efficiency", "dimensionless"),
        "plate" => ("Plate transmission", "dimensionless"),
        "slab" => ("Slab depth integral", "mm"),
        "cylinder" => (
            "Cylinder transmission (including enabled capillary wall)",
            "dimensionless",
        ),
        "sphere" => ("Sphere transmission", "dimensionless"),
        _ => return Err("Unsupported correction preview.".into()),
    };
    let mode = args["mode"].as_str().unwrap_or("percentile");
    if !["percentile", "minmax", "mean3std"].contains(&mode) {
        return Err("Unknown Auto levels mode.".into());
    }
    let percentile = args["percentile"].as_f64().unwrap_or(2.5);
    if !percentile.is_finite() || !(0.0..50.).contains(&percentile) {
        return Err("Invalid preview percentile.".into());
    }
    // Correction maps have no detector gap sentinel. Do not filter map values.
    let values = processing.preview_map(kind, image, geometry, control)?;
    control.check()?;
    if values.iter().any(|v| !v.is_finite() || *v <= 0.) {
        return Err("Correction preview is not finite and positive across this detector.".into());
    }
    let mut raster = Raster::image(&values, image.shape);
    raster.metadata["limits"] = json!(display::levels(
        &values,
        image.shape,
        mode,
        percentile,
        false
    ));
    raster.metadata["autoLevels"] =
        json!({"mode":mode,"percentile":percentile,"filter_gaps":false});
    Ok(Reply {
        result: json!({"ok":true,"correctionPreview":{
            "kind":kind,"label":label,"units":units,"convention":"divisor","raster":raster.metadata
        }}),
        buffers: vec![raster.buffer],
    })
}
