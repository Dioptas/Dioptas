use super::*;
use nalgebra::{Matrix3, Vector3};
use phasesmith_crystallography::UnitCell;
fn length(v: V3) -> f64 {
    fft::dot(v, v).sqrt()
}
fn cross(a: V3, b: V3) -> V3 {
    [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]
}
fn det(b: M3) -> f64 {
    fft::dot(b[0], cross(b[1], b[2]))
}
fn parameters(b: M3) -> [f64; 6] {
    let l = b.map(length);
    let angle = |i: usize, j: usize| {
        (fft::dot(b[i], b[j]) / (l[i] * l[j]))
            .clamp(-1., 1.)
            .acos()
            .to_degrees()
    };
    [l[0], l[1], l[2], angle(1, 2), angle(0, 2), angle(0, 1)]
}
fn image<'a>(
    data: &'a [f64],
    mask: &'a [bool],
    variance: Option<&'a [f64]>,
    shape: [usize; 2],
    c: &Config,
) -> spots::Image<'a> {
    spots::Image {
        values: data,
        height: shape[0],
        width: shape[1],
        mask,
        variance,
        gain: c.gain,
        read_noise: c.read_noise,
        saturation: Some(c.saturation),
    }
}
impl Crystal {
    pub(super) fn process(
        &mut self,
        stage: usize,
        control: &Control,
        automatic: bool,
    ) -> Result<String, String> {
        control.check()?;
        match stage {
            0 => self.background(control),
            1 => self.detect(control),
            2 => self.cells(control, automatic),
            3 => self.geometry(control),
            4 => self.integrate(control),
            5 => self.scale(control),
            6 => self.solve(control),
            _ => unreachable!(),
        }
    }
    fn background(&mut self, control: &Control) -> Result<String, String> {
        if !self.config.background {
            self.background = None;
            return Ok("Disabled: local background is still fitted during spot detection and original-count integration.".into());
        }
        let nf = self.sources.len();
        let pixels = self.shape[0] * self.shape[1];
        let size = pixels
            .checked_mul(nf)
            .and_then(|v| v.checked_mul(8))
            .ok_or("Scan scratch size overflow.")?;
        if size > SCRATCH_BYTES / 2 {
            return Err("Omega background needs two scratch arrays and this scan exceeds the 16 GiB scratch limit. Disable omega background or load fewer frames; original-count local-background integration remains available.".into());
        }
        let mut raw = tempfile::tempfile().map_err(err)?;
        let baseline = tempfile::NamedTempFile::new().map_err(err)?;
        baseline.as_file().set_len(size as u64).map_err(err)?;
        for i in 0..nf {
            control.check()?;
            let data = self.read(i)?;
            let bytes: Vec<u8> = data.iter().flat_map(|v| v.to_le_bytes()).collect();
            raw.write_all(&bytes).map_err(err)?;
            control.publish(json!({"running":true,"current":i+1,"total":nf,"label":"Reading original counts for omega background"}));
        }
        let engine = spots::omega_background::Engine::new(2)?;
        let tile = (2_000_000 / nf).clamp(1, 4096);
        let mut out = baseline.reopen().map_err(err)?;
        let mut converged = 0;
        let mut fitted = 0;
        for first in (0..pixels).step_by(tile) {
            control.check()?;
            let count = tile.min(pixels - first);
            let mut data = vec![0.; count * nf];
            let mut mask = vec![false; count * nf];
            let mut bytes = vec![0u8; count * 8];
            for frame in 0..nf {
                raw.seek(SeekFrom::Start(((frame * pixels + first) * 8) as u64))
                    .map_err(err)?;
                raw.read_exact(&mut bytes).map_err(err)?;
                for (j, b) in bytes.as_chunks::<8>().0.iter().enumerate() {
                    let v = f64::from_le_bytes(*b);
                    let k = j * nf + frame;
                    let pixel = first + j;
                    let (x, y) = (pixel % self.shape[1], pixel / self.shape[1]);
                    data[k] = v;
                    mask[k] = self.excluded_frames.contains(&frame)
                        || !v.is_finite()
                        || v < 0.
                        || v >= self.config.saturation
                        || self
                            .mask
                            .iter()
                            .any(|&[x0, y0, x1, y1]| x >= x0 && x < x1 && y >= y0 && y < y1);
                }
            }
            let fit = engine.baselines(
                &data,
                nf,
                Some(&mask),
                spots::omega_background::Parameters {
                    smoothness: self.config.smoothness,
                    tolerance: 0.01,
                    max_iterations: 30,
                },
                3,
            )?;
            converged += fit.converged.iter().filter(|&&c| c).count();
            fitted += fit
                .baseline
                .chunks_exact(nf)
                .filter(|row| row.iter().any(|v| v.is_finite()))
                .count();
            for frame in 0..nf {
                out.seek(SeekFrom::Start(((frame * pixels + first) * 8) as u64))
                    .map_err(err)?;
                bytes.clear();
                for j in 0..count {
                    bytes.extend_from_slice(&fit.baseline[j * nf + frame].to_le_bytes());
                }
                out.write_all(&bytes).map_err(err)?;
            }
            control.publish(json!({"running":true,"current":first+count,"total":pixels,"label":"Fitting omega background · positions only"}));
        }
        self.background = Some(Arc::new(baseline));
        Ok(format!(
            "arPLS: {converged}/{fitted} fitted pixels converged. Positions only; intensities retain original counts."
        ))
    }
    fn detect(&mut self, control: &Control) -> Result<String, String> {
        let mut peaks = Vec::new();
        let options = spots::Options {
            threshold_sigma: self.config.threshold,
            min_pixels: self.config.min_pixels,
            ..Default::default()
        };
        let n = self.sources.len();
        for frame in 0..n {
            control.check()?;
            if self.excluded_frames.contains(&frame) {
                continue;
            }
            let raw = self.read(frame)?;
            let mut mask = self.mask_for(&raw, frame);
            let variance: Vec<_> = raw
                .iter()
                .map(|v| (v.max(0.) / self.config.gain + self.config.read_noise.powi(2)).max(1.))
                .collect();
            let mut values = raw;
            if let Some(bg) = self.baseline(frame)? {
                for ((v, m), b) in values.iter_mut().zip(&mut mask).zip(bg) {
                    if !b.is_finite() {
                        *m = true;
                    } else {
                        *v -= b;
                    }
                }
            }
            let found = spots::detect(
                &image(&values, &mask, Some(&variance), self.shape, &self.config),
                options,
            )
            .map_err(err)?;
            for s in found.spots {
                if s.values[..2].iter().all(|v| v.is_finite()) {
                    peaks.push(Peak {
                        frame,
                        xy: [s.values[0], s.values[1]],
                        intensity: s.values[2].max(0.),
                        flags: s.flags,
                        bounds: [s.bounds.x0, s.bounds.y0, s.bounds.x1, s.bounds.y1],
                        track: 0,
                    });
                }
            }
            if peaks.len() > 200000 {
                return Err("More than 200,000 spot observations: raise the threshold or mask powder/diamond regions.".into());
            }
            control.publish(json!({"running":true,"current":frame+1,"total":n,"label":"Finding peaks in rotation frames"}));
        }
        if peaks.len() < 12 {
            return Err(format!(
                "Only {} peaks found; at least 12 are required. Lower the threshold, check background and masks, or verify the scan.",
                peaks.len()
            ));
        }
        let frames: Vec<_> = peaks.iter().map(|p| p.frame as u32).collect();
        let xy: Vec<_> = peaks.iter().map(|p| p.xy).collect();
        let segments = vec![0u32; n];
        let ids =
            spots::rotation::link(&frames, &xy, &segments, self.config.link_radius, 20_000_000)
                .map_err(err)?;
        let mut groups: BTreeMap<usize, Vec<usize>> = BTreeMap::new();
        for (i, id) in ids.into_iter().enumerate() {
            peaks[i].track = id as usize;
            groups.entry(id as usize).or_default().push(i);
        }
        let mut tracks = Vec::new();
        for (_id, rows) in groups {
            let samples: Vec<_> = rows
                .iter()
                .map(|&i| {
                    [
                        peaks[i].xy[0],
                        peaks[i].xy[1],
                        self.config.omega_start
                            + (peaks[i].frame as f64) * self.config.omega_step
                            + self.config.exposure / 2.,
                        peaks[i].intensity.max(1e-9),
                    ]
                })
                .collect();
            let summary = spots::rotation::summarize(&samples).map_err(err)?;
            let first = peaks[rows[0]].frame;
            let last = peaks[*rows.last().unwrap()].frame;
            let mut bounds = [usize::MAX, usize::MAX, 0, 0];
            let mut flags = 0;
            let id = tracks.len();
            for i in rows {
                peaks[i].track = id;
                let b = peaks[i].bounds;
                bounds = [
                    bounds[0].min(b[0]),
                    bounds[1].min(b[1]),
                    bounds[2].max(b[2]),
                    bounds[3].max(b[3]),
                ];
                flags |= peaks[i].flags;
            }
            if first == 0
                || last == n - 1
                || self
                    .excluded_frames
                    .iter()
                    .any(|&i| i + 1 == first || i == last + 1)
            {
                flags |= 1024;
            }
            tracks.push(Track {
                observed: [summary[0], summary[1], summary[2]],
                first,
                last,
                bounds,
                flags,
                excluded: false,
            });
        }
        let description = format!(
            "{} observations linked into {} tracks. Flagged tracks are retained for inspection.",
            peaks.len(),
            tracks.len()
        );
        self.peaks = peaks;
        self.tracks = tracks;
        Ok(description)
    }
    fn cloud(&self) -> Result<(Vec<usize>, Vec<V3>), String> {
        let mut g = self
            .geometry
            .ok_or("Load a PONI calibration in Frames before cell finding.")?
            .native();
        g.axis = self.config.axis;
        let available: Vec<_> = self
            .tracks
            .iter()
            .enumerate()
            .filter(|(_, t)| !t.excluded && t.flags == 0)
            .map(|(i, _)| i)
            .collect();
        let ids: Vec<_> = available
            .iter()
            .step_by(available.len().div_ceil(10000).max(1))
            .copied()
            .collect();
        let xyz: Vec<_> = ids.iter().map(|&i| self.tracks[i].observed).collect();
        let q = g.convert(&xyz).map_err(err)?;
        if q.len() < 25 {
            return Err(format!(
                "{} unflagged tracks; at least 25 are required for independent cell validation. Inspect masks, threshold and scan coverage.",
                q.len()
            ));
        }
        Ok((ids, q))
    }
    fn cells(&mut self, control: &Control, automatic: bool) -> Result<String, String> {
        if self.cells.is_empty() {
            let (_, q) = self.cloud()?;
            let train: Vec<_> = q
                .iter()
                .enumerate()
                .filter(|(i, _)| i % 5 != 0)
                .map(|(_, v)| *v)
                .collect();
            let test: Vec<_> = q
                .iter()
                .enumerate()
                .filter(|(i, _)| i % 5 == 0)
                .map(|(_, v)| *v)
                .collect();
            let engine = fft::Engine::new(2)?;
            let qmax = q.iter().flatten().copied().map(f64::abs).fold(0., f64::max);
            let n = 256;
            let step = (2. * qmax / 252.).min(1. / (2.1 * self.config.max_cell));
            control.publish(json!({"running":true,"current":0,"total":1,"label":"Searching position-only FFT lattice candidates"}));
            let (vectors, _, _) = engine.windowed_maxima(
                &train,
                n,
                step,
                self.config.min_cell,
                self.config.max_cell,
                96,
            )?;
            control.check()?;
            let refined = engine
                .refine_fourier(&train, &vectors, (1. / (n as f64 * step)) * 1.5)
                .map_err(err)?;
            let vectors: Vec<_> = refined.into_iter().map(|r| r.0).collect();
            let mut candidates: Vec<Cell> = Vec::new();
            for i in 0..vectors.len() {
                control.check()?;
                for j in i + 1..vectors.len() {
                    for k in j + 1..vectors.len() {
                        let mut a = [vectors[i], vectors[j], vectors[k]];
                        if det(a).abs() < 15. || det(a).abs() > 100000. {
                            continue;
                        }
                        if det(a) < 0. {
                            a.swap(0, 1);
                        }
                        let Ok(b) = fft::inverse_transpose(a) else {
                            continue;
                        };
                        let support = engine.score(&train, a, b);
                        let count = support
                            .iter()
                            .filter(|(h, d)| *h != [0.; 3] && *d < self.config.tolerance)
                            .count();
                        if count < 20 || count * 2 < train.len() {
                            continue;
                        }
                        let Ok(reduced) = spots::reduction::reduce(a, 1e-10, 1000) else {
                            continue;
                        };
                        a = reduced.basis;
                        let b = fft::inverse_transpose(a)?;
                        let a = refine_basis(&train, a, b, self.config.tolerance)?;
                        let b = fft::inverse_transpose(a)?;
                        let score = engine.score(&test, a, b);
                        let selected: Vec<_> = score
                            .iter()
                            .filter(|(h, d)| *h != [0.; 3] && *d < self.config.tolerance)
                            .collect();
                        if selected.len() < 5 || selected.len() * 2 < test.len() {
                            continue;
                        }
                        let params = parameters(a);
                        if params[..3]
                            .iter()
                            .any(|&l| l < self.config.min_cell || l > self.config.max_cell)
                        {
                            continue;
                        }
                        let all_scores = engine.score(&q, a, b);
                        if !primitive_indices(&all_scores, self.config.tolerance) {
                            continue;
                        }
                        let all = all_scores
                            .iter()
                            .filter(|(h, d)| *h != [0.; 3] && *d < self.config.tolerance)
                            .count();
                        let rms = (selected.iter().map(|(_, d)| d * d).sum::<f64>()
                            / selected.len() as f64)
                            .sqrt();
                        if candidates.iter().any(|c| same_lattice(c.direct, a)) {
                            continue;
                        }
                        candidates.push(Cell {
                            direct: a,
                            parameters: params,
                            indexed: all,
                            total: q.len(),
                            rms,
                            validation: selected.len(),
                        });
                        candidates.sort_by(|a, b| {
                            cell_score(b, self.config.tolerance)
                                .total_cmp(&cell_score(a, self.config.tolerance))
                                .then(det(a.direct).total_cmp(&det(b.direct)))
                                .then(a.rms.total_cmp(&b.rms))
                        });
                        candidates.truncate(12);
                    }
                }
            }
            self.cells = candidates;
        }
        if self.cells.is_empty() {
            return Err("No lattice passed independent withheld-position gates. Check geometry, spindle axis and omega sign, lower the peak threshold, or exclude diamond/powder regions.".into());
        }
        if self.selected.is_none() {
            let best = &self.cells[0];
            let diamond = diamond_like(best.parameters);
            if automatic
                && !diamond
                && best.indexed * 100 >= best.total * 70
                && (self.cells.len() == 1 || best.indexed > self.cells[1].indexed + best.total / 10)
            {
                self.selected = Some(0);
            } else {
                return Err(format!(
                    "{}. Inspect indexed coverage and withheld RMS, then use the sample cell.{}",
                    if self.cells.len() == 1 {
                        "One plausible cell found; confirm it before continuing".to_owned()
                    } else {
                        format!(
                            "{} plausible cells; choose the sample lattice",
                            self.cells.len()
                        )
                    },
                    if diamond {
                        " The leading cell is diamond-like."
                    } else {
                        ""
                    }
                ));
            }
        }
        let cell = &self.cells[self.selected.unwrap()];
        Ok(format!(
            "Selected reduced primitive cell: {}/{} tracks indexed; withheld reciprocal RMS {:.5} Å⁻¹. Confirm the conventional setting before symmetry analysis.",
            cell.indexed, cell.total, cell.rms
        ))
    }
    fn geometry(&mut self, control: &Control) -> Result<String, String> {
        let cell = &self.cells[self.selected.ok_or("Select a cell first.")?];
        let direct = cell.direct;
        let mut basis = fft::inverse_transpose(direct)?;
        if let Some(metric) = self.config.metric {
            if cell
                .parameters
                .iter()
                .zip(metric)
                .enumerate()
                .any(|(i, (a, b))| {
                    if i < 3 {
                        (a - b).abs() > 0.05 * a
                    } else {
                        (a - b).abs() > 5.
                    }
                })
            {
                return Err("The supplied metric differs from the selected row setting by more than 5% in length or 5° in angle. Reorder the cell axes explicitly or choose the matching candidate.".into());
            }
            basis = fitting::reference_basis(basis, metric).map_err(err)?;
        }
        let (ids, q) = self.cloud()?;
        let scores = fft::Engine::new(1)?.score(&q, direct, basis);
        let mut hkl = Vec::new();
        let mut observed = Vec::new();
        for ((h, d), id) in scores.into_iter().zip(ids) {
            if h != [0.; 3] && d < self.config.tolerance {
                hkl.push(h.map(|x| x as i64));
                observed.push(self.tracks[id].observed);
            }
        }
        let mut g = self
            .initial_geometry
            .ok_or("Load a PONI calibration first.")?
            .native();
        g.axis = self.config.axis;
        if !self.config.refine_geometry {
            let predictions = spots::prediction::predict(
                g,
                basis,
                &hkl,
                &observed.iter().map(|v| v[2]).collect::<Vec<_>>(),
                false,
            )
            .map_err(err)?;
            let residuals: Vec<_> = predictions
                .iter()
                .zip(&observed)
                .filter(|(p, _)| p.flags == 0)
                .map(|(p, o)| (p.values[0] - o[0]).powi(2) + (p.values[1] - o[1]).powi(2))
                .collect();
            let rms = (residuals.iter().sum::<f64>() / residuals.len().max(1) as f64).sqrt();
            if residuals.len() < 20 || rms > 5. {
                return Err(format!(
                    "Fixed-geometry prediction RMS {rms:.3} px is above 5 px or fewer than 20 predictions are valid. Check cell, calibration and acquisition, or enable geometry refinement."
                ));
            }
            self.basis = Some(basis);
            self.geometry = Some(g.into());
            self.geometry_report =
                json!({"refined":false,"rmsPixels":rms,"observations":residuals.len()});
            return Ok(format!(
                "Calibration held fixed; prediction RMS {rms:.3} px on {} tracks.",
                residuals.len()
            ));
        }
        let training: Vec<_> = (0..hkl.len()).map(|i| i % 5 != 0).collect();
        let eligible = vec![true; hkl.len()];
        let fit=fitting::fit(&fitting::Input{observed:&observed,hkl:&hkl,training:&training,eligible:&eligible,basis,geometry:g,image_shape:self.shape,reference_cell:None,refine_lengths:false},fitting::Options::default(),|current,total|{control.check().map_err(spots::SpotError)?;control.publish(json!({"running":true,"current":current,"total":total,"label":"Refining detector pose and crystal orientation"}));Ok(())}).map_err(err)?;
        let report = json!({"refined":true,"converged":fit.converged,"atBounds":fit.at_bounds,"condition":fit.scaled_condition,"maximumCorrelation":fit.maximum_parameter_correlation,"rms":fit.rms,"counts":fit.counts,"evaluations":fit.evaluations,"parameters":fit.parameters,"accepted":fit.acceptable()});
        self.geometry_report = report;
        if !fit.acceptable() {
            return Err("Geometry refinement did not pass convergence, identification and withheld-improvement gates. Review diagnostics; keep the calibration fixed or correct the acquisition settings.".into());
        }
        self.geometry = Some(fit.state.geometry.into());
        self.basis = Some(fit.state.basis);
        Ok(format!(
            "Refined 9 pose/orientation parameters; withheld RMS {:.3} → {:.3} px. Wavelength and cell lengths held fixed.",
            fit.rms[1][0][0], fit.rms[1][1][0]
        ))
    }
    fn integrate(&mut self, control: &Control) -> Result<String, String> {
        let b = self.basis.ok_or("Run geometry validation first.")?;
        let a = fft::inverse_transpose(b)?;
        let g = self.geometry.unwrap().native();
        let ids: Vec<_> = self
            .tracks
            .iter()
            .enumerate()
            .filter(|(_, t)| !t.excluded && t.observed.iter().all(|v| v.is_finite()))
            .map(|(i, _)| i)
            .collect();
        let q = g
            .convert(
                &ids.iter()
                    .map(|&i| self.tracks[i].observed)
                    .collect::<Vec<_>>(),
            )
            .map_err(err)?;
        let scores = fft::Engine::new(1)?.score(&q, a, b);
        let mut tracks = Vec::new();
        let mut rows = Vec::new();
        for ((h, d), id) in scores.into_iter().zip(ids) {
            if h == [0.; 3] || d >= self.config.tolerance {
                continue;
            }
            let t = &self.tracks[id];
            let ray = std::array::from_fn(|j| {
                g.origin[j] + t.observed[0] * g.fast[j] + t.observed[1] * g.slow[j]
            });
            let ray = ray.map(|v| v / length(ray));
            let beam = g.beam.map(|v| v / length(g.beam));
            let axis = g.axis.map(|v| v / length(g.axis));
            let e = [0., 1., 0.];
            let orth = cross(beam, e);
            let p = self.config.polarization * (1. - fft::dot(ray, e).powi(2))
                + (1. - self.config.polarization) * (1. - fft::dot(ray, orth).powi(2));
            let correction = fft::dot(cross(ray, beam), axis).abs() / p;
            if !correction.is_finite() || correction < 1e-8 {
                continue;
            }
            let frame_zero = self.config.omega_start;
            let start =
                ((t.observed[2] - self.config.omega_radius - frame_zero - self.config.exposure)
                    / self.config.omega_step)
                    .floor() as isize
                    + 1;
            let stop = ((t.observed[2] + self.config.omega_radius - frame_zero)
                / self.config.omega_step)
                .ceil() as usize;
            let predicted =
                spots::prediction::predict(g, b, &[h.map(|v| v as i64)], &[t.observed[2]], false)
                    .map_err(err)?;
            let position_flag = if predicted[0].flags != 0
                || (predicted[0].values[0] - t.observed[0])
                    .hypot(predicted[0].values[1] - t.observed[1])
                    > 3.
                || (predicted[0].values[2] - t.observed[2]).abs() > self.config.omega_step.max(0.5)
            {
                2048
            } else {
                0
            };
            let partial = (self.config.omega_step - self.config.exposure).abs()
                > self.config.omega_step * 0.001
                || start < 0
                || stop > self.sources.len()
                || self
                    .excluded_frames
                    .iter()
                    .any(|&i| (i as isize) >= start && i < stop);
            tracks.push((id, start.max(0) as usize, stop.min(self.sources.len())));
            rows.push(Reflection {
                hkl: h.map(|v| v as i64),
                omega: t.observed[2],
                intensity: 0.,
                sigma: 0.,
                flags: t.flags | position_flag | if partial { 1024 } else { 0 },
                track: id,
                correction,
            });
        }
        if rows.is_empty() {
            return Err("No indexed complete tracks remain for integration.".into());
        }
        for frame in 0..self.sources.len() {
            control.check()?;
            if self.excluded_frames.contains(&frame) {
                continue;
            }
            let data = self.read(frame)?;
            let mask = self.mask_for(&data, frame);
            let active: Vec<_> = tracks
                .iter()
                .enumerate()
                .filter(|(_, (_, first, last))| frame >= *first && frame < *last)
                .map(|(i, _)| i)
                .collect();
            if active.is_empty() {
                continue;
            }
            let boxes: Vec<_> = active
                .iter()
                .map(|&i| {
                    let t = &self.tracks[tracks[i].0];
                    let r = self.config.aperture_radius;
                    let x = t.observed[0].floor() as usize;
                    let y = t.observed[1].floor() as usize;
                    spots::Bounds {
                        x0: x.saturating_sub(r),
                        y0: y.saturating_sub(r),
                        x1: (x + r + 1).min(self.shape[1]),
                        y1: (y + r + 1).min(self.shape[0]),
                    }
                })
                .collect();
            let measurements = spots::extract(
                &image(&data, &mask, None, self.shape, &self.config),
                &boxes,
                spots::Options {
                    min_pixels: self.config.min_pixels,
                    max_spots: 200000,
                    ..Default::default()
                },
            )
            .map_err(err)?;
            for (i, s) in active.into_iter().zip(measurements) {
                rows[i].flags |= s.flags & !spots::NO_CENTROID;
                if s.values[2..4].iter().all(|v| v.is_finite()) {
                    rows[i].intensity += s.values[2];
                    rows[i].sigma += s.values[3].powi(2);
                } else {
                    rows[i].flags |= spots::BACKGROUND;
                }
            }
            control.publish(json!({"running":true,"current":frame+1,"total":self.sources.len(),"label":"Integrating original counts · local background"}));
        }
        for r in &mut rows {
            r.intensity *= r.correction;
            r.sigma = r.sigma.sqrt() * r.correction;
            if r.sigma <= 0. {
                r.flags |= spots::BACKGROUND;
            }
        }
        let count = rows.iter().filter(|r| r.flags == 0).count();
        self.unscaled_reflections = rows.clone();
        self.reflections = rows;
        if count < 12 {
            return Err(format!(
                "Only {count} usable integrated reflections. Inspect the retained flagged rows, overlaps, masks and coverage."
            ));
        }
        Ok(format!(
            "{count} measured complete tracks integrated from original counts with local background, counting σ and Lorentz/polarization correction. No absorption or empirical scan scaling applied."
        ))
    }
    fn solve(&mut self, control: &Control) -> Result<String, String> {
        let elements: Vec<_> = self
            .config
            .elements
            .split(|c: char| c == ',' || c.is_whitespace())
            .filter(|s| !s.is_empty())
            .map(str::to_owned)
            .collect();
        if elements.is_empty() {
            return Err("Enter the element symbols and explicitly supplied space group to search for structure candidates, or export the integrated reflections.".into());
        }
        let cell = self.cell()?;
        let group = phasesmith_io::space_group_by_number(i32::from(self.config.group))
            .map_err(err)?
            .space_group;
        let observations: Vec<_> = self
            .reflections
            .iter()
            .filter(|r| r.flags == 0)
            .map(|r| solution::Observation {
                hkl: r.hkl.map(|v| v as i32),
                intensity: r.intensity,
                sigma: r.sigma,
            })
            .collect();
        let token = solution::Cancellation::default();
        let finished = Arc::new(std::sync::atomic::AtomicBool::new(false));
        let options = solution::SolveOptions {
            seed: 0,
            trials: 4,
            cycles: 800,
            phasing: solution::PhasingMethod::DualSpace,
            refinement: Some(if self.config.adp == "anisotropic" {
                solution::AdpMode::Anisotropic
            } else {
                solution::AdpMode::Isotropic
            }),
            max_seconds: self.config.search_seconds,
            cancellation: Some(token.clone()),
            completion: false,
            ..Default::default()
        };
        let result = std::thread::scope(|scope| {
            let done = finished.clone();
            scope.spawn(move || {
                while !done.load(std::sync::atomic::Ordering::Acquire) {
                    if control.check().is_err() {
                        let _ = token.cancel();
                        break;
                    }
                    std::thread::sleep(std::time::Duration::from_millis(20));
                }
            });
            let _completion = SearchCompletion(finished.clone());
            let result = solution::solve_elements(
                &observations,
                cell,
                &group,
                &elements,
                &options,
                &solution::SharedSearchOptions::default(),
            );
            finished.store(true, std::sync::atomic::Ordering::Release);
            result
        })
        .map_err(err)?;
        control.check()?;
        let best=result.candidates.first().ok_or("No structure candidate found within the declared budget; export observations or increase the search budget.")?;
        let (mode, parameters, termination) = best
            .refinement
            .as_ref()
            .map(|r| (r.mode.to_owned(), r.parameter_count, r.termination))
            .unwrap_or(("P1".into(), 0, "not refined"));
        self.structure = json!({"r1":best.r1,"mode":mode,"parameters":parameters,"termination":termination,"searchTermination":result.termination,"targetMet":result.target_met,"atoms":best.species.len(),"species":best.species,"xyz":best.fractional_xyz,"group":self.config.group,"observations":observations.len(),"families":result.data.family_count,"absentObservations":result.data.absent_observations,"seed":0,"engine":ENGINE});
        let cp = [
            cell.a_angstrom,
            cell.b_angstrom,
            cell.c_angstrom,
            cell.alpha_deg,
            cell.beta_deg,
            cell.gamma_deg,
        ];
        let mut cif = format!(
            "data_dioptas_candidate\n# Candidate search; not a fully validated structure refinement\n_cell_length_a {}\n_cell_length_b {}\n_cell_length_c {}\n_cell_angle_alpha {}\n_cell_angle_beta {}\n_cell_angle_gamma {}\n_symmetry_space_group_name_H-M 'P 1'\nloop_\n_atom_site_label\n_atom_site_type_symbol\n_atom_site_fract_x\n_atom_site_fract_y\n_atom_site_fract_z\n_atom_site_U_iso_or_equiv\n",
            cp[0], cp[1], cp[2], cp[3], cp[4], cp[5]
        );
        for (i, (s, p)) in best.species.iter().zip(&best.fractional_xyz).enumerate() {
            cif.push_str(&format!(
                "{s}{} {s} {} {} {} {}\n",
                i + 1,
                p[0],
                p[1],
                p[2],
                best.refinement
                    .as_ref()
                    .and_then(|r| r.full_u_equiv.get(i).copied())
                    .unwrap_or(best.u_iso)
            ));
        }
        self.cif = Some(cif);
        Ok(format!(
            "Candidate R1 {:.3}% · {} ADPs · {parameters} parameters · {termination}. Candidate assessment only; lower R1 does not establish correctness.",
            best.r1 * 100.,
            self.config.adp
        ))
    }
    pub(super) fn cell(&self) -> Result<UnitCell, String> {
        let basis = self
            .basis
            .ok_or("Validate geometry before using cell metrics.")?;
        let p = parameters(fft::inverse_transpose(basis)?);
        {
            let c = UnitCell {
                a_angstrom: p[0],
                b_angstrom: p[1],
                c_angstrom: p[2],
                alpha_deg: p[3],
                beta_deg: p[4],
                gamma_deg: p[5],
            };
            c.geometry().map_err(err)?;
            Ok(c)
        }
    }
    pub(super) fn edit(&mut self, args: &Value) -> Result<(), String> {
        match args["operation"].as_str() {
            Some("cell") => {
                let index = args["index"].as_u64().ok_or("Choose a cell candidate.")? as usize;
                if index >= self.cells.len() {
                    return Err("Cell candidate no longer exists.".into());
                }
                self.invalidate(3);
                self.selected = Some(index);
                self.stages[2].status = "complete".into();
                self.stages[2].detail =
                    format!("Cell {} explicitly selected by the user.", index + 1);
            }
            Some("track") => {
                let id = args["index"].as_u64().ok_or("Choose a track.")? as usize;
                if id >= self.tracks.len() {
                    return Err("Track no longer exists.".into());
                }
                self.tracks[id].excluded = !self.tracks[id].excluded;
                self.invalidate(2);
            }
            Some("frame") => {
                let id = args["index"].as_u64().ok_or("Choose a frame.")? as usize;
                if id >= self.sources.len() {
                    return Err("Frame no longer exists.".into());
                }
                if self.excluded_frames.contains(&id) {
                    self.excluded_frames.retain(|&x| x != id);
                } else {
                    self.excluded_frames.push(id);
                }
                self.invalidate(0);
                self.preview("raw")?;
            }
            Some("mask") => {
                let b: [usize; 4] = serde_json::from_value(args["bounds"].clone()).map_err(err)?;
                if b[0] >= b[2] || b[1] >= b[3] || b[2] > self.shape[1] || b[3] > self.shape[0] {
                    return Err("Mask rectangle must lie inside the detector.".into());
                }
                self.mask.push(b);
                self.invalidate(0);
                self.preview("raw")?;
            }
            Some("remove_mask") => {
                let i = args["index"].as_u64().ok_or("Choose a mask region.")? as usize;
                if i >= self.mask.len() {
                    return Err("Mask region no longer exists.".into());
                }
                self.mask.remove(i);
                self.invalidate(0);
                self.preview("raw")?;
            }
            Some("clear_mask") => {
                self.mask.clear();
                self.invalidate(0);
                self.preview("raw")?;
            }
            Some("rerun") => {
                let stage = args["index"]
                    .as_u64()
                    .filter(|v| *v < 7)
                    .ok_or("Choose a processing stage.")? as usize;
                self.invalidate(stage);
            }
            _ => return Err("Unknown workflow edit.".into()),
        }
        Ok(())
    }
}
fn refine_basis(q: &[V3], a: M3, b: M3, tolerance: f64) -> Result<M3, String> {
    let mut hh = Matrix3::zeros();
    let mut hq = Matrix3::zeros();
    for &point in q {
        let (h, d) = fft::indexed(point, a, b);
        if h == [0.; 3] || d >= tolerance {
            continue;
        }
        let h = Vector3::from(h);
        let q = Vector3::from(point);
        hh += h * h.transpose();
        hq += h * q.transpose();
    }
    let Some(solved) = hh.lu().solve(&hq) else {
        return Ok(a);
    };
    let rows = std::array::from_fn(|i| std::array::from_fn(|j| solved[(i, j)]));
    fft::inverse_transpose(rows)
}

