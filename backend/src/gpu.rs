//! Platform GPU backend detection and 1D/2D plan wrappers (Metal on macOS,
//! CUDA via dynamic loading on Windows/Linux). Always falls back cleanly to CPU
//! when no compatible GPU is available.
use serde::{Deserialize, Serialize};
use std::sync::OnceLock;

/// User-selectable compute backend for 1D/2D integration.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ComputeBackend {
    /// Automatically use the platform GPU (Metal on macOS, CUDA on Windows/Linux)
    /// when available and beneficial; otherwise run on CPU.
    #[default]
    Auto,
    /// Always run integration on CPU.
    Cpu,
    /// Prefer the platform GPU whenever supported by the integration options,
    /// falling back to CPU only if the GPU or option combination is unavailable.
    Gpu,
}

impl ComputeBackend {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Auto => "auto",
            Self::Cpu => "cpu",
            Self::Gpu => "gpu",
        }
    }

    pub fn parse(value: &str) -> Result<Self, String> {
        match value {
            "auto" => Ok(Self::Auto),
            "cpu" => Ok(Self::Cpu),
            "gpu" => Ok(Self::Gpu),
            _ => Err("Choose automatic, CPU or GPU compute backend.".into()),
        }
    }
}

/// Accumulation precision for GPU 1D/2D integration.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum GpuPrecision {
    /// Plain single-precision accumulation (fastest).
    F32,
    /// Compensated (Kahan/Neumaier) single-precision accumulation (default).
    #[default]
    F32Compensated,
    /// Double-precision accumulation (CUDA only; falls back to CPU on Metal).
    F64,
}

impl GpuPrecision {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::F32 => "f32",
            Self::F32Compensated => "f32_compensated",
            Self::F64 => "f64",
        }
    }

    pub fn parse(value: &str) -> Result<Self, String> {
        match value {
            "f32" => Ok(Self::F32),
            "f32_compensated" => Ok(Self::F32Compensated),
            "f64" => Ok(Self::F64),
            _ => Err("Choose f32, f32_compensated or f64 GPU precision.".into()),
        }
    }
}

/// Process-wide GPU availability probe result.
#[derive(Clone, Debug)]
pub struct GpuDeviceInfo {
    pub available: bool,
    /// Human-readable API name (`"Metal"` or `"CUDA"`), or `None` when unsupported.
    pub backend: Option<&'static str>,
    /// Detected GPU name (e.g. `"Apple M4 Pro"`, `"NVIDIA GeForce RTX 4090"`).
    pub device_name: Option<String>,
    /// Whether the platform GPU backend supports native `f64` kernels (CUDA: true, Metal: false).
    pub supports_f64: bool,
    /// Diagnostic reason when unavailable.
    pub reason: Option<String>,
}

/// Minimum detector pixel count before `ComputeBackend::Auto` prefers GPU for
/// interactive single-frame integration (avoids dispatch overhead on tiny
/// synthetic images while activating on all real area detectors).
pub const AUTO_MIN_PIXELS: usize = 256 * 256;

/// Probes the default GPU device once per process and caches the result.
pub fn device_info() -> &'static GpuDeviceInfo {
    static INFO: OnceLock<GpuDeviceInfo> = OnceLock::new();
    INFO.get_or_init(probe_device)
}

/// Returns whether a GPU plan should be attempted for the given backend
/// preference and frame pixel count.
pub fn should_use_gpu(backend: ComputeBackend, pixels: usize) -> bool {
    if !device_info().available {
        return false;
    }
    match backend {
        ComputeBackend::Cpu => false,
        ComputeBackend::Gpu => true,
        ComputeBackend::Auto => pixels >= AUTO_MIN_PIXELS,
    }
}

#[cfg(all(feature = "dioptrin", target_os = "macos"))]
fn probe_device() -> GpuDeviceInfo {
    let info = dioptrin::integration::metal_info(0);
    GpuDeviceInfo {
        available: info.available,
        backend: Some("Metal"),
        device_name: info.device_name,
        supports_f64: false,
        reason: info.reason,
    }
}

