//! Experiment-owned DAC confinement, never part of an authored EoS record.
use crate::phases::Phases;
use std::sync::Arc;

#[derive(Clone, Copy, Debug, PartialEq, serde::Serialize, serde::Deserialize)]
#[serde(try_from = "f64", into = "f64")]
pub(crate) struct DacFraction(f64);

impl Default for DacFraction {
    fn default() -> Self {
        Self(0.25)
    }
}
impl TryFrom<f64> for DacFraction {
    type Error = String;
    fn try_from(value: f64) -> Result<Self, String> {
        if value.is_finite() && (0.0..1.0).contains(&value) {
            Ok(Self(value))
        } else {
            Err("The DAC thermal-pressure fraction must be finite and in [0, 1).".into())
        }
    }
}
impl From<DacFraction> for f64 {
    fn from(value: DacFraction) -> Self {
        value.0
    }
}
impl Phases {
    pub fn effective_dac_fraction(&self) -> Option<DacFraction> {
        self.cold_pressure.then_some(self.dac_fraction)
    }

    pub fn set_dac_thermal_pressure(
        &mut self,
        enabled: bool,
        fraction: DacFraction,
        wavelength: f64,
    ) -> Result<(), String> {
        // Stage every phase before publishing any setting or calculated position.
        let mut next = self.clone();
        next.cold_pressure = enabled;
        next.dac_fraction = fraction;
        for phase in &mut next.items {
            Arc::make_mut(phase).recalculate(wavelength, enabled.then_some(fraction), false)?;
        }
        *self = next;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn fractions_validate_commands_and_serialized_history() {
        for v in [-0.1, 1.0, f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
            assert!(DacFraction::try_from(v).is_err());
        }
        for v in [0.0, 0.25, 0.4, 0.999999] {
            let f = DacFraction::try_from(v).unwrap();
            assert_eq!(
                serde_json::from_value::<DacFraction>(serde_json::json!(v)).unwrap(),
                f
            );
        }
        assert!(serde_json::from_value::<DacFraction>(serde_json::json!(1.0)).is_err());
    }

    #[test]
    fn qt_phase_model_independent_numerical_reference() {
        use crate::phases::{self, Phases};
        use serde_json::{Value, json};
        let fixtures: Value =
            serde_json::from_str(include_str!("../tests/fixtures/dac-qt-reference.json")).unwrap();
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let mut checked = 0;
        let mut max_relative: f64 = 0.0;
        for case in fixtures["cases"].as_array().unwrap() {
            let doc = if let Some(path) = case["path"].as_str() {
                phases::read_file(&root.join(path)).unwrap()
            } else {
                case["document"].clone()
            };
            let reference = (!phases::records(&doc).is_empty()).then_some(0);
            let mut phases = Phases::default();
            phases
                .add(doc, String::new(), "file", reference, 0.5, 0.5, 0.31)
                .unwrap();
            let source_document = phases.items[0].document.clone();
            for sample in case["samples"].as_array().unwrap() {
                let fraction = DacFraction::try_from(sample["factor"].as_f64().unwrap()).unwrap();
                // Reset conditions on a staged phase, as the session command does.
                let phase = Arc::make_mut(&mut phases.items[0]);
                phase.pressure = sample["pressure"].as_f64().unwrap();
                phase.temperature = sample["temperature"].as_f64().unwrap();
                phases
                    .set_dac_thermal_pressure(sample["enabled"].as_bool().unwrap(), fraction, 0.31)
                    .unwrap();
                let phase = &phases.items[0];
                let scale = (phase.current_volume / phase.reference_volume()).cbrt();
                let a = crate::phase_crystal::cell(&phase.document)
                    .unwrap()
                    .a_angstrom
                    * scale;
                let d = phase.cell_spacing(&phase.reflections[0]) * scale;
                for (actual, key) in [(phase.current_volume, "volume"), (a, "a"), (d, "d")] {
                    let expected = sample[key].as_f64().unwrap();
                    max_relative =
                        max_relative.max((actual - expected).abs() / expected.abs().max(1.0));
                    assert!(
                        (actual - expected).abs() <= 2e-7 * expected.abs().max(1.),
                        "{} {sample} {key}: native {actual}, Qt {expected}",
                        case["id"]
                    );
                }
                assert_eq!(json!(phase.pressure), sample["pressure"]);
                assert_eq!(json!(phase.temperature), sample["temperature"]);
                assert!(!phase.modified);
                assert_eq!(phase.document, source_document);
                checked += 1;
            }
        }
        assert_eq!(checked, 398);
        println!("Qt PhaseModel: {checked} states; maximum relative difference {max_relative:e}");
    }
}
