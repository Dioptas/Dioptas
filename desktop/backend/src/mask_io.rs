//! Mask files retain Qt's stored-row convention, independently of detector I/O.
use super::*;
impl Session {
    pub(super) fn mask_file(&mut self, args: &Value) -> Result<Reply, String> {
        self.require_image()?;
        check_keys(
            args,
            &["path", "save", "add", "flipud", "defer_integration"],
        )?;
        let file = path(args)?;
        let shape = self.image.as_ref().unwrap().shape;
        let flip = args
            .get("flipud")
            .map_or(Ok(false), |v| boolean(v, "Flip mask rows"))?;
        if args
            .get("save")
            .map_or(Ok(false), |v| boolean(v, "Save mask"))?
        {
            let data = if flip {
                self.mask
                    .chunks_exact(shape[1])
                    .rev()
                    .flatten()
                    .copied()
                    .collect()
            } else {
                self.mask.as_ref().clone()
            };
            match file
                .extension()
                .unwrap_or_default()
                .to_string_lossy()
                .to_lowercase()
                .as_str()
            {
                "npy" => {
                    let prefix = format!(
                        "{{'descr': '|i1', 'fortran_order': False, 'shape': ({}, {}), }}",
                        shape[0], shape[1]
                    );
                    let padding = (64 - (10 + prefix.len() + 1) % 64) % 64;
                    let header = prefix + &" ".repeat(padding) + "\n";
                    let mut bytes = b"\x93NUMPY\x01\x00".to_vec();
                    bytes.extend_from_slice(&(header.len() as u16).to_le_bytes());
                    bytes.extend_from_slice(header.as_bytes());
                    bytes.extend_from_slice(&data);
                    atomic_write(file, &bytes)?;
                }
                "edf" => {
                    let header = format!(
                        "{{\nHeaderID = EH:000001:000000:000000 ;\nImage = 1 ;\nByteOrder = LowByteFirst ;\nDataType = SignedByte ;\nDim_1 = {} ;\nDim_2 = {} ;\nSize = {} ;\nEDF_HeaderSize = 512 ;\n",
                        shape[1],
                        shape[0],
                        data.len()
                    );
                    let mut bytes = header.into_bytes();
                    if bytes.len() > 510 {
                        return Err("EDF mask header exceeds its block.".into());
                    }
                    bytes.resize(510, b' ');
                    bytes.extend_from_slice(b"}\n");
                    bytes.extend_from_slice(&data);
                    atomic_write(file, &bytes)?;
                }
                _ => file_workflow::atomic_render(file, |out| {
                    let mut encoder =
                        tiff::encoder::TiffEncoder::new(out).map_err(|e| e.to_string())?;
                    encoder
                        .write_image::<tiff::encoder::colortype::Gray8>(
                            shape[1] as u32,
                            shape[0] as u32,
                            &data,
                        )
                        .map_err(|e| e.to_string())
                })?,
            }
            self.mask_filename = Some(file.to_string_lossy().into_owned());
            let mut reply = self.snapshot(false);
            reply.result["savedPath"] = json!(file);
            return Ok(reply);
        }
        let text_format = file
            .extension()
            .is_some_and(|e| e.eq_ignore_ascii_case("txt") || e.eq_ignore_ascii_case("dat"));
        let mut values: Vec<u8> = if text_format {
            use std::io::Read;
            let mut text = String::new();
            std::fs::File::open(file)
                .map_err(|e| e.to_string())?
                .take(64 * 1024 * 1024 + 1)
                .read_to_string(&mut text)
                .map_err(|e| e.to_string())?;
            if text.len() > 64 * 1024 * 1024 {
                return Err("Text mask exceeds 64 MiB.".into());
            }
            let rows: Vec<Vec<f64>> = text
                .lines()
                .map(|line| line.split('#').next().unwrap_or("").trim())
                .filter(|line| !line.is_empty())
                .map(|line| {
                    line.split_whitespace()
                        .map(|v| {
                            v.parse::<f64>()
                                .ok()
                                .filter(|v| v.is_finite())
                                .ok_or("Mask data must contain finite numeric values.")
                        })
                        .collect::<Result<Vec<_>, _>>()
                })
                .collect::<Result<Vec<_>, _>>()?;
            if rows.len() != shape[0] || rows.iter().any(|r| r.len() != shape[1]) {
                return Err("Mask dimensions do not match the current image.".into());
            }
            rows.into_iter()
                .flatten()
                .map(|v| u8::from(v != 0.0))
                .collect()
        } else {
            let image = Image::open(file, &json!({}))?;
            if image.shape != shape {
                return Err("Mask dimensions do not match the current image.".into());
            }
            if image.values.iter().any(|v| !v.is_finite()) {
                return Err("Mask data must contain finite numeric values.".into());
            }
            image
                .values
                .chunks_exact(shape[1])
                .rev()
                .flatten()
                .map(|v| u8::from(*v != 0.0))
                .collect()
        };
        if flip {
            values = values
                .chunks_exact(shape[1])
                .rev()
                .flatten()
                .copied()
                .collect();
        }
        let add = args
            .get("add")
            .map_or(Ok(false), |v| boolean(v, "Add mask"))?;
        let values = if add {
            values
                .iter()
                .zip(self.mask.iter())
                .map(|(a, b)| u8::from(*a != 0 || *b != 0))
                .collect()
        } else {
            values
        };
        self.replace_mask(values);
        if !add {
            self.mask_filename = Some(file.to_string_lossy().into_owned());
        }
        self.settings.use_mask = true;
        let defer = args
            .get("defer_integration")
            .map_or(Ok(false), |v| boolean(v, "Defer integration"))?;
        self.calculate(defer)?;
        self.revision += 1;
        Ok(self.snapshot(false))
    }
}