#[cfg(all(feature = "dioptrin", any(target_os = "windows", target_os = "linux")))]
fn probe_device() -> GpuDeviceInfo {
    let info = dioptrin::integration::cuda_info(0);
    GpuDeviceInfo {
        available: info.available,
        backend: Some("CUDA"),
        device_name: info.device_name,
        supports_f64: true,
        reason: info.reason,
    }
}

#[cfg(not(all(
    feature = "dioptrin",
    any(target_os = "macos", target_os = "windows", target_os = "linux")
)))]
fn probe_device() -> GpuDeviceInfo {
    GpuDeviceInfo {
        available: false,
        backend: None,
        device_name: None,
        supports_f64: false,
        reason: Some("GPU acceleration is not enabled in this build.".into()),
    }
}

#[cfg(feature = "dioptrin")]
pub mod plans {
    use super::GpuPrecision;
    use dioptrin::integration::{Fixed1dResult, InputOrder, Integrator};

    #[cfg(target_os = "macos")]
    use dioptrin::integration::{
        Metal1dOptions, Metal1dPlan, Metal2dOptions, Metal2dPlan, MetalPrecision,
    };

    #[cfg(any(target_os = "windows", target_os = "linux"))]
    use dioptrin::integration::{
        Cuda1dOptions, Cuda1dPlan, Cuda2dOptions, Cuda2dPlan, CudaPrecision,
    };

    /// Platform-neutral cached 1D GPU integration plan.
    pub struct Gpu1dPlan {
        #[cfg(target_os = "macos")]
        inner: Metal1dPlan,
        #[cfg(any(target_os = "windows", target_os = "linux"))]
        inner: Cuda1dPlan,
    }

    impl Gpu1dPlan {
        pub fn prepare(
            engine: &Integrator,
            shape: (usize, usize),
            bins: usize,
            order: InputOrder,
            precision: GpuPrecision,
        ) -> Result<Self, String> {
            #[cfg(target_os = "macos")]
            {
                let metal_precision = match precision {
                    GpuPrecision::F32 => MetalPrecision::F32,
                    GpuPrecision::F32Compensated => MetalPrecision::F32Compensated,
                    GpuPrecision::F64 => {
                        return Err(
                            "Metal GPU does not support float64; falling back to CPU.".into()
                        );
                    }
                };
                let opts = Metal1dOptions::new()
                    .with_input_order(order)
                    .with_precision(metal_precision);
                let inner = engine
                    .prepare_metal1d(shape, bins, &opts)
                    .map_err(|e| e.to_string())?;
                Ok(Self { inner })
            }
            #[cfg(any(target_os = "windows", target_os = "linux"))]
            {
                let cuda_precision = match precision {
                    GpuPrecision::F32 => CudaPrecision::F32,
                    GpuPrecision::F32Compensated => CudaPrecision::F32Compensated,
                    GpuPrecision::F64 => CudaPrecision::F64,
                };
                let opts = Cuda1dOptions::new()
                    .with_input_order(order)
                    .with_precision(cuda_precision);
                let inner = engine
                    .prepare_cuda1d(shape, bins, &opts)
                    .map_err(|e| e.to_string())?;
                Ok(Self { inner })
            }
            #[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
            {
                let _ = (engine, shape, bins, order, precision);
                Err("GPU acceleration is not supported on this platform.".into())
            }
        }

        pub fn integrate_f64(&self, data: &[f64], errors: bool) -> Result<Fixed1dResult, String> {
            #[cfg(any(target_os = "macos", target_os = "windows", target_os = "linux"))]
            {
                self.inner
                    .integrate_frame(data, errors)
                    .map_err(|e| e.to_string())
            }
            #[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
            {
                let _ = (data, errors);
                Err("GPU acceleration is not supported on this platform.".into())
            }
        }

        pub fn integrate_batch_u16(
            &self,
            frames: &[&[u16]],
            errors: bool,
        ) -> Result<Vec<Fixed1dResult>, String> {
            #[cfg(any(target_os = "macos", target_os = "windows", target_os = "linux"))]
            {
                self.inner
                    .integrate_frames(frames, errors)
                    .map_err(|e| e.to_string())
            }
            #[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
            {
                let _ = (frames, errors);
                Err("GPU acceleration is not supported on this platform.".into())
            }
        }

