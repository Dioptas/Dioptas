//! Pattern/background/overlay state independent of detector integration plans.
use crate::background_fit::ChebyshevFit;
use crate::control::Control;
use serde_json::{Value, json};
use std::{io::Read, path::Path, sync::Arc};
pub(crate) fn convert_coordinate(value: f64, from: &str, to: &str, wavelength: f64) -> f64 {
    if from == to {
        return value;
    }
    let tau = 2.0 * std::f64::consts::PI;
    let lambda = wavelength * 1e10;
    let q = match from {
        "2th_deg" => 2.0 * tau * (value.to_radians() / 2.0).sin() / lambda,
        "q_A^-1" => value,
        "q_nm^-1" => value / 10.0,
        "d_A" => tau / value,
        _ => f64::NAN,
    };
    match to {
        "2th_deg" => 2.0 * (q * lambda / (2.0 * tau)).asin().to_degrees(),
        "q_A^-1" => q,
        "q_nm^-1" => 10.0 * q,
        "d_A" => tau / q,
        _ => f64::NAN,
    }
}
#[derive(Clone, PartialEq, serde::Serialize, serde::Deserialize)]
pub(crate) struct Curve {
    #[serde(with = "crate::history_transfer::arc")]
    pub x: Arc<Vec<f64>>,
    #[serde(with = "crate::history_transfer::arc")]
    pub y: Arc<Vec<f64>>,
    #[serde(with = "crate::history_transfer::optional_arc")]
    pub sigma: Option<Arc<Vec<f64>>>,
    #[serde(with = "crate::history_transfer::optional_arc")]
    pub spread: Option<Arc<Vec<f64>>>,
}
impl Curve {
    pub fn from_json(v: &Value) -> Result<Self, String> {
        let parse = |key| {
            v[key]
                .as_array()
                .ok_or("Missing pattern array.")?
                .iter()
                .map(|v| {
                    v.as_f64()
                        .or_else(|| (key == "y" && v.is_null()).then_some(f64::NAN))
                        .ok_or("Pattern contains unavailable samples.")
                })
                .collect::<Result<Vec<_>, _>>()
        };
        let x = parse("x")?;
        let y = parse("y")?;
        if x.len() != y.len() {
            return Err("Pattern arrays differ in length.".into());
        }
        for key in ["sigma", "azimuthalStd"] {
            if v[key].as_array().is_some_and(|a| a.len() != x.len()) {
                return Err("Pattern uncertainty arrays differ in length.".into());
            }
        }
        Ok(Self {
            x: Arc::new(x),
            y: Arc::new(y),
            sigma: v
                .get("sigma")
                .and_then(Value::as_array)
                .map(|a| {
                    a.iter()
                        .map(|v| v.as_f64().ok_or("Pattern errors are unavailable."))
                        .collect::<Result<Vec<_>, _>>()
                })
                .transpose()?
                .map(Arc::new),
            spread: v["azimuthalStd"]
                .as_array()
                .map(|a| Arc::new(a.iter().map(|v| v.as_f64().unwrap_or(f64::NAN)).collect())),
        })
    }
    pub fn read(path: &Path) -> Result<Self, String> {
        let mut text = String::new();
        std::fs::File::open(path)
            .map_err(|e| e.to_string())?
            .take(64 * 1024 * 1024 + 1)
            .read_to_string(&mut text)
            .map_err(|e| e.to_string())?;
        if text.len() > 64 * 1024 * 1024 {
            return Err("Pattern file exceeds 64 MiB.".into());
        }
        let skip = if path
            .extension()
            .is_some_and(|s| s.eq_ignore_ascii_case("chi"))
        {
            4
        } else {
            0
        };
        let mut x = Vec::new();
        let mut y = Vec::new();
        let mut errors = Vec::new();
        let mut has_errors = true;
        let fxye = text.lines().position(|l| l.starts_with("BANK "));
        let factor = fxye.map_or(1.0, |i| {
            if text.lines().nth(i).unwrap().contains("CONQ") {
                1.0
            } else {
                100.0
            }
        });
        for line in text.lines().skip(fxye.map_or(skip, |i| i + 1)) {
            let line = line.split('#').next().unwrap().trim();
            if line.is_empty() {
                continue;
            }
            let fields = line
                .split(|c: char| c.is_whitespace() || c == ',')
                .filter(|s| !s.is_empty())
                .collect::<Vec<_>>();
            if fields.len() < 2 {
                return Err("Wrong data format for pattern file.".into());
            }
            let a = fields[0]
                .parse::<f64>()
                .map_err(|_| "Invalid pattern coordinate.")?;
            let b = fields[1]
                .parse::<f64>()
                .map_err(|_| "Invalid pattern intensity.")?;
            if !a.is_finite() || !b.is_finite() {
                return Err("Pattern file needs finite coordinates and intensities.".into());
            }
            x.push(a / factor);
            y.push(b);
            if fields.len() > 2 {
                errors.push(
                    fields[2]
                        .parse::<f64>()
                        .map_err(|_| "Invalid pattern error.")?,
                );
            } else {
                has_errors = false;
            }
            if x.len() > 1_000_000 {
                return Err("Pattern file exceeds one million samples.".into());
            }
        }
        if x.is_empty() {
            return Err("Pattern file has no samples.".into());
        }
        // Like the current PatternModel, imported error columns do not claim
        // propagated integration errors. Preserve numerical-unit semantics.
        let _ = (errors, has_errors);
        Ok(Self {
            x: Arc::new(x),
            y: Arc::new(y),
            sigma: None,
            spread: None,
        })
    }
    pub fn json(&self) -> Value {
        json!({"x":self.x,"y":self.y})
    }
}
#[derive(Clone, PartialEq, serde::Serialize, serde::Deserialize)]
pub(crate) struct Background {
    pub enabled: bool,
    pub smoothing: f64,
    pub iterations: usize,
    pub order: usize,
    pub range: Option<[f64; 2]>,
}
impl Background {
    /// One typed validation boundary for live edits and persisted projects.
    /// Order zero and the wider smoothing interval retain legacy project support.
    pub(crate) fn from_value(value: Value) -> Result<Self, String> {
        let settings: Self = serde_json::from_value(value)
            .map_err(|e| format!("Invalid pattern background settings: {e}"))?;
        if !settings.smoothing.is_finite() || !(1e-9..=1e9).contains(&settings.smoothing) {
            return Err("Background smoothing must be between 1e-9 and 1e9.".into());
        }
        if !(1..=99999).contains(&settings.iterations) {
            return Err("Background iterations must be between 1 and 99999.".into());
        }
        if settings.order > 1000 {
            return Err("Background polynomial order must be between 0 and 1000.".into());
        }
        if let Some([low, high]) = settings.range
            && (!low.is_finite() || !high.is_finite() || low < -1e12 || high > 1e12 || low >= high)
        {
            return Err("Background range needs finite, increasing bounds within ±1e12.".into());
        }
        Ok(settings)
    }
}
impl Default for Background {
    fn default() -> Self {
        Self {
            enabled: false,
            smoothing: 0.1,
            iterations: 150,
            order: 50,
            range: None,
        }
    }
}
#[derive(Clone, PartialEq, serde::Serialize, serde::Deserialize)]
pub(crate) struct Overlay {
    pub uid: String,
    pub name: String,
    pub visible: bool,
    pub color: String,
    pub scale: f64,
    pub offset: f64,
    #[serde(with = "crate::history_transfer::arc")]
    pub data: Arc<Curve>,
    #[serde(default)]
    pub batch_source: Option<crate::batch_waterfall::Source>,
}
impl Overlay {
    fn coordinates(&self, unit: &str) -> Result<Arc<Vec<f64>>, String> {
        if let Some(source) = &self.batch_source {
            Ok(Arc::new(source.coordinates(&self.data.x, unit)?))
        } else {
            Ok(self.data.x.clone())
        }
    }
    pub fn curve(&self, unit: &str) -> Result<Curve, String> {
        Ok(Curve {
            x: self.coordinates(unit)?,
            y: Arc::new(
                self.data
                    .y
                    .iter()
                    .map(|v| v * self.scale + self.offset)
                    .collect(),
            ),
            sigma: self
                .data
                .sigma
                .as_ref()
                .map(|s| Arc::new(s.iter().map(|v| v * self.scale.abs()).collect())),
            spread: self
                .data
                .spread
                .as_ref()
                .map(|s| Arc::new(s.iter().map(|v| v * self.scale.abs()).collect())),
        })
    }
}
#[derive(Clone, PartialEq, serde::Serialize, serde::Deserialize)]
pub(crate) struct Patterns {
    #[serde(with = "crate::history_transfer::optional_arc")]
    pub raw: Option<Arc<Curve>>,
    pub name: String,
    pub path: Option<String>,
    pub unit: String,
    pub imported: bool,
    pub color: String,
    pub visible: bool,
    pub background: Background,
    pub overlays: Vec<Overlay>,
    pub background_uid: Option<String>,
    #[serde(with = "crate::history_transfer::optional_arc")]
    pub anonymous_background: Option<Arc<Curve>>,
    pub separation: f64,
    pub directory: String,
    pub file_mode: String,
    next_uid: u64,
    #[serde(with = "crate::history_transfer::optional_arc")]
    pub extracted: Option<Arc<Curve>>,
}
impl Default for Patterns {
    fn default() -> Self {
        Self {
            raw: None,
            name: String::new(),
            path: None,
            unit: "2th_deg".into(),
            imported: false,
            color: "#ffffff".into(),
            visible: true,
            background: Default::default(),
            overlays: vec![],
            background_uid: None,
            anonymous_background: None,
            separation: crate::waterfall_spacing::DEFAULT_SPACING,
            directory: String::new(),
            file_mode: "number".into(),
            next_uid: 1,
            extracted: None,
        }
    }
}
pub fn color(v: &Value) -> Result<String, String> {
    let s = v.as_str().ok_or("Choose a color.")?;
    if s.len() != 7 || !s.starts_with('#') || !s[1..].bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err("Use a six-digit hexadecimal color.".into());
    }
    Ok(s.to_ascii_lowercase())
}
pub fn finite(v: &Value, name: &str, low: f64, high: f64) -> Result<f64, String> {
    v.as_f64()
        .filter(|v| v.is_finite() && *v >= low && *v <= high)
        .ok_or_else(|| format!("Invalid {name}."))
}
fn boolean(v: &Value) -> Result<bool, String> {
    v.as_bool().ok_or("Value must be a boolean.".into())
}
pub fn interpolate(x: &[f64], y: &[f64], value: f64) -> Option<f64> {
    if x.len() != y.len() || x.is_empty() {
        return None;
    }
    if x.len() == 1 {
        return (x[0] == value).then_some(y[0]);
    }
    let descending = x[0] > *x.last().unwrap();
    if value < x[0].min(*x.last().unwrap()) || value > x[0].max(*x.last().unwrap()) {
        return None;
    }
    let k = x.partition_point(|v| if descending { *v > value } else { *v < value });
    if k == 0 {
        return Some(y[0]);
    }
    if k == x.len() {
        return Some(y[k - 1]);
    }
    let span = x[k] - x[k - 1];
    if span == 0.0 {
        return Some(y[k]);
    }
    Some(y[k - 1] + (value - x[k - 1]) / span * (y[k] - y[k - 1]))
}
impl Patterns {
    pub fn restore_global(&mut self, source: &Self) {
        if self.overlays != source.overlays {
            self.extracted = None;
        }
        if self
            .background_uid
            .as_ref()
            .is_some_and(|uid| !source.overlays.iter().any(|o| o.uid == *uid))
        {
            self.background_uid = None;
        }
        self.overlays = source.overlays.clone();
        self.directory = source.directory.clone();
        self.separation = source.separation;
        self.next_uid = self.next_uid.max(source.next_uid);
    }
    pub fn project_overlay_ids(&mut self) {
        let maximum = self
            .overlays
            .iter()
            .filter_map(|o| o.uid.strip_prefix("native-overlay-")?.parse::<u64>().ok())
            .max()
            .unwrap_or(0);
        self.next_uid = self.next_uid.max(maximum.saturating_add(1));
    }
    pub fn retain_counter(&mut self, source: &Self) {
        self.next_uid = self.next_uid.max(source.next_uid);
    }

