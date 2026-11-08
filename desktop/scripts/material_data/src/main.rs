//! Explicit regeneration of the attenuation-only subset. Never run at app startup.
use sha2::{Digest, Sha256};
use std::{fs, path::Path};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let output = std::env::args()
        .nth(1)
        .ok_or("Pass the backend/data output directory")?;
    let db = xraydb::XrayDb::try_new()?;
    let full = postcard::to_allocvec(db.raw())?;
    let mut subset: xraydb_data::XrayDatabase = postcard::from_bytes(&full)?;
    subset.xray_levels.clear();
    subset.xray_transitions.clear();
    subset.coster_kronig.clear();
    subset.chantler.clear();
    subset.waasmaier.clear();
    subset.compton_energies.incident.clear();
    subset.compton_energies.xray_90deg.clear();
    subset.compton_energies.xray_mean.clear();
    subset.compton_energies.electron_mean.clear();
    subset.keski_rahkonen_krause.clear();
    subset.krause_oliver.clear();
    subset.corelevel_widths.clear();
    subset.ionization_potentials.clear();
    let bytes = postcard::to_allocvec(&subset)?;
    let metadata = serde_json::json!({
        "source":"https://github.com/Ameyanagi/xraydb-rs", "crate_version":"0.4.1",
        "upstream_data_version": db.data_version(), "data_license":"CC0-1.0 (XrayDB)",
        "full_postcard_sha256":format!("{:x}", Sha256::digest(&full)),
        "subset_sha256":format!("{:x}",Sha256::digest(&bytes)), "subset_bytes":bytes.len(),
        "elements":subset.elements.len(), "photoabsorption_rows":subset.photoabsorption.len(),
        "scattering_rows":subset.scattering.len(),
        "retained_tables":["version","elements","photoabsorption","scattering"],
        "encoding":"xraydb-data 0.4.1 postcard; all retained f64 values unchanged"
    });
    fs::create_dir_all(&output)?;
    fs::write(Path::new(&output).join("attenuation.bin"), &bytes)?;
    fs::write(
        Path::new(&output).join("attenuation.json"),
        format!("{}\n", serde_json::to_string_pretty(&metadata)?),
    )?;
    println!("{}", serde_json::to_string_pretty(&metadata)?);
    Ok(())
}