        pub fn integrate_batch_u32(
            &self,
            frames: &[&[u32]],
            errors: bool,
        ) -> Result<Vec<Fixed1dResult>, String> {
            #[cfg(any(target_os = "macos", target_os = "windows", target_os = "linux"))]
            {
                self.inner
                    .integrate_frames(frames, errors)
                    .map_err(|e| e.to_string())
            }
            #[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
            {
                let _ = (frames, errors);
                Err("GPU acceleration is not supported on this platform.".into())
            }
        }
    }

    /// Platform-neutral cached 2D GPU integration plan.
    pub struct Gpu2dPlan {
        #[cfg(target_os = "macos")]
        inner: Metal2dPlan,
        #[cfg(any(target_os = "windows", target_os = "linux"))]
        inner: Cuda2dPlan,
    }

    impl Gpu2dPlan {
        pub fn prepare(
            engine: &Integrator,
            shape: (usize, usize),
            n_radial: usize,
            n_azimuthal: usize,
            azimuthal_range: Option<(f64, f64)>,
            order: InputOrder,
            precision: GpuPrecision,
        ) -> Result<Self, String> {
            #[cfg(target_os = "macos")]
            {
                let metal_precision = match precision {
                    GpuPrecision::F32 => MetalPrecision::F32,
                    GpuPrecision::F32Compensated => MetalPrecision::F32Compensated,
                    GpuPrecision::F64 => {
                        return Err(
                            "Metal GPU does not support float64; falling back to CPU.".into()
                        );
                    }
                };
                let opts = Metal2dOptions::new()
                    .with_input_order(order)
                    .with_precision(metal_precision);
                let inner = engine
                    .prepare_metal2d(shape, n_radial, n_azimuthal, azimuthal_range, &opts)
                    .map_err(|e| e.to_string())?;
                Ok(Self { inner })
            }
            #[cfg(any(target_os = "windows", target_os = "linux"))]
            {
                let cuda_precision = match precision {
                    GpuPrecision::F32 => CudaPrecision::F32,
                    GpuPrecision::F32Compensated => CudaPrecision::F32Compensated,
                    GpuPrecision::F64 => CudaPrecision::F64,
                };
                let opts = Cuda2dOptions::new()
                    .with_input_order(order)
                    .with_precision(cuda_precision);
                let inner = engine
                    .prepare_cuda2d(shape, n_radial, n_azimuthal, azimuthal_range, &opts)
                    .map_err(|e| e.to_string())?;
                Ok(Self { inner })
            }
            #[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
            {
                let _ = (
                    engine,
                    shape,
                    n_radial,
                    n_azimuthal,
                    azimuthal_range,
                    order,
                    precision,
                );
                Err("GPU acceleration is not supported on this platform.".into())
            }
        }

        pub fn radial_bounds(&self) -> Option<[f64; 2]> {
            #[cfg(any(target_os = "macos", target_os = "windows", target_os = "linux"))]
            {
                let r = self.inner.radial()?;
                if r.is_empty() {
                    None
                } else {
                    Some([r[0], *r.last().unwrap()])
                }
            }
            #[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
            {
                None
            }
        }

        pub fn azimuthal_bounds_deg(&self) -> Option<[f64; 2]> {
            #[cfg(any(target_os = "macos", target_os = "windows", target_os = "linux"))]
            {
                let a = self.inner.azimuthal()?;
                if a.is_empty() {
                    None
                } else {
                    Some([a[0].to_degrees(), a.last().unwrap().to_degrees()])
                }
            }
            #[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
            {
                None
            }
        }

