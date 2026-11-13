//! Structure-independent scan scaling and exact symmetry-family diagnostics.
use super::*;
use phasesmith_workflows::space_group_search as symmetry;
impl Crystal {
    pub(super) fn scale(&mut self, control: &Control) -> Result<String, String> {
        control.check()?;
        let cell = self.cell()?;
        let info =
            phasesmith_io::space_group_by_number(i32::from(self.config.group)).map_err(err)?;
        let group = &info.space_group;
        // Validate the explicitly supplied symmetry against the actual selected metric.
        let catalogue = vec![symmetry::Hypothesis {
            number: info.number,
            symbol: info.hm_symbol.clone(),
            hall: info.hall_symbol.clone(),
            group: group.clone(),
        }];
        let raw: Vec<_> = self
            .reflections
            .iter()
            .filter(|r| r.usable())
            .map(|r| solution::Observation {
                hkl: r.hkl.map(|x| x as i32),
                intensity: r.intensity,
                sigma: r.sigma,
            })
            .collect();
        let assessment=symmetry::assess(&raw,cell,&catalogue,&symmetry::AssessmentOptions::default()).map_err(|e|format!("Supplied space group does not match the selected index setting/metric: {e}. Use P1 or enter the exact cell metric in Geometry."))?;
        let mut families: BTreeMap<[i32; 3], usize> = BTreeMap::new();
        let mut groups = Vec::new();
        let mut ids = Vec::new();
        for (i, row) in self
            .reflections
            .iter()
            .enumerate()
            .filter(|(_, r)| r.usable())
        {
            let key = group
                .reflection_orbit(row.hkl.map(|x| x as i32), true)
                .map_err(err)?[0];
            let next = families.len();
            groups.push(*families.entry(key).or_insert(next));
            ids.push(i);
        }
        let mut rows: Vec<_> = ids.iter().map(|&i| self.reflections[i].clone()).collect();
        let native_profile = self.config.integration_method == "profile";
        if native_profile && self.config.scan_scaling {
            return Err("The native profile recipe already applies family scaling; disable the separate log-linear scan scale.".into());
        }
        if native_profile && self.profile_report.is_null() {
            return Err("Rerun Intensities to prepare the native profile reduction.".into());
        }
        let mut fit_summary = if native_profile {
            json!({"applied":true,"model":"PhaseSmith native per-frame/detector/ray family scaling","recipe":"orthorhombic-v1","errorFloor":self.profile_report["errorFloor"]})
        } else {
            json!({"applied":false,"model":"none"})
        };
        if self.config.scan_scaling && !native_profile {
            let intensity: Vec<_> = rows.iter().map(|r| r.intensity).collect();
            let sigma: Vec<_> = rows.iter().map(|r| r.sigma).collect();
            let omega: Vec<_> = rows.iter().map(|r| r.omega).collect();
            let range = [
                self.config.omega_start,
                self.config.omega_start + self.sources.len() as f64 * self.config.omega_step,
            ];
            let half = (range[1] - range[0]) / 2.;
            let middle = range[0] + half;
            let x: Vec<_> = omega.iter().map(|v| (v - middle) / half).collect();
            let training = vec![true; rows.len()];
            let fit=spots::scan_scaling::fit(&intensity,&sigma,&x,&groups,&training,spots::scan_scaling::Options{minimum_snr:5.,relative_error_floor:0.02,huber:2.5,max_iterations:50,tolerance:1e-8}).map_err(|e|format!("Scan scaling is not supported by the measured redundancy: {e}. Disable scan scaling to retain unscaled observations."))?;
            if !fit.converged {
                return Err("Scan scaling reached the iteration limit. Disable it or inspect repeated-family coverage before continuing.".into());
            }
            let applied = spots::scan_scaling::apply(
                &intensity,
                &sigma,
                &omega,
                range,
                fit.coefficient,
                fit.variance,
            )
            .map_err(err)?;
            for (r, v) in rows.iter_mut().zip(applied) {
                r.intensity = v[1];
                r.sigma = v[2];
                r.correction *= v[0];
            }
            fit_summary = json!({"applied":true,"model":"robust log-linear omega scale from repeated symmetry families","coefficient":fit.coefficient,"variance":fit.variance,"references":fit.reference_ids.len(),"iterations":fit.iterations,"converged":fit.converged,"uncertainty":"conditional counting sigma; shared scale uncertainty reported separately"});
        }
        let observations: Vec<_> = rows
            .iter()
            .map(|r| solution::Observation {
                hkl: r.hkl.map(|x| x as i32),
                intensity: r.intensity,
                sigma: r.sigma,
            })
            .collect();
        let merged = solution::prepare_data(&observations, cell, group).map_err(err)?;
        let mut grouped = vec![Vec::new(); families.len()];
        for (row, &family) in rows.iter().zip(&groups) {
            grouped[family].push(row);
        }
        let mut numerator = 0.;
        let mut denominator = 0.;
        let mut repeats = 0;
        let mut half_a = Vec::new();
        let mut half_b = Vec::new();
        for family in &grouped {
            if family.len() < 2 {
                continue;
            }
            repeats += 1;
            let weight: f64 = family.iter().map(|r| 1. / r.sigma.powi(2)).sum();
            let mean = family
                .iter()
                .map(|r| r.intensity / r.sigma.powi(2))
                .sum::<f64>()
                / weight;
            for r in family {
                numerator += (r.intensity - mean).abs();
                denominator += r.intensity.abs();
            }
            let halves = |parity: usize| {
                let rows: Vec<_> = family
                    .iter()
                    .enumerate()
                    .filter(|(i, _)| i % 2 == parity)
                    .map(|(_, r)| *r)
                    .collect();
                rows.iter()
                    .map(|r| r.intensity / r.sigma.powi(2))
                    .sum::<f64>()
                    / rows.iter().map(|r| 1. / r.sigma.powi(2)).sum::<f64>()
            };
            half_a.push(halves(0));
            half_b.push(halves(1));
        }
        let cc = if half_a.len() >= 10 {
            let ma = half_a.iter().sum::<f64>() / half_a.len() as f64;
            let mb = half_b.iter().sum::<f64>() / half_b.len() as f64;
            let covariance: f64 = half_a
                .iter()
                .zip(&half_b)
                .map(|(a, b)| (a - ma) * (b - mb))
                .sum();
            let va: f64 = half_a.iter().map(|v| (v - ma).powi(2)).sum();
            let vb: f64 = half_b.iter().map(|v| (v - mb).powi(2)).sum();
            if va * vb > 0. {
                Some(covariance / (va * vb).sqrt())
            } else {
                None
            }
        } else {
            None
        };
        // Statistics retain the unmerged source observations and do not delete absences.
        let laue = &assessment.laue[assessment.evidence[0].laue];
        self.scaling = json!({"fit":fit_summary,"group":self.config.group,"symbol":info.hm_symbol,"hall":info.hall_symbol,"families":merged.family_count,"systematicAbsences":merged.absent_observations,"nonpositiveFamilies":merged.nonpositive_families,"repeatedFamilies":repeats,"rInt":if denominator>0.{Some(numerator/denominator)}else{None},"ccHalf":cc,"multiplicity":rows.len()as f64/families.len().max(1)as f64,"symmetryStatus":laue.status,"strongAbsenceViolations":assessment.evidence[0].strong_violations,"absorption":"not corrected","completeness":null});
        // Commit scaled values only after every validation succeeds. A rerun starts
        // from freshly integrated original counts, avoiding repeated scale application.
        for (id, row) in ids.into_iter().zip(rows) {
            self.reflections[id] = row;
        }
        Ok(format!(
            "{} independent {} families; {repeats} repeated families; {} systematic-absence rows retained. {} No absorption correction.",
            merged.family_count,
            info.hm_symbol,
            merged.absent_observations,
            if native_profile {
                "Native per-frame/detector/ray family scaling applied."
            } else if self.config.scan_scaling {
                "Robust scan scale applied."
            } else {
                "Scan scale disabled."
            }
        ))
    }
}
