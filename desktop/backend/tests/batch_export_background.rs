//! Independent Qt-reference readback of exports after the integrated background workflow.
use dioptas_backend::{
    Session,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::{path::Path, str::FromStr};
fn call(s: &mut Session, action: &str, payload: Value) -> Reply {
    let reply = s.invoke(&Request {
        id: 1,
        action: action.into(),
        payload,
        cached_buffers: vec![],
    });
    assert_eq!(reply.result["ok"], true, "{action}: {}", reply.result);
    reply
}
fn session() -> Session {
    Session::new(Path::new(env!("CARGO_MANIFEST_DIR")).join("../.."))
}
fn rows(path: &Path, extension: &str) -> Vec<Vec<f64>> {
    let text = std::fs::read_to_string(path).unwrap();
    let skip = match extension {
        "chi" => 4,
        "fxye" => text.lines().position(|s| s.starts_with("BANK ")).unwrap() + 1,
        _ => 0,
    };
    text.lines()
        .skip(skip)
        .filter(|s| !s.starts_with('#') && !s.is_empty())
        .map(|s| s.split_whitespace().map(|v| v.parse().unwrap()).collect())
        .collect()
}
fn near(actual: f64, expected: f64) {
    assert!(
        (actual - expected).abs() < 2e-8 * expected.abs().max(1.),
        "{actual} != {expected}"
    );
}
#[test]
fn integrated_background_normalization_and_cut_export_full_f64_data_without_state_changes() {
    let references: Value =
        serde_json::from_str(include_str!("fixtures/batch_background_qt.json")).unwrap();
    for (case, refit_normalized) in [(0, false), (0, true), (2, false), (2, true)] {
        let reference = &references["cases"][case];
        let unit = reference["unit"].as_str().unwrap();
        let x: Vec<f64> = serde_json::from_value(reference["x"].clone()).unwrap();
        let data: Vec<f64> = serde_json::from_value(reference["data"].clone()).unwrap();
        let background: Vec<f64> = serde_json::from_value(reference["background"].clone()).unwrap();
        let n = x.len();
        let temp = tempfile::tempdir().unwrap();
        let input = temp.path().join("garnet_processed_042.nxs");
        {
            let file = hdf5::File::create(&input).unwrap();
            file.new_dataset::<f64>()
                .shape([3, n])
                .create("data")
                .unwrap()
                .write_raw(&data)
                .unwrap();
            let axis = file
                .new_dataset_builder()
                .with_data(&x)
                .create("binning")
                .unwrap();
            axis.new_attr::<hdf5::types::VarLenUnicode>()
                .shape(())
                .create("radial_unit")
                .unwrap()
                .write_scalar(&hdf5::types::VarLenUnicode::from_str(unit).unwrap())
                .unwrap();
            let sigma: Vec<_> = data.iter().map(|v| v.sqrt()).collect();
            file.new_dataset::<f64>()
                .shape([3, n])
                .create("counting_std")
                .unwrap()
                .write_raw(&sigma)
                .unwrap();
        }
        let mut s = session();
        call(&mut s, "batch_open", json!({"path":input}));
        call(
            &mut s,
            "batch_background_extract",
            json!({"parameters":reference["parameters"]}),
        );
        let (low, high) = (x[10].min(x[80]), x[10].max(x[80]));
        call(
            &mut s,
            "batch_background_display",
            json!({"range":[low,high],"unit":unit,"subtract":true,"cut":true}),
        );
        call(
            &mut s,
            "batch_normalization_settings",
            json!({"start":4,"stop":69,"reference":1}),
        );
        call(&mut s, "batch_normalize", json!({"enabled":true}));
        call(&mut s, "batch_select", json!({"index":2}));
        // Qt fits the current intensity scale. Validate both operation orders
        // against the corresponding independent Qt reference, not an assumed
        // scale-invariant fit.
        if refit_normalized {
            call(
                &mut s,
                "batch_background_extract",
                json!({"parameters":reference["parameters"]}),
            );
        }
        let before = call(&mut s, "batch_snapshot", json!({})).result["batch"].clone();
        assert_eq!(before["exportBaseName"], "garnet_processed_042");
        assert_eq!(before["sourceBins"], json!([10, 81]));
        assert_eq!(before["normalized"], true);
        let means: Vec<_> = data
            .chunks_exact(n)
            .map(|row| row[4..70].iter().sum::<f64>() / 66.)
            .collect();
        let factors: Vec<_> = means.iter().map(|mean| means[1] / mean).collect();
        let expected_data: Vec<_> = data
            .iter()
            .enumerate()
            .map(|(i, y)| y * factors[i / n])
            .collect();
        let expected_bg: Vec<f64> = if refit_normalized {
            serde_json::from_value(reference["normalized_background"].clone()).unwrap()
        } else {
            background
                .iter()
                .enumerate()
                .map(|(i, y)| y * factors[i / n])
                .collect()
        };
        let reference_file = temp.path().join("native_reference.h5");
        call(
            &mut s,
            "integration_save_batch",
            json!({"path":reference_file}),
        );
        let native_background: Vec<f64> = hdf5::File::open(reference_file)
            .unwrap()
            .dataset("processed/process/bkg")
            .unwrap()
            .read_raw()
            .unwrap();
        for (&actual, &expected) in native_background.iter().zip(&expected_bg) {
            assert!(
                (actual - expected).abs() < 2e-9 * expected.abs().max(1.),
                "Qt-reference fit mismatch: {actual} != {expected}"
            );
        }
        for extension in ["xy", "chi", "dat", "fxye"] {
            let output_unit = if extension == "fxye" && unit == "d_A" {
                "q_A^-1"
            } else {
                unit
            };
            let template = temp.path().join(format!("export.{extension}"));
            let result = call(
                &mut s,
                "integration_save_batch",
                json!({"path":template,"unit":output_unit}),
            );
            assert_eq!(result.result["savedPaths"].as_array().unwrap().len(), 6);
            for (row, &factor) in factors.iter().enumerate() {
                let file = temp.path().join(format!("export_{row:03}.{extension}"));
                let original = rows(&file, extension);
                let subtracted = rows(
                    &temp
                        .path()
                        .join(format!("bkg_subtracted/export_{row:03}.{extension}")),
                    extension,
                );
                assert_eq!(
                    original.len(),
                    n,
                    "Display cut must not restrict numerical exports"
                );
                for col in 0..n {
                    let i = row * n + col;
                    let radial = if unit == output_unit {
                        x[col]
                    } else {
                        std::f64::consts::TAU / x[col]
                    };
                    let radial_factor = if extension == "fxye" && output_unit != "q_A^-1" {
                        100.
                    } else {
                        1.
                    };
                    near(original[col][0], radial * radial_factor);
                    near(original[col][1], expected_data[i]);
                    assert_eq!(subtracted[col][1], expected_data[i] - native_background[i]);
                    if extension == "fxye" {
                        near(original[col][2], data[i].sqrt() * factor);
                        assert_eq!(original[col][2], subtracted[col][2]);
                    }
                }
                let text = std::fs::read_to_string(file).unwrap();
                let header = text
                    .lines()
                    .find_map(|l| l.strip_prefix("# batch: "))
                    .unwrap();
                let metadata: Value = serde_json::from_str(header).unwrap();
                assert_eq!(metadata["background"], before["backgroundState"]);
                assert_eq!(metadata["processed_source_stem"], "garnet_processed_042");
                assert_eq!(metadata["normalization_reference"], 1);
                assert_eq!(metadata["normalization_bins"], json!([4, 70]));
                assert_eq!(metadata["normalized"], true);
            }
        }
        for extension in ["h5", "nxs"] {
            let file = temp.path().join(format!("normalized.{extension}"));
            call(&mut s, "integration_save_batch", json!({"path":file}));
            let f = hdf5::File::open(&file).unwrap();
            let values: Vec<f64> = f
                .dataset("processed/result/data")
                .unwrap()
                .read_raw()
                .unwrap();
            let bg: Vec<f64> = f
                .dataset("processed/process/bkg")
                .unwrap()
                .read_raw()
                .unwrap();
            assert_eq!(values, expected_data);
            for (a, b) in bg.iter().zip(&expected_bg) {
                near(*a, *b);
            }
        }
        let csv = temp.path().join("normalized.csv");
        call(&mut s, "integration_save_batch", json!({"path":csv}));
        let mut reader = csv::Reader::from_path(csv).unwrap();
        let records: Vec<_> = reader.records().map(Result::unwrap).collect();
        assert_eq!(records.len(), 3 * n);
        for (i, record) in records.iter().enumerate() {
            let row = i % 3;
            let col = i / 3;
            assert_eq!(record[1].parse::<usize>().unwrap(), row);
            assert_eq!(
                record[2].parse::<f64>().unwrap(),
                expected_data[row * n + col]
            );
        }
        assert_eq!(
            call(&mut s, "batch_snapshot", json!({})).result["batch"],
            before
        );
        let project = temp.path().join("roundtrip.dio");
        call(&mut s, "save_project", json!({"path":project}));
        std::fs::remove_file(&input).unwrap();
        let mut restored = session();
        call(&mut restored, "open_project", json!({"path":project}));
        let reopened = call(&mut restored, "batch_snapshot", json!({})).result["batch"].clone();
        assert_eq!(reopened["exportBaseName"], "garnet_processed_042");
        assert_eq!(reopened["backgroundState"], before["backgroundState"]);
        assert_eq!(reopened["normalizationRange"], before["normalizationRange"]);
        let new_source = temp.path().join("renamed_processed.nxs");
        std::fs::copy(temp.path().join("normalized.nxs"), &new_source).unwrap();
        let reopened = call(
            &mut restored,
            "batch_load_data",
            json!({"paths":[new_source]}),
        );
        assert_eq!(
            reopened.result["batch"]["exportBaseName"],
            "renamed_processed"
        );
    }
}