// Equivalence gate: exact integer, unimodular row changes preserve a lattice.
fn same_lattice(a: M3, b: M3) -> bool {
    let Ok(inverse) = fft::inverse_transpose(b) else {
        return false;
    };
    let transform = a.map(|row| inverse.map(|dual| fft::dot(row, dual)));
    transform
        .iter()
        .flatten()
        .all(|v| (v - v.round()).abs() < 0.002)
        && ((det(transform).abs() - 1.).abs() < 0.002)
}
// A primitive observed index lattice spans Z³. GCD of its integer 3×3 minors
// rejects harmonics/supercells. This is a support gate, not a cell reducer.
fn primitive_indices(scores: &[(V3, f64)], tolerance: f64) -> bool {
    let h: Vec<_> = scores
        .iter()
        .filter(|(h, d)| *h != [0.; 3] && *d < tolerance)
        .take(32)
        .map(|(h, _)| *h)
        .collect();
    let mut divisor = 0i64;
    for i in 0..h.len() {
        for j in i + 1..h.len() {
            for k in j + 1..h.len() {
                let mut value = det([h[i], h[j], h[k]]).round().abs() as i64;
                while value != 0 {
                    let next = divisor % value;
                    divisor = value;
                    value = next;
                }
                if divisor == 1 {
                    return true;
                }
            }
        }
    }
    false
}