        pub fn integrate_f64(&self, data: &[f64]) -> Result<Vec<f64>, String> {
            #[cfg(any(target_os = "macos", target_os = "windows", target_os = "linux"))]
            {
                self.inner
                    .integrate_frame(data, false)
                    .map(|r| r.intensity)
                    .map_err(|e| e.to_string())
            }
            #[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
            {
                let _ = data;
                Err("GPU acceleration is not supported on this platform.".into())
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn compute_backend_round_trip() {
        for (raw, expected) in [
            ("auto", ComputeBackend::Auto),
            ("cpu", ComputeBackend::Cpu),
            ("gpu", ComputeBackend::Gpu),
        ] {
            assert_eq!(ComputeBackend::parse(raw).unwrap(), expected);
            assert_eq!(expected.as_str(), raw);
        }
        assert!(ComputeBackend::parse("opencl").is_err());
        for (raw, expected) in [
            ("f32", GpuPrecision::F32),
            ("f32_compensated", GpuPrecision::F32Compensated),
            ("f64", GpuPrecision::F64),
        ] {
            assert_eq!(GpuPrecision::parse(raw).unwrap(), expected);
            assert_eq!(expected.as_str(), raw);
        }
        assert!(GpuPrecision::parse("f16").is_err());
    }

    #[test]
    fn probe_reports_platform_info() {
        let info = device_info();
        #[cfg(all(feature = "dioptrin", target_os = "macos"))]
        {
            assert_eq!(info.backend, Some("Metal"));
            if info.available {
                assert!(info.device_name.as_deref().is_some_and(|n| !n.is_empty()));
            }
        }
        #[cfg(all(feature = "dioptrin", any(target_os = "windows", target_os = "linux")))]
        {
            assert_eq!(info.backend, Some("CUDA"));
        }
        #[cfg(not(feature = "dioptrin"))]
        {
            assert!(!info.available);
            assert!(info.backend.is_none());
        }
        assert!(!should_use_gpu(ComputeBackend::Cpu, 10_000_000));
        assert!(!should_use_gpu(ComputeBackend::Auto, 64 * 64));
    }

    #[cfg(feature = "dioptrin")]
    #[test]
    fn gpu_1d_and_2d_match_cpu_engine_when_available() {
        if !device_info().available {
            return;
        }
        use crate::{
            geometry::Geometry,
            integration::{Engine, Options},
        };
        let shape = [64, 80];
        let pixels = shape[0] * shape[1];
        let data: Vec<f64> = (0..pixels)
            .map(|i| ((i * 73 + 17) % 10_000) as f64 + 10.0)
            .collect();
        let mask: Vec<u8> = (0..pixels).map(|i| u8::from(i % 13 == 0)).collect();
        let params = Geometry {
            pixel1: 1e-4,
            pixel2: 1e-4,
            poni1: 32e-4,
            poni2: 40e-4,
            dist: 0.1,
            ..Geometry::default()
        };
        let cpu_opts = Options {
            bins: 60,
            automatic_bins: false,
            cake_bins: 18,
            unit: "2th_deg".into(),
            polarization: 0.99,
            errors: true,
            supersampling: 1,
            pyfai: false,
            solid_angle: true,
            azimuth: None,
            cake_azimuth: None,
            trim: false,
            spread: false,
            dynamic_mask: false,
            csc: false,
            auto_layout: false,
            compute_backend: ComputeBackend::Cpu,
            gpu_precision: GpuPrecision::F32Compensated,
        };
        let mut gpu_opts = cpu_opts.clone();
        gpu_opts.compute_backend = ComputeBackend::Gpu;

        let mut cpu_engine = Engine::default();
        let mut gpu_engine = Engine::default();
        let (cpu_pat, cpu_sigma) = cpu_engine
            .integrate_pattern_with_variance(&data, None, shape, &params, &mask, &cpu_opts, None)
            .unwrap();
        let (gpu_pat, gpu_sigma) = gpu_engine
            .integrate_pattern_with_variance(&data, None, shape, &params, &mask, &gpu_opts, None)
            .unwrap();
        assert_eq!(gpu_engine.diagnostics()["gpuIntegrations"], 1);

        let cx = cpu_pat["x"].as_array().unwrap();
        let gx = gpu_pat["x"].as_array().unwrap();
        assert_eq!(cx.len(), gx.len());
        for (a, b) in cx.iter().zip(gx) {
            assert_eq!(
                a.as_f64().unwrap().to_bits(),
                b.as_f64().unwrap().to_bits(),
                "1D radial axis must be bit-identical between CPU and GPU"
            );
        }

        let cy = cpu_pat["y"].as_array().unwrap();
        let gy = gpu_pat["y"].as_array().unwrap();
        assert_eq!(cy.len(), gy.len());
        for (a, b) in cy.iter().zip(gy) {
            let av = a.as_f64().unwrap();
            let bv = b.as_f64().unwrap();
            assert!(
                (av - bv).abs() <= 1e-5 * av.abs().max(1.0),
                "1D mismatch: cpu={av} gpu={bv}"
            );
        }
        for (a, b) in cpu_sigma.unwrap().iter().zip(gpu_sigma.unwrap()) {
            assert!(
                (a - b).abs() <= 1e-5 * a.abs().max(1.0),
                "1D sigma mismatch: cpu={a} gpu={b}"
            );
        }

        // Switching backend/precision must NOT rebuild the CPU scientific plan.
        let builds_before = gpu_engine.diagnostics()["patternPlanBuilds"]
            .as_u64()
            .unwrap();
        let mut f32_opts = gpu_opts.clone();
        f32_opts.gpu_precision = GpuPrecision::F32;
        gpu_engine
            .integrate_pattern_with_variance(&data, None, shape, &params, &mask, &f32_opts, None)
            .unwrap();
        assert_eq!(
            gpu_engine.diagnostics()["patternPlanBuilds"]
                .as_u64()
                .unwrap(),
            builds_before
        );
        assert_eq!(gpu_engine.diagnostics()["gpuIntegrations"], 2);

        // Supersampling (subpixel) runs on GPU and matches CPU.
        let mut ss_cpu = cpu_opts.clone();
        ss_cpu.supersampling = 2;
        let mut ss_gpu = gpu_opts.clone();
        ss_gpu.supersampling = 2;
        let (ss_cpu_pat, _) = cpu_engine
            .integrate_pattern_with_variance(&data, None, shape, &params, &mask, &ss_cpu, None)
            .unwrap();
        let (ss_gpu_pat, _) = gpu_engine
            .integrate_pattern_with_variance(&data, None, shape, &params, &mask, &ss_gpu, None)
            .unwrap();
        assert_eq!(gpu_engine.diagnostics()["gpuIntegrations"], 3);
        for (a, b) in ss_cpu_pat["y"]
            .as_array()
            .unwrap()
            .iter()
            .zip(ss_gpu_pat["y"].as_array().unwrap())
        {
            let av = a.as_f64().unwrap();
            let bv = b.as_f64().unwrap();
            assert!(
                (av - bv).abs() <= 1e-5 * av.abs().max(1.0),
                "1D supersampled mismatch: cpu={av} gpu={bv}"
            );
        }

        let (gpu_cake_raster, gpu_cake) = gpu_engine
            .integrate_cake(&data, shape, &params, &mask, &gpu_opts)
            .unwrap();
        assert_eq!(gpu_engine.diagnostics()["gpuIntegrations"], 4);
        let radial_range = gpu_cake_raster.metadata["radialRange"].as_array().unwrap();
        let azimuth_range = gpu_cake_raster.metadata["azimuthRange"].as_array().unwrap();
        assert!(radial_range[0].as_f64().unwrap() < radial_range[1].as_f64().unwrap());
        assert!(azimuth_range[0].as_f64().unwrap() < azimuth_range[1].as_f64().unwrap());

        let mut ai = dioptrin::integration::Integrator::new(params.native_geometry(shape).unwrap())
            .with_method(dioptrin::integration::IntegrationMethod::PixelSplit)
            .with_radial_unit(dioptrin::integration::RadialUnit::TthDeg)
            .with_polarization_factor(cpu_opts.polarization);
        ai.set_mask(dioptrin::mask::Mask {
            data: mask.clone(),
            dim1: shape[0],
            dim2: shape[1],
        });
        let ref_cake = ai
            .integrate2d_on_azimuthal_range_from_slice(
                &data,
                shape[0],
                shape[1],
                cpu_opts.bins,
                cpu_opts.cake_bins,
                (-std::f64::consts::PI, std::f64::consts::PI),
                false,
            )
            .unwrap();
        assert_eq!(ref_cake.intensity.len(), gpu_cake.len());
        for (a, b) in ref_cake.intensity.iter().zip(&gpu_cake) {
            assert!(
                (a - b).abs() <= 1e-5 * a.abs().max(1.0),
                "2D cake mismatch: ref={a} gpu={b}"
            );
        }
    }
}