    pub fn convert_unit(&mut self, to: &str, wavelength: f64) -> Result<(), String> {
        let from = self.unit.clone();
        if from == to {
            return Ok(());
        }
        let convert = |x| convert_coordinate(x, &from, to, wavelength);
        if let Some(range) = self.background.range {
            let mut converted = [convert(range[0]), convert(range[1])];
            if converted.iter().all(|v| v.is_finite()) {
                converted.sort_by(f64::total_cmp);
                self.background.range = Some(converted);
            } else {
                self.background.range = None;
            }
        }
        if self.imported
            && let Some(raw) = &mut self.raw
        {
            let x: Vec<_> = raw.x.iter().map(|&x| convert(x)).collect();
            if x.iter().any(|x| !x.is_finite()) {
                return Err(
                    "Pattern coordinates cannot be converted at the current wavelength.".into(),
                );
            }
            Arc::make_mut(raw).x = Arc::new(x);
        }
        self.unit = to.into();
        self.extracted = None;
        Ok(())
    }
    pub fn ingest(
        &mut self,
        mut curve: Curve,
        unit: &str,
        name: &str,
        path: Option<String>,
        imported: bool,
    ) {
        if self.background.enabled && curve.x.len() > 1 && curve.x[0] > *curve.x.last().unwrap() {
            curve.x = Arc::new(curve.x.iter().rev().copied().collect());
            curve.y = Arc::new(curve.y.iter().rev().copied().collect());
            curve.sigma = curve
                .sigma
                .map(|v| Arc::new(v.iter().rev().copied().collect()));
            curve.spread = curve
                .spread
                .map(|v| Arc::new(v.iter().rev().copied().collect()));
        }
        self.raw = Some(Arc::new(curve));
        self.unit = unit.into();
        self.name = name.into();
        self.path = path;
        self.imported = imported;
        self.extracted = None;
    }
    pub fn details(&self) -> Value {
        json!({"patternName":self.name,"patternPath":if self.imported{self.path.clone().unwrap_or_default()}else{String::new()},"originalPatternColor":self.color,"originalPatternVisible":self.visible,
        "patternFileIteration":self.file_mode,"patternBackground":{"enabled":self.background.enabled,"smoothing":self.background.smoothing,"iterations":self.background.iterations,"order":self.background.order,"range":self.background.range,"overlay":self.background_uid.is_some()||self.anonymous_background.is_some()},
        "supportsOverlayUids":true,"overlays":self.overlays.iter().map(|o|json!({"uid":o.uid,"name":o.name,"visible":o.visible,"color":o.color,"scale":o.scale,"offset":o.offset,"background":self.background_uid.as_ref()==Some(&o.uid),"batchSource":o.batch_source})).collect::<Vec<_>>(),"waterfallSeparation":self.separation,"overlayDirectory":self.directory})
    }
    pub fn configure_background(&mut self, args: &Value) -> Result<(), String> {
        let enabled = boolean(&args["enabled"])?;
        // Enabling without explicit fields retains the established reset-to-defaults
        // behavior; disabling without fields retains the current draft.
        let defaults = if enabled {
            Background::default()
        } else {
            self.background.clone()
        };
        let mut value = serde_json::to_value(defaults).map_err(|e| e.to_string())?;
        value["enabled"] = json!(enabled);
        for key in ["smoothing", "iterations", "order", "range"] {
            if let Some(field) = args.get(key) {
                value[key] = field.clone();
            }
        }
        let mut b = Background::from_value(value)?;
        if enabled && self.raw.is_none() {
            return Err("Load or integrate a pattern first.".into());
        }
        if let Some(raw) = &self.raw
            && raw.x.len() > 1
        {
            let mut ids: (Vec<usize>, Vec<f64>) = ((0..raw.x.len()).collect(), vec![]);
            ids.0.sort_by(|&a, &b| raw.x[a].total_cmp(&raw.x[b]));
            ids.1 = ids.0.iter().map(|&i| raw.x[i]).collect();
            if self.background.enabled || enabled {
                self.raw = Some(Arc::new(Curve {
                    x: Arc::new(ids.1.clone()),
                    y: Arc::new(ids.0.iter().map(|&i| raw.y[i]).collect()),
                    sigma: raw
                        .sigma
                        .as_ref()
                        .map(|v| Arc::new(ids.0.iter().map(|&i| v[i]).collect())),
                    spread: raw
                        .spread
                        .as_ref()
                        .map(|v| Arc::new(ids.0.iter().map(|&i| v[i]).collect())),
                }));
            }
            if let Some(r) = &mut b.range {
                let x = &ids.1;
                let step = x[1] - x[0];
                r[0] = r[0].max(x[0] - step / 2.0).min(x[x.len() - 1] - 1.5 * step);
                r[1] = r[1].min(x[x.len() - 1] + step / 2.0).max(x[0] + 1.5 * step);
            }
        }
        self.background = b;
        self.extracted = None;
        Ok(())
    }
    pub fn build(&mut self, control: &Control) -> Result<Option<Value>, String> {
        self.build_with_progress(control, true, None)
    }
    pub(crate) fn build_background_row(
        &mut self,
        control: &Control,
        prepared: &mut Option<Arc<ChebyshevFit>>,
    ) -> Result<Option<Value>, String> {
        self.build_with_progress(control, false, Some(prepared))
    }
    fn build_with_progress(
        &mut self,
        control: &Control,
        progress: bool,
        prepared: Option<&mut Option<Arc<ChebyshevFit>>>,
    ) -> Result<Option<Value>, String> {
        let mut curves = vec![];
        for o in &self.overlays {
            if o.visible {
                let curve = o.curve(&self.unit)?;
                let mut v = curve.json();
                v["sigma"] = json!(curve.sigma);
                v["azimuthalStd"] = json!(curve.spread);
                v["name"] = json!(o.name);
                v["color"] = json!(o.color);
                curves.push(v);
            }
        }
        let Some(raw) = &self.raw else {
            return Ok((!curves.is_empty())
                .then(|| json!({"x":[],"y":[],"unit":self.unit,"curves":curves,"phaseLines":[]})));
        };
        let mut x = raw.x.as_ref().clone();
        let mut y = raw.y.as_ref().clone();
        let mut indices: Vec<_> = (0..x.len()).collect();
        if let Some(curve) = self
            .overlays
            .iter()
            .find(|o| Some(&o.uid) == self.background_uid.as_ref())
            .map(|o| o.curve(&self.unit))
            .transpose()?
            .or_else(|| {
                self.anonymous_background
                    .as_ref()
                    .map(|c| c.as_ref().clone())
            })
        {
            let mut xx = vec![];
            let mut yy = vec![];
            let mut ii = vec![];
            for (i, (&a, &b)) in x.iter().zip(&y).enumerate() {
                if let Some(v) = interpolate(&curve.x, &curve.y, a) {
                    xx.push(a);
                    yy.push(b - v);
                    ii.push(i);
                }
            }
            if xx.is_empty() {
                return Err("The background and pattern do not overlap.".into());
            }
            x = xx;
            y = yy;
            indices = ii;
        }
        let mut inspection = vec![];
        if self.background.enabled {
            if let Some([low, high]) = self.background.range {
                let ids: Vec<_> = x
                    .iter()
                    .enumerate()
                    .filter_map(|(i, &v)| (v > low && v < high).then_some(i))
                    .collect();
                x = ids.iter().map(|&i| x[i]).collect();
                y = ids.iter().map(|&i| y[i]).collect();
                indices = ids.iter().map(|&i| indices[i]).collect();
            }
            if x.len() < 2 {
                return Err(
                    "Background range must include at least two distinct pattern samples.".into(),
                );
            }
            let background = if let Some(cached) = &self.extracted {
                cached.clone()
            } else {
                control.check()?;
                if progress {
                    control.publish(json!({"running":true,"current":0,"total":2,"label":"Smoothing pattern background"}));
                }
                let points = (self.background.smoothing / (x[1] - x[0])).abs() as usize;
                if points > 2_000_000 {
                    return Err(
                        "Background smoothing window exceeds the bounded working allocation."
                            .into(),
                    );
                }
                let smoothed = crate::batch_background::smooth_cancellable(
                    &y,
                    points,
                    self.background.iterations,
                    control,
                )?;
                control.check()?;
                if progress {
                    control.publish(json!({"running":true,"current":1,"total":2,"label":"Fitting background polynomial"}));
                }
                let fitted = if let Some(slot) = prepared {
                    if slot
                        .as_ref()
                        .is_none_or(|p| !p.matches(&x, self.background.order))
                    {
                        *slot = Some(Arc::new(ChebyshevFit::new(&x, self.background.order)?));
                    }
                    slot.as_ref().unwrap().fit(&smoothed)?
                } else {
                    chebyshev(&x, &smoothed, self.background.order)?
                };
                let bg = Arc::new(Curve {
                    x: Arc::new(x.clone()),
                    y: Arc::new(fitted),
                    sigma: None,
                    spread: None,
                });
                self.extracted = Some(bg.clone());
                bg
            };
            for (v, b) in y.iter_mut().zip(background.y.iter()) {
                *v -= b;
            }
            inspection
                .push(json!({"name":"Original pattern","color":"#8196a6","x":raw.x,"y":raw.y}));
            inspection.push(json!({"name":"Fitted background","color":"#73bba6","x":background.x,"y":background.y}));
        }
        control.check()?;
        let errors = raw
            .sigma
            .as_ref()
            .map(|s| indices.iter().map(|&i| s[i]).collect::<Vec<_>>());
        let spread = raw
            .spread
            .as_ref()
            .map(|s| indices.iter().map(|&i| s[i]).collect::<Vec<_>>());
        Ok(Some(
            json!({"x":x,"y":y,"unit":self.unit,"curves":curves,"phaseLines":[],"backgroundCurves":inspection,"sigma":errors,"azimuthalStd":spread,"spottiness":crate::spottiness::diagnostic(raw)}),
        ))
    }
    fn set_background(&mut self, uid: Option<String>) {
        self.anonymous_background = None;
        if let Some(previous) = &self.background_uid
            && Some(previous) != uid.as_ref()
            && let Some(o) = self.overlays.iter_mut().find(|o| o.uid == *previous)
        {
            o.visible = true;
        }
        if let Some(uid) = &uid
            && let Some(o) = self.overlays.iter_mut().find(|o| o.uid == *uid)
        {
            o.visible = false;
        }
        self.background_uid = uid;
        self.extracted = None;
    }
    pub fn clear_background(&mut self) {
        self.set_background(None);
        self.extracted = None;
    }
    pub fn edit_overlay(&mut self, args: &Value, current: Option<&Value>) -> Result<(), String> {
        let op = args["operation"]
            .as_str()
            .ok_or("Choose an overlay operation.")?;
        match op {
            "original_color" => self.color = color(&args["color"])?,
            "original_visibility" => self.visible = boolean(&args["visible"])?,
            "load" => {
                let paths = if let Some(a) = args.get("paths") {
                    a.as_array()
                        .ok_or("Choose overlay files.")?
                        .iter()
                        .map(|p| p.as_str().ok_or("Overlay path must be text."))
                        .collect::<Result<Vec<_>, _>>()?
                } else {
                    vec![args["path"].as_str().ok_or("Choose overlay files.")?]
                };
                for path in paths {
                    let data = Curve::read(Path::new(path))?;
                    self.add(
                        data,
                        Path::new(path)
                            .file_stem()
                            .unwrap_or_default()
                            .to_string_lossy()
                            .into(),
                    );
                    self.directory = Path::new(path)
                        .parent()
                        .unwrap_or(Path::new("."))
                        .to_string_lossy()
                        .into();
                }
            }
            "capture" | "capture_background" => {
                let curve = Curve::from_json(current.ok_or("Load or integrate a pattern first.")?)?;
                if curve.x.is_empty() {
                    return Err("Load or integrate a pattern first.".into());
                }
                self.add(curve, self.name.clone());
                if op == "capture_background" {
                    self.set_background(self.overlays.last().map(|o| o.uid.clone()));
                }
            }
            "clear" => {
                self.overlays.clear();
                self.background_uid = None;
                self.visible = true;
                self.extracted = None;
            }
            "waterfall" | "waterfall_separation" | "waterfall_auto" => {
                self.separation = if op == "waterfall_auto" {
                    crate::waterfall_spacing::estimate(
                        self.overlays.iter().map(|o| (o.data.y.as_slice(), o.scale)),
                    )
                } else if let Some(v) = args.get("separation") {
                    finite(v, "Separation", -100000.0, 100000.0)?
                } else {
                    self.separation
                };
                if op == "waterfall" || op == "waterfall_auto" {
                    let n = self.overlays.len();
                    for (i, o) in self.overlays.iter_mut().enumerate() {
                        o.offset = -self.separation * (n - i) as f64;
                    }
                }
            }
            "reset_offsets" => {
                for o in &mut self.overlays {
                    o.offset = 0.0;
                }
            }
            "visibility" => {
                let v = boolean(&args["visible"])?;
                for o in &mut self.overlays {
                    o.visible = v;
                }
            }
            "color_scale" => {
                let colors = args["colors"]
                    .as_array()
                    .filter(|a| a.len() == self.overlays.len())
                    .ok_or("Choose one color for every overlay.")?
                    .iter()
                    .map(color)
                    .collect::<Result<Vec<_>, _>>()?;
                for (o, c) in self.overlays.iter_mut().zip(colors) {
                    o.color = c;
                }
            }
            _ => {
                // A queued reorder/removal changes indices. Resolve stable identities
                // when the edit executes, and never redirect a missing UID to an index.
                // Index-only clients remain supported for explicit Python compatibility.
                let i = if let Some(uid) = args.get("uid") {
                    let uid = uid.as_str().ok_or("Overlay identity must be text.")?;
                    self.overlays
                        .iter()
                        .position(|overlay| overlay.uid == uid)
                        .ok_or("The selected overlay no longer exists.")?
                } else {
                    args["index"]
                        .as_u64()
                        .and_then(|v| usize::try_from(v).ok())
                        .filter(|&i| i < self.overlays.len())
                        .ok_or("Choose an overlay.")?
                };
                match op {
                    "remove" => {
                        let o = self.overlays.remove(i);
                        if Some(&o.uid) == self.background_uid.as_ref() {
                            self.set_background(None);
                        }
                        if self.overlays.is_empty() {
                            self.visible = true;
                        }
                    }
                    "background" => {
                        let uid = self.overlays[i].uid.clone();
                        self.set_background(
                            (self.background_uid.as_ref() != Some(&uid)).then_some(uid),
                        );
                    }
                    "move" => {
                        let dir = args["direction"]
                            .as_i64()
                            .filter(|d| *d == 1 || *d == -1)
                            .ok_or("Direction must be -1 or 1.")?;
                        let target =
                            (i as i64 + dir).clamp(0, self.overlays.len() as i64 - 1) as usize;
                        self.overlays.swap(i, target);
                    }
                    "match_intensity" => {
                        if let Some(cur) = current {
                            let x = cur["x"].as_array().ok_or("Missing pattern.")?;
                            let y = cur["y"].as_array().unwrap();
                            let data = &self.overlays[i].data;
                            let coordinates = self.overlays[i].coordinates(&self.unit)?;
                            let (mut num, mut den) = (0.0, 0.0);
                            for (a, b) in x.iter().zip(y) {
                                if let (Some(a), Some(b)) = (a.as_f64(), b.as_f64())
                                    && let Some(v) = interpolate(&coordinates, &data.y, a)
                                {
                                    num += v * b;
                                    den += v * v;
                                }
                            }
                            if den != 0.0 {
                                self.overlays[i].scale = (num / den).max(0.0);
                                self.overlays[i].offset = 0.0;
                            }
                        }
                    }
                    "update" => {
                        for (key, v) in args.as_object().unwrap() {
                            match key.as_str() {
                                "operation" | "index" | "uid" => {}
                                "scale" => {
                                    self.overlays[i].scale =
                                        finite(v, "Scale", -9999999.0, 9999999.0)?.max(0.0)
                                }
                                "offset" => {
                                    self.overlays[i].offset =
                                        finite(v, "Offset", -9999999.0, 9999999.0)?
                                }
                                "name" => {
                                    self.overlays[i].name =
                                        v.as_str().ok_or("Overlay name must be text.")?.into()
                                }
                                "visible" => self.overlays[i].visible = boolean(v)?,
                                "color" => self.overlays[i].color = color(v)?,
                                _ => return Err("Unknown overlay option.".into()),
                            }
                        }
                    }
                    _ => return Err("Unknown overlay operation.".into()),
                }
                if Some(
                    &self
                        .overlays
                        .get(i)
                        .map(|o| o.uid.clone())
                        .unwrap_or_default(),
                ) == self.background_uid.as_ref()
                {
                    self.extracted = None;
                }
            }
        }
        Ok(())
    }
    pub(crate) fn replace_batch_waterfall(
        &mut self,
        curves: Vec<(Curve, String, crate::batch_waterfall::Source)>,
    ) -> Result<(), String> {
        // Qt replaces the overlay list. Preserve the current pattern and its background settings.
        self.overlays.clear();
        self.background_uid = None;
        self.extracted = None;
        for (curve, name, source) in curves {
            self.add(curve, name);
            self.overlays.last_mut().unwrap().batch_source = Some(source);
        }
        self.edit_overlay(&json!({"operation":"waterfall_auto"}), None)
    }
    fn add(&mut self, data: Curve, name: String) {
        let palette = ["#f0b66c", "#73bba6", "#82a6d6", "#d38fa5", "#b6a1da"];
        let uid = format!("native-overlay-{}", self.next_uid);
        self.next_uid += 1;
        let color = palette[self.overlays.len() % palette.len()].into();
        self.overlays.push(Overlay {
            uid,
            name,
            visible: true,
            color,
            scale: 1.0,
            offset: 0.0,
            data: Arc::new(data),
            batch_source: None,
        });
    }
}
pub(crate) fn chebyshev(x: &[f64], y: &[f64], degree: usize) -> Result<Vec<f64>, String> {
    ChebyshevFit::new(x, degree)?.fit(y)
}
