//! Desktop grid/unit adapters; the splitting algorithms live in Dioptrin.
use dioptrin::{
    geometry::Geometry,
    integration::{IntegrationGrid2d, PixelSplitMode, RadialUnit},
    lut::Lut1d,
};

pub fn radial_range(g: &Geometry, unit: RadialUnit) -> [f64; 2] {
    dioptrin::lut::pyfai_radial_range(g, unit)
}

pub fn build1d(
    g: &Geometry,
    unit: RadialUnit,
    bins: usize,
    azimuth: Option<[f64; 2]>,
    radial: Option<[f64; 2]>,
) -> Result<Lut1d, String> {
    dioptrin::lut::build_lut1d_pyfai_csr(
        g,
        unit,
        bins,
        azimuth.map(|range| crate::sector::angular(Some(range))),
        radial,
    )
}

pub fn grid2d(
    g: &Geometry,
    unit: RadialUnit,
    bins: usize,
    angular_bins: usize,
    azimuth: Option<[f64; 2]>,
    radial: Option<[f64; 2]>,
) -> Result<IntegrationGrid2d, String> {
    let [lo, hi] = radial.unwrap_or_else(|| radial_range(g, unit));
    let [a, b] = crate::sector::angular(azimuth);
    Ok(
        IntegrationGrid2d::new(bins, angular_bins, (lo, hi), (a, b))?
            .with_pixel_split_mode(PixelSplitMode::PyfaiHistogram),
    )
}
