//! Matched timing of the desktop's numerical execution paths, without I/O/UI.
use dioptrin::{geometry::Geometry, poni::Poni, mask::Mask,
    integration::{Integrator, IntegrationMethod, IntegrationGrid2d, RadialUnit, Fixed1dPlan, FixedCsr1dPlan, FixedGrid2dPlan},
    lut::{Lut1d, build_lut1d_pyfai_csr, integrate1d}};
use serde_json::{Value, json};
use std::{path::Path, time::Instant, hint::black_box};
const N: usize = 1000;
const A: usize = 360;
struct Case {
    engine: Integrator,
    fixed: Option<Fixed1dPlan>,
    lut: Option<Lut1d>,
    fixed_csr: Option<FixedCsr1dPlan>,
    fixed2d: Option<FixedGrid2dPlan>,
    norm: Vec<f64>,
    grid: IntegrationGrid2d,
    pyfai: bool,
    cake: bool,
    shape: (usize, usize),
}
impl Case {
    fn new(g: &Geometry, mask: &[u8], range: [f64;2], pyfai: bool, cake: bool) -> Self {
        let mut engine = Integrator::new(g.clone())
            .with_method(if pyfai { IntegrationMethod::PyfaiFull } else { IntegrationMethod::PixelSplit })
            .with_radial_unit(RadialUnit::TthDeg).with_radial_range(range[0], range[1])
            .with_polarization_factor(0.99).with_fast_math(true);
        engine.set_mask(Mask {data:mask.to_vec(),dim1:g.dim1,dim2:g.dim2});
        let mut fixed=None; let mut lut=None; let mut norm=Vec::new();
        if !cake {
            if pyfai {
                // Desktop PyfaiFull 1D uses the general CSR path.
                let tth=g.calc_tth_all();let azi=g.calc_azimuth_all();
                norm=g.calc_solid_angle();
                for (v,p) in norm.iter_mut().zip(g.calc_polarization(0.99,&tth,&azi)) {*v *= p;}
                lut=Some(build_lut1d_pyfai_csr(g,RadialUnit::TthDeg,N,None,Some(range)).unwrap());
            } else {
                // Desktop default polygon 1D uses its fixed-mask CSC plan.
                fixed=Some(engine.prepare_fixed1d((g.dim1,g.dim2),N).unwrap().with_auto_layout());
            }
        }
        let grid=IntegrationGrid2d::new(N,A,(range[0],range[1]),(-std::f64::consts::PI,std::f64::consts::PI)).unwrap();
        let fixed_csr=if pyfai&&!cake {Some(FixedCsr1dPlan::new(lut.take().unwrap(),std::mem::take(&mut norm),Some(mask.to_vec())).unwrap())}else{None};
        let fixed2d=if pyfai&&cake {Some(engine.prepare_fixed2d_on_grid((g.dim1,g.dim2),&grid).unwrap())}else{None};
        Self {engine,fixed,lut,norm,grid,fixed_csr,fixed2d,pyfai,cake,shape:(g.dim1,g.dim2)}
    }
    fn run(&self, data: &[f64], mask: &[u8]) -> Vec<f64> {
        if !self.cake {
            if let Some(plan)=&self.fixed_csr {return plan.integrate_frame(data,false).unwrap().intensity;}
            if let Some(plan)=&self.fixed {return plan.integrate_frame(data,false).unwrap().intensity;}
            return integrate1d(data,self.lut.as_ref().unwrap(),Some(mask),&self.norm).1;
        }
        if self.pyfai {
            if let Some(plan)=&self.fixed2d {return plan.integrate_frame(data,false).unwrap().0;}
            let raw=self.engine.integrate2d_raw_on_grid_from_slice(data,self.shape.0,self.shape.1,&self.grid,false).unwrap();
            raw.sum_signal.iter().zip(raw.sum_norm).map(|(s,n)|if n==0. {0.} else {s/n}).collect()
        } else {
            self.engine.integrate2d_with_azimuthal_range_from_slice(data,self.shape.0,self.shape.1,N,A,
                -std::f64::consts::PI+std::f64::consts::PI/A as f64,std::f64::consts::TAU/A as f64)
        }
    }
}
fn save(path: &Path, v: &[f64]) {std::fs::write(path,v.iter().flat_map(|x|x.to_le_bytes()).collect::<Vec<_>>()).unwrap();}
fn main() {
    let out=std::path::PathBuf::from(std::env::args().nth(1).unwrap());
    let input:Value=serde_json::from_slice(&std::fs::read(out.join("input.json")).unwrap()).unwrap();
    let shape=(input["shape"][0].as_u64().unwrap() as usize,input["shape"][1].as_u64().unwrap() as usize);
    let data:Vec<f64>=std::fs::read(out.join("image.f64")).unwrap().chunks_exact(8).map(|x|f64::from_le_bytes(x.try_into().unwrap())).collect();
    let mask=std::fs::read(out.join("mask.u8")).unwrap();
    let g=Geometry::new(shape.0,shape.1,Poni::load(input["poni"].as_str().unwrap()).unwrap());
    let (r,c)=g.corner_grid();let (tth,_)=g.calc_tth_and_azimuth(&r,&c);
    let range=[tth.iter().copied().fold(f64::INFINITY,f64::min).to_degrees(),tth.iter().copied().fold(f64::NEG_INFINITY,f64::max).to_degrees()+10.*f64::EPSILON];
    let names=["polygon_1d","pyfai_1d","polygon_cake","pyfai_cake"];
    let mut cold:[Vec<f64>;4]=Default::default();let mut warm:[Vec<f64>;4]=Default::default();
    let mut cases:Vec<Option<Case>>=(0..4).map(|_|None).collect();
    for round in 0..5 {
        for k in 0..4 {let i=if round%2==0 {k} else {3-k};let start=Instant::now();
            let case=Case::new(&g,&mask,range,i%2==1,i>=2);let result=black_box(case.run(&data,&mask));
            cold[i].push(start.elapsed().as_secs_f64()*1000.);
            if round==4 {save(&out.join(format!("{}.f64",names[i])),&result);cases[i]=Some(case);}
        }
        eprintln!("cold round {} complete",round+1);
    }
    for round in 0..21 {for k in 0..4 {let i=if round%2==0 {k} else {3-k};let case=cases[i].as_ref().unwrap();
        let start=Instant::now();let result=black_box(case.run(&data,&mask));warm[i].push(start.elapsed().as_secs_f64()*1000.);black_box(result);
    }}
    let timing:Vec<_>=(0..4).map(|i|json!({"case":names[i],"coldMs":cold[i],"warmMs":warm[i]})).collect();
    let output=json!({"input":input,"radialEdges":range,"azimuthEdgesDeg":[-180.,180.],"timing":timing,
        "library":"Dioptrin bcdbee3 resident polygon execution","profile":"cargo release, opt-level=3, default LTO off",
        "scope":"resident float64 samples; first call includes integrator/mask, geometry arrays, corrections, LUT/plan and integration; warm calls reuse plans; excludes file I/O, transport, JSON, raster display and plotting",
        "paths":{"polygon_1d":"fixed CSC plan","pyfai_1d":"fixed strict CSR plan","polygon_cake":"ordinary polygon CSR with desktop azimuth centers","pyfai_cake":"fixed shared-grid intensity plan"}});
    std::fs::write(out.join("timing.json"),serde_json::to_vec_pretty(&output).unwrap()).unwrap();
    println!("{}",output);
}
