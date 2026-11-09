//! Public production APIs only; resident samples are frozen outside timing.
use dioptrin::{geometry::Geometry,poni::Poni,mask::Mask,detector,
    integration::{Integrator,IntegrationMethod,RadialUnit,SparseLayout,Fixed1dPlan}};
use rayon::prelude::*;
use serde_json::{Value,json};
use std::{path::PathBuf,sync::Arc,time::{Instant,Duration},hint::black_box,io::Write};
use memmap2::{Mmap,MmapOptions};
type Output=(Vec<f64>,Option<Vec<f64>>);
struct Samples {image:Vec<f64>,copies:Vec<Vec<f64>>,frozen:Option<Mmap>,pixels:usize}
impl Samples {
    fn new(meta:&Value)->Self {
        let image:Vec<f64>=std::fs::read(meta["data"].as_str().unwrap()).unwrap().chunks_exact(8).map(|b|f64::from_le_bytes(b.try_into().unwrap())).collect();
        let pixels=image.len();
        let frozen=meta["batchData"].as_str().map(|p|{
            let file=std::fs::File::open(p).unwrap();
            // SAFETY: this is the previously frozen, SHA-256-verified read-only
            // benchmark input. This study never modifies or truncates it.
            let map=unsafe{MmapOptions::new().map(&file).unwrap()};
            assert_eq!(map.len(),pixels*meta["batchFrames"].as_u64().unwrap() as usize*8);map
        });
        let copies=if frozen.is_none(){(0..meta["batchFrames"].as_u64().unwrap()).map(|_|image.clone()).collect()}else{vec![]};
        Self{image,copies,frozen,pixels}
    }
    fn frames(&self)->Vec<&[f64]>{
        if let Some(map)=&self.frozen {
            assert!(cfg!(target_endian="little"));
            let values:&[f64]=bytemuck::try_cast_slice(map.as_ref()).unwrap();
            values.chunks_exact(self.pixels).collect()
        }else{self.copies.iter().map(Vec::as_slice).collect()}
    }
}
struct Runner {kind:&'static str,engine:Integrator,plan:Option<Fixed1dPlan>,shape:(usize,usize),bins:usize}
impl Runner {
    fn new(kind:&'static str,g:&Geometry,mask:&[u8],bins:usize,range:[f64;2])->Self {
        let mut engine=Integrator::new(g.clone()).with_method(IntegrationMethod::PixelSplit)
            .with_radial_unit(RadialUnit::TthDeg).with_radial_range(range[0],range[1])
            .with_fast_math(true).with_sparse_layout(if kind=="csr"{SparseLayout::Csr}else{SparseLayout::Csc})
            .with_polarization_factor(0.965);
        engine.set_mask(Mask{data:mask.to_vec(),dim1:g.dim1,dim2:g.dim2});
        let plan=if kind=="resident"{Some(engine.prepare_fixed1d((g.dim1,g.dim2),bins).unwrap())}else{None};
        Self{kind,engine,plan,shape:(g.dim1,g.dim2),bins}
    }
    fn one(&self,data:&[f64],errors:bool)->Output {
        if let Some(plan)=&self.plan {let r=plan.integrate_frame(data,errors).unwrap();return(r.intensity,r.errors);}
        if errors {let (_,y,e)=self.engine.integrate1d_with_errors_from_slice(data,self.shape.0,self.shape.1,self.bins);(y,Some(e))}
        else{let (_,y)=self.engine.integrate1d_from_slice(data,self.shape.0,self.shape.1,self.bins);(y,None)}
    }
    fn execute(&self,samples:&Samples,frames:&[&[f64]],batch:bool,errors:bool){
        if batch {black_box(frames.par_iter().map(|data|self.one(data,errors)).collect::<Vec<_>>());}
        else {black_box(self.one(&samples.image,errors));}
    }
}
fn metrics(a:&[f64],b:&[f64])->Value {
    let mut max:f64=0.;let(mut d,mut n)=(0.,0.);let mut bits=true;
    for (&a,&b) in a.iter().zip(b){assert!(a.is_finite()&&b.is_finite());max=max.max((a-b).abs());d+=(a-b)*(a-b);n+=a*a;bits &= a.to_bits()==b.to_bits();}
    let rel=(d/n.max(f64::MIN_POSITIVE)).sqrt();assert!(rel<2e-12,"relative L2 {rel}");
    json!({"relativeL2":rel,"maxAbsolute":max,"bitwise":bits})
}
fn main(){
    let out=PathBuf::from(std::env::args().nth(1).unwrap());
    let study:Value=serde_json::from_slice(&std::fs::read(out.join("inputs.json")).unwrap()).unwrap();
    rayon::ThreadPoolBuilder::new().num_threads(8).build_global().unwrap();
    let only=std::env::args().nth(2);
    let mut log=std::fs::OpenOptions::new().create(true).append(true).open(out.join("results.jsonl")).unwrap();
    for meta in study["images"].as_array().unwrap() {
        if only.as_ref().is_some_and(|id|meta["id"].as_str()!=Some(id)){continue;}
        let data=Samples::new(meta);let frames=data.frames();
        let mask=std::fs::read(meta["mask"].as_str().unwrap()).unwrap();assert_eq!(mask.len(),data.pixels);
        let mut p=Poni::new();
        p.pixel1=meta["pixel1"].as_f64().unwrap();p.pixel2=meta["pixel2"].as_f64().unwrap();p.distance=meta["distance"].as_f64().unwrap();
        p.poni1=meta["poni1"].as_f64().unwrap();p.poni2=meta["poni2"].as_f64().unwrap();p.rot1=meta["rot1"].as_f64().unwrap();p.rot2=meta["rot2"].as_f64().unwrap();p.rot3=meta["rot3"].as_f64().unwrap();p.wavelength=meta["wavelength"].as_f64().unwrap();
        let mut g=Geometry::new(meta["shape"][0].as_u64().unwrap() as usize,meta["shape"][1].as_u64().unwrap() as usize,p);
        if let Some(name)=meta["detector"].as_str(){let mut d=detector::named(name).unwrap();d.orientation=meta["orientation"].as_u64().unwrap() as u8;d.pixel1=meta["basePixel1"].as_f64().unwrap_or(g.poni.pixel1);d.pixel2=meta["basePixel2"].as_f64().unwrap_or(g.poni.pixel2);g=g.with_detector(Arc::new(d)).unwrap();}
        let (corners,_)=g.angular_corners();let range=[corners.iter().copied().fold(f64::INFINITY,f64::min).to_degrees(),corners.iter().copied().fold(f64::NEG_INFINITY,f64::max).to_degrees()+10.*f64::EPSILON];drop(corners);
        let selected_bins:Value=std::env::var("BENCH_BINS").ok().map(|s|serde_json::from_str(&s).unwrap()).unwrap_or_else(||study["bins"].clone());
        for (case,bins) in selected_bins.as_array().unwrap().iter().enumerate(){
            let bins=bins.as_u64().unwrap() as usize;
            let mut runners=Vec::new();let mut cold=Vec::new();
            for kind in ["csr","csc","resident"]{
                let start=Instant::now();let r=Runner::new(kind,&g,&mask,bins,range);black_box(r.one(&data.image,false));cold.push(start.elapsed().as_secs_f64()*1000.);runners.push(r);
            }
            let reference=runners[1].one(&data.image,true);
            let checks:Vec<_>=runners.iter().map(|r|{let got=r.one(&data.image,true);json!({"layout":r.kind,"intensity":metrics(&reference.0,&got.0),"sigma":metrics(reference.1.as_ref().unwrap(),got.1.as_ref().unwrap())})}).collect();
            for batch in [false,true]{for errors in [false,true]{
                let mut times:[Vec<f64>;3]=Default::default();let mut calls=[0;3];
                for r in &runners{r.execute(&data,&frames,batch,errors);}
                for rep in 0..5 {for k in 0..3 {let idx=if rep%2==0 {(k+case)%3}else{(2-k+case)%3};
                    let start=Instant::now();let mut count=0;
                    while count<5 || start.elapsed()<Duration::from_millis(80){runners[idx].execute(&data,&frames,batch,errors);count+=1;}
                    let per_frame=start.elapsed().as_secs_f64()*1000./count as f64/if batch {frames.len() as f64}else{1.};
                    times[idx].push(per_frame);calls[idx]+=count;
                }}
                let records:Vec<_>=(0..3).map(|i|json!({"layout":runners[i].kind,"samplesMsPerFrame":times[i],"calls":calls[i],"coldMs":cold[i]})).collect();
                let record=json!({"run":std::env::var("BENCH_RUN").unwrap_or_else(|_|"initial".into()),"revision":"bcdbee36f43a38359d02d547e07020b175e1a122","image":meta["id"],"pixels":data.pixels,"bins":bins,"batch":batch,"errors":errors,"frames":if batch {frames.len()}else{1},"threads":8,"records":records,"numerics":checks,"radialEdges":range});
                writeln!(log,"{}",record).unwrap();log.flush().unwrap();
                println!("{} bins={} batch={} errors={} complete",meta["id"],bins,batch,errors);
            }}
        }
    }
}
