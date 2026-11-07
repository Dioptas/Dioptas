//! Reuses the native engine; no numerical kernels are copied into the host.
use crate::{display::Raster, geometry::Geometry as Parameters, image::Image};
use dioptrin::{
    geometry::Geometry,
    integration::{IntegrationMethod, Integrator, RadialUnit},
    mask::Mask,
};
use serde_json::{Value, json};

pub struct Products {
    pub pattern: Value,
    pub cake: Raster,
    pub cake_values: Vec<f64>,
    pub sigma: Option<Vec<f64>>,
}

pub struct Options<'a> {
    pub bins: usize,
    pub cake_bins: usize,
    pub unit: &'a str,
    pub polarization: f64,
    pub errors: bool,
}

pub fn integrate(
    image: &Image,
    parameters: &Parameters,
    mask: &[u8],
    options: Options<'_>,
) -> Products {
    let Options {
        bins,
        cake_bins,
        unit,
        polarization,
        errors,
    } = options;
    let poni = parameters.native_poni();
    let [height, width] = image.shape;
    let mut integrator = Integrator::new(Geometry::new(height, width, poni))
        .with_method(IntegrationMethod::PixelSplit)
        .with_fast_math(false)
        .with_polarization_factor(polarization)
        .with_radial_unit(if unit == "q_A^-1" {
            RadialUnit::QAngstrom
        } else {
            RadialUnit::TthDeg
        });
    integrator.set_mask(Mask {
        data: mask.to_vec(),
        dim1: height,
        dim2: width,
    });
    let (mut x, y, sigma) = if errors {
        let (x, y, sigma) =
            integrator.integrate1d_with_errors_from_slice(&image.values, height, width, bins);
        (x, y, Some(sigma))
    } else {
        let (x, y) = integrator.integrate1d_from_slice(&image.values, height, width, bins);
        (x, y, None)
    };
    if unit == "d_A" {
        for value in &mut x {
            *value = parameters.wavelength * 1e10 / (2.0 * (value.to_radians() / 2.0).sin());
        }
    }
    // As in the current desktop, cake coordinates remain 2theta for every
    // pattern unit. Explicit ±pi grid avoids an inferred azimuth extent.
    integrator.set_radial_unit(RadialUnit::TthDeg);
    let pixels = integrator.integrate2d_with_azimuthal_range_from_slice(
        &image.values,
        height,
        width,
        bins,
        cake_bins,
        -std::f64::consts::PI + std::f64::consts::PI / cake_bins as f64,
        std::f64::consts::TAU / cake_bins as f64,
    );
    // PixelSplit bins cover pixel CORNERS, rather than the center-array extent.
    // Use the engine's own geometry API for these coordinates. Its public 2D
    // result currently contains pixels only; keep this adapter aligned with
    // Dioptrin's PixelSplit range contract (including its upper-edge epsilon).
    let geometry = integrator.geometry();
    let (rows, columns) = geometry.corner_grid();
    let (angles, _) = geometry.calc_tth_and_azimuth(&rows, &columns);
    let radial = RadialUnit::TthDeg.convert_from_tth(&angles, parameters.wavelength);
    let low = radial.iter().copied().fold(f64::INFINITY, f64::min);
    let high = radial.iter().copied().fold(f64::NEG_INFINITY, f64::max) + 10.0 * f64::EPSILON;
    let half_step = (high - low) / (2.0 * bins as f64);
    let mut cake = Raster::image(&pixels, [cake_bins, bins]);
    cake.metadata["radialRange"] = json!([low + half_step, high - half_step]);
    cake.metadata["azimuthRange"] = json!([
        -180.0 + 180.0 / cake_bins as f64,
        180.0 - 180.0 / cake_bins as f64
    ]);
    cake.metadata["unit"] = json!("2th_deg");
    Products {
        pattern: json!({"x": x, "y": y, "unit": unit}),
        cake,
        cake_values: pixels,
        sigma,
    }
}
