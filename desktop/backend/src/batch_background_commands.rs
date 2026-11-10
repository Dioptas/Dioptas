//! Batch-only routing; Map and Integration retain their scientific owners.
use super::*;
pub(super) fn normalization_bins(b: &crate::series::Series, args: &Value) -> Result<Value, String> {
    let min = finite(&args["minimum"], "Normalization minimum", 0.0, 1e12)?;
    let max = finite(&args["maximum"], "Normalization maximum", 0.0, 1e12)?;
    if min >= max {
        return Err("Choose an increasing normalization interval.".into());
    }
    let axis = b.profile(0, args["unit"].as_str().unwrap_or(&b.unit))?.x;
    let ids: Vec<_> = axis
        .iter()
        .enumerate()
        .filter_map(|(i, &x)| (x >= min && x <= max).then_some(i))
        .collect();
    if ids.is_empty() {
        return Err("Normalization region contains no stored sample centers.".into());
    }
    let mut converted = args.clone();
    converted["start"] = json!(ids[0]);
    converted["stop"] = json!(ids.last().unwrap());
    Ok(converted)
}
impl Session {
    pub(super) fn batch_background_command(
        &mut self,
        action: &str,
        args: &Value,
    ) -> Result<Reply, String> {
        let control = self.control.clone();
        let b = self
            .batch
            .as_mut()
            .ok_or("Load and integrate batch images first.")?;
        b.configure_batch_background(args)?;
        if action == "batch_background_extract" {
            b.extract_batch_background(&control)?;
        }
        // A background display change never reloads detector images, reruns
        // Integration's own background, changes selection, or touches Map.
        self.revision += 1;
        let mut reply = self.snapshot(false);
        self.attach_batch(&mut reply);
        Ok(reply)
    }
}
