//! Portable, versioned SCXRD recipes and original-observation exports.
use super::*;
use std::io::BufWriter;
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Recipe {
    schema: String,
    version: u32,
    engine: String,
    #[serde(default)]
    adapter: String,
    config: Config,
    sources: Vec<Source>,
    #[serde(default)]
    protected_sources: Vec<PathBuf>,
    #[serde(default)]
    calibration_source: Option<PathBuf>,
    shape: [usize; 2],
    geometry: Option<Geometry>,
    mask: Vec<[usize; 4]>,
    excluded_frames: Vec<usize>,
    excluded_tracks: Vec<usize>,
    selected_cell: Option<Cell>,
}
fn atomic(
    path: &Path,
    write: impl FnOnce(&mut BufWriter<&File>) -> Result<(), String>,
) -> Result<(), String> {
    let parent = path
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or(Path::new("."));
    let temporary = tempfile::NamedTempFile::new_in(parent).map_err(err)?;
    {
        let mut w = BufWriter::new(temporary.as_file());
        write(&mut w)?;
        w.flush().map_err(err)?;
    }
    temporary.as_file().sync_all().map_err(err)?;
    temporary.persist(path).map_err(err)?;
    Ok(())
}
impl Session {
    pub(super) fn scxrd_file(&mut self, args: &Value) -> Result<Reply, String> {
        let op = args["operation"]
            .as_str()
            .ok_or("Choose a single-crystal file operation.")?;
        if op == "protocol_builtin" {
            let (first, last) = self.scxrd.config.apply_protocol(protocol::builtin())?;
            self.scxrd.excluded_frames = (0..self.scxrd.sources.len())
                .filter(|i| *i < first || *i > last)
                .collect();
            self.scxrd.invalidate(0);
            self.scxrd.notice=Some("Bundled PhaseSmith v29 protocol applied. Review acquisition, cell/symmetry/element priors and DAC assumptions, then confirm Frames.".into());
            if self.scxrd.has_sources() {
                if self.scxrd.excluded_frames.contains(&self.scxrd.frame) {
                    self.scxrd.frame = first.min(self.scxrd.sources.len() - 1);
                }
                self.scxrd.preview("raw")?;
            }
            return Ok(self.scxrd.reply());
        }
        if op == "use_calibration" {
            if !self.settings.calibrated {
                return Err(
                    "Load or refine a powder calibration first, or load a PONI file here.".into(),
                );
            }
            let g = self.settings.geometry.clone();
            self.scxrd.set_poni(&g)?;
            self.scxrd.calibration_source =
                self.settings.calibration_path.as_ref().map(PathBuf::from);
            if let Some(p) = &self.scxrd.calibration_source {
                self.scxrd.protected_sources.push(p.clone());
            }
            return Ok(self.scxrd.reply());
        }
        let path = PathBuf::from(
            args["path"]
                .as_str()
                .ok_or("Choose an input or output file.")?,
        );
        if matches!(
            op,
            "save" | "reflections" | "hkl" | "cif" | "protocol_save" | "audit"
        ) {
            let canonical = std::fs::canonicalize(&path).ok();
            if self
                .scxrd
                .sources
                .iter()
                .map(|s| &s.path)
                .chain(self.scxrd.protected_sources.iter())
                .any(|source| {
                    source == &path
                        || canonical.as_ref().is_some_and(|target| {
                            std::fs::canonicalize(source).ok().as_ref() == Some(target)
                        })
                })
            {
                return Err(
                    "Choose a different export path: original detector source files are protected."
                        .into(),
                );
            }
        }
        match op {
            "audit" => {
                let directory =
                    self.scxrd.profile_audit.as_ref().ok_or(
                        "Enable Keep stage outputs and rerun the PhaseSmith protocol first.",
                    )?;
                atomic(&path, |w| {
                    let mut source =
                        File::open(directory.path().join("stages.npz")).map_err(err)?;
                    std::io::copy(&mut source, w).map_err(err)?;
                    Ok(())
                })?;
            }
            "protocol" => {
                let file = File::open(&path).map_err(err)?;
                if file.metadata().map_err(err)?.len() > 8 * 1024 * 1024 {
                    return Err("Protocol exceeds 8 MiB.".into());
                }
                let p: Value = serde_json::from_reader(file).map_err(err)?;
                let (first, last) = self.scxrd.config.apply_protocol(p)?;
                self.scxrd.excluded_frames = (0..self.scxrd.sources.len())
                    .filter(|i| *i < first || *i > last)
                    .collect();
                self.scxrd.invalidate(0);
                self.scxrd.notice = Some(format!(
                    "Loaded PhaseSmith protocol {}. Review declared acquisition, supplied cell/symmetry/elements and cell-shadow assumptions; confirm before processing.",
                    path.file_name().unwrap_or_default().to_string_lossy()
                ));
                if self.scxrd.has_sources() {
                    if self.scxrd.excluded_frames.contains(&self.scxrd.frame) {
                        self.scxrd.frame = first.min(self.scxrd.sources.len() - 1);
                    }
                    self.scxrd.preview("raw")?;
                }
            }
            "protocol_save" => {
                if self.scxrd.config.integration_method != "profile" {
                    return Err("Select the PhaseSmith protocol workflow before saving its effective protocol.".into());
                }
                let (first, last) = self.scxrd.protocol_range()?;
                let p = self.scxrd.config.active_protocol(first, last)?;
                atomic(&path, |w| serde_json::to_writer_pretty(w, &p).map_err(err))?;
            }
            "calibration" => {
                let g = crate::geometry::Geometry::load(&path)?;
                self.scxrd.set_poni(&g)?;
                self.scxrd.calibration_source = Some(path.clone());
                self.scxrd.protected_sources.push(path.clone());
            }
            "open" | "preset" => {
                let file = File::open(&path).map_err(err)?;
                if file.metadata().map_err(err)?.len() > 8 * 1024 * 1024 {
                    return Err("Recipe exceeds 8 MiB.".into());
                }
                let recipe: Recipe = serde_json::from_reader(file).map_err(err)?;
                if recipe.schema != "dioptas.scxrd.rust" || recipe.version != 1 {
                    return Err("Unsupported SCXRD recipe schema or version.".into());
                }
                recipe.config.check()?;
                if op == "preset" {
                    let mut config = recipe.config;
                    config.confirmed = false;
                    self.scxrd.config = config;
                    self.scxrd.invalidate(0);
                    if self.scxrd.has_sources() {
                        self.scxrd.preview("raw")?;
                    }
                    self.scxrd.notice=Some("Recipe settings applied. Current frames, calibration, regions and frame exclusions are retained; peak/cell decisions were reset. Review copied acquisition, element, symmetry and metric priors before processing.".into());
                    return Ok(self.scxrd.reply());
                }
                if recipe.sources.len() < 3
                    || recipe.sources.len() > MAX_FRAMES
                    || recipe.shape.contains(&0)
                    || recipe.shape[0]
                        .checked_mul(recipe.shape[1])
                        .is_none_or(|n| n > MAX_PIXELS)
                {
                    return Err("Invalid recipe frame or detector limits.".into());
                }
                if recipe
                    .excluded_frames
                    .iter()
                    .any(|&f| f >= recipe.sources.len())
                    || recipe.mask.iter().any(|b| {
                        b[0] >= b[2]
                            || b[1] >= b[3]
                            || b[2] > recipe.shape[1]
                            || b[3] > recipe.shape[0]
                    })
                {
                    return Err("Invalid recipe frame exclusions or mask rectangles.".into());
                }
                if let Some(g) = recipe.geometry {
                    g.native().convert(&[[0., 0., 0.]]).map_err(err)?;
                }
                let mut candidate = Crystal {
                    config: recipe.config,
                    sources: recipe.sources,
                    protected_sources: vec![],
                    calibration_source: recipe.calibration_source,
                    shape: recipe.shape,
                    geometry: recipe.geometry,
                    initial_geometry: recipe.geometry,
                    mask: recipe.mask,
                    excluded_frames: recipe.excluded_frames,
                    ..Default::default()
                };
                for i in 0..candidate.sources.len() {
                    self.control.check()?;
                    candidate.read(i)?;
                    let source = &candidate.sources[i];
                    let image = Image::open(&source.path, &json!({"frame":source.frame}))?;
                    for (path, _) in image.source_fingerprint()? {
                        if !candidate.protected_sources.contains(&path) {
                            candidate.protected_sources.push(path);
                        }
                    }
                    self.control.publish(json!({"running":true,"current":i+1,"total":candidate.sources.len(),"label":"Verifying recipe source hashes"}));
                }
                if let Some(path) = &candidate.calibration_source {
                    candidate.protected_sources.push(path.clone());
                }
                // Rebuild numerical products rather than trusting cached output in a recipe.
                if !recipe.excluded_tracks.is_empty() || recipe.selected_cell.is_some() {
                    for stage in 0..=1 {
                        let start = std::time::Instant::now();
                        let detail = candidate.process(stage, &self.control, false)?;
                        candidate.stages[stage] = Stage {
                            status: "complete".into(),
                            detail,
                            seconds: start.elapsed().as_secs_f64(),
                        };
                    }
                    for index in recipe.excluded_tracks {
                        let track = candidate.tracks.get_mut(index).ok_or(
                            "Recipe track identities no longer reproduce with this engine.",
                        )?;
                        track.excluded = true;
                    }
                    if let Some(saved) = recipe.selected_cell {
                        let _ = candidate.process(2, &self.control, false);
                        let index = candidate
                            .cells
                            .iter()
                            .position(|c| {
                                c.direct
                                    .iter()
                                    .flatten()
                                    .zip(saved.direct.iter().flatten())
                                    .all(|(a, b)| (a - b).abs() < 1e-10)
                            })
                            .ok_or(
                                "Saved cell does not reproduce. The preceding session is retained.",
                            )?;
                        candidate.selected = Some(index);
                        candidate.stages[2] = Stage {
                            status: "complete".into(),
                            detail: "Reproduced and restored the user-selected cell.".into(),
                            seconds: 0.,
                        };
                    }
                }
                candidate.notice = Some(
                    if recipe.engine == ENGINE && recipe.adapter == adapter_identity() {
                        "Recipe sources verified; settings and decisions restored. Run to rebuild remaining products.".into()
                    } else {
                        format!(
                            "Recipe engine or adapter revision differs from this build (saved engine: {}; current: {ENGINE}). Source hashes verified; numerical products must be revalidated.",
                            recipe.engine
                        )
                    },
                );
                candidate.preview("raw")?;
                self.scxrd = candidate;
            }
            "save" => {
                self.scxrd.sources_check()?;
                if self.scxrd.config.integration_method == "profile"
                    && self.scxrd.tracks.iter().any(|t| t.excluded)
                {
                    return Err("Clear unsupported manual track exclusions or select summation before saving a profile recipe.".into());
                }
                // A recipe identifies every frame by its decoded counts; hash the
                // frames that processing has not read yet.
                for i in 0..self.scxrd.sources.len() {
                    if self.scxrd.sources[i].digest.get().is_none() {
                        self.control.check()?;
                        self.scxrd.read(i)?;
                        self.control.publish(json!({"running":true,"current":i+1,"total":self.scxrd.sources.len(),"label":"Hashing frames for the recipe"}));
                    }
                }
                let c = &self.scxrd;
                let recipe = Recipe {
                    schema: "dioptas.scxrd.rust".into(),
                    version: 1,
                    engine: ENGINE.into(),
                    adapter: adapter_identity().into(),
                    config: c.config.clone(),
                    sources: c.sources.clone(),
                    protected_sources: c.protected_sources.clone(),
                    calibration_source: c.calibration_source.clone(),
                    shape: c.shape,
                    geometry: c.initial_geometry,
                    mask: c.mask.clone(),
                    excluded_frames: c.excluded_frames.clone(),
                    excluded_tracks: c
                        .tracks
                        .iter()
                        .enumerate()
                        .filter(|(_, t)| t.excluded)
                        .map(|(i, _)| i)
                        .collect(),
                    selected_cell: if c.config.integration_method == "profile" {
                        None
                    } else {
                        c.selected.map(|i| c.cells[i].clone())
                    },
                };
                let bytes = serde_json::to_vec_pretty(&recipe).map_err(err)?;
                if bytes.len() > 8 * 1024 * 1024 {
                    return Err("Recipe exceeds the 8 MiB portable metadata limit. Select a smaller source set.".into());
                }
                atomic(&path, |w| w.write_all(&bytes).map_err(err))?;
            }
            "reflections" => {
                if self.scxrd.reflections.is_empty() {
                    return Err("Integrate the scan before exporting reflections.".into());
                }
                atomic(&path, |w| {
                    writeln!(w,"# Dioptas SCXRD · {ENGINE}\n# Integration: {}. Signed observations and original quality flags retained. No absorption correction. Missing identity = -1; eligibility is the usable column, not flags == 0.\n# h k l I sigma_I omega_deg flags detected_track predicted_crossing correction usable",self.scxrd.config.integration_method).map_err(err)?;
                    for r in &self.scxrd.reflections {
                        writeln!(
                            w,
                            "{} {} {} {:.12e} {:.12e} {:.9} {} {} {} {:.12e} {}",
                            r.hkl[0],
                            r.hkl[1],
                            r.hkl[2],
                            r.intensity,
                            r.sigma,
                            r.omega,
                            r.flags,
                            r.track.map(|id| id as i64).unwrap_or(-1),
                            r.crossing.map(|id| id as i64).unwrap_or(-1),
                            r.correction,
                            u8::from(r.usable())
                        )
                        .map_err(err)?;
                    }
                    Ok(())
                })?;
            }
            "hkl" => {
                let usable: Vec<_> = self
                    .scxrd
                    .reflections
                    .iter()
                    .filter(|r| r.usable())
                    .collect();
                if usable.is_empty() {
                    return Err("Integrate usable reflections before exporting HKLF4.".into());
                }
                if usable.iter().any(|r| r.hkl.iter().any(|h| h.abs() > 999)) {
                    return Err("Miller indices exceed the HKLF4 field width; export the complete observation table instead.".into());
                }
                let max = usable
                    .iter()
                    .map(|r| r.intensity.abs().max(r.sigma))
                    .fold(1., f64::max);
                let scale = (9999. / max).min(1.);
                if usable.iter().any(|r| {
                    format!("{:.2}", r.sigma * scale)
                        .parse::<f64>()
                        .map_or(true, |v| v <= 0.)
                }) {
                    return Err("HKLF4 cannot preserve positive uncertainties at this dynamic range. Export the full-precision observation table instead.".into());
                }
                atomic(&path, |w| {
                    for r in usable {
                        writeln!(
                            w,
                            "{:4}{:4}{:4}{:8.2}{:8.2}",
                            r.hkl[0],
                            r.hkl[1],
                            r.hkl[2],
                            r.intensity * scale,
                            r.sigma * scale
                        )
                        .map_err(err)?;
                    }
                    writeln!(w, "{:4}{:4}{:4}{:8.2}{:8.2}", 0, 0, 0, 0., 0.).map_err(err)?;
                    Ok(())
                })?;
            }
            "cif" => {
                let cif = self
                    .scxrd
                    .cif
                    .as_ref()
                    .ok_or("Search for a structure candidate before exporting its CIF.")?;
                atomic(&path, |w| w.write_all(cif.as_bytes()).map_err(err))?;
            }
            _ => return Err("Unknown SCXRD file operation.".into()),
        }
        if matches!(
            op,
            "save" | "reflections" | "hkl" | "cif" | "protocol_save" | "audit"
        ) && !self.scxrd.saved_exports.contains(&path)
        {
            self.scxrd.saved_exports.push(path.clone());
        }
        let mut reply = self.scxrd.reply();
        if matches!(
            op,
            "save" | "reflections" | "hkl" | "cif" | "protocol_save" | "audit"
        ) {
            reply.result["savedPath"] = json!(path);
        }
        Ok(reply)
    }
}
impl Crystal {
    pub(super) fn set_poni(&mut self, g: &crate::geometry::Geometry) -> Result<(), String> {
        let mut g = g.clone();
        if !self.shape.contains(&0) {
            g.sync_shape(self.shape)?;
        }
        g.validate()?;
        if g.distortion_file.is_some()
            || g.detector.as_ref().is_some_and(|d| {
                !matches!(d.map, dioptrin::detector::PixelMap::Uniform)
                    || d.spline.is_some()
                    || !matches!(d.orientation, 0 | 3)
            })
        {
            return Err("SCXRD currently requires an affine planar detector without spline/distortion/orientation overrides. Keep the preceding geometry or load a uniform-detector PONI.".into());
        }
        let (s1, c1) = g.rot1.sin_cos();
        let (s2, c2) = g.rot2.sin_cos();
        let (s3, c3) = g.rot3.sin_cos();
        let rz = Matrix3::new(c3, -s3, 0., s3, c3, 0., 0., 0., 1.);
        let ry = Matrix3::new(c2, 0., -s2, 0., 1., 0., s2, 0., c2);
        let rx = Matrix3::new(1., 0., 0., 0., c1, s1, 0., -s1, c1);
        let r = rz * ry * rx;
        let mv = |a: V3| {
            let v = r * nalgebra::Vector3::from(a);
            [v[0], v[1], v[2]]
        };
        let geometry = Geometry {
            origin: mv([g.pixel1 / 2. - g.poni1, g.pixel2 / 2. - g.poni2, g.dist]),
            fast: mv([0., g.pixel2, 0.]),
            slow: mv([g.pixel1, 0., 0.]),
            beam: [0., 0., 1.],
            axis: self.config.axis,
            wavelength: g.wavelength * 1e10,
        };
        geometry.native().convert(&[[0., 0., 0.]]).map_err(err)?;
        self.initial_geometry = Some(geometry);
        self.geometry = Some(geometry);
        self.poni = Some(g);
        self.invalidate(0);
        Ok(())
    }
}
use nalgebra::Matrix3;