fn diamond_like(p: [f64; 6]) -> bool {
    (p[..3].iter().all(|l| (*l - 3.567).abs() < 0.15)
        && p[3..].iter().all(|a| (*a - 90.).abs() < 3.))
        || (p[..3]
            .iter()
            .all(|l| (*l - 3.567 / 2f64.sqrt()).abs() < 0.12)
            && p[3..]
                .iter()
                .all(|a| (*a - 60.).abs() < 3. || (*a - 120.).abs() < 3.))
}
fn cell_score(cell: &Cell, tolerance: f64) -> f64 {
    // Expected support of uniform reciprocal background: N × V × 4πr³/3.
    cell.indexed as f64
        - cell.total as f64 * det(cell.direct).abs() * 4. * std::f64::consts::PI / 3.
            * tolerance.powi(3)
}

struct SearchCompletion(Arc<std::sync::atomic::AtomicBool>);
impl Drop for SearchCompletion {
    fn drop(&mut self) {
        self.0.store(true, std::sync::atomic::Ordering::Release);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn primitive_diamond_and_supercell_gates() {
        assert!(diamond_like([2.522, 2.522, 2.522, 60., 60., 60.]));
        assert!(diamond_like([3.567, 3.567, 3.567, 90., 90., 90.]));
        assert!(!diamond_like([7., 9., 11., 90., 90., 90.]));
        assert!(primitive_indices(
            &[([1., 0., 0.], 0.), ([0., 1., 0.], 0.), ([0., 0., 1.], 0.)],
            0.01
        ));
        assert!(!primitive_indices(
            &[([2., 0., 0.], 0.), ([0., 2., 0.], 0.), ([0., 0., 2.], 0.)],
            0.01
        ));
    }
    #[test]
    fn equivalent_row_settings_are_not_reported_as_competing_cells() {
        let a = [[7., 0., 0.], [0., 9., 0.], [0., 0., 11.]];
        let b = [[7., 9., 0.], [0., 9., 0.], [0., 0., 11.]];
        assert!(same_lattice(a, b));
        assert!(!same_lattice(
            a,
            [[14., 0., 0.], [0., 9., 0.], [0., 0., 11.]]
        ));
    }
}
