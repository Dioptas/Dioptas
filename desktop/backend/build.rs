use std::{env, fs, path::Path};
fn main() {
    let root = env::var("CARGO_MANIFEST_DIR").unwrap();
    let directory = Path::new(&root).join("../../dioptas/resources/calibrants");
    println!("cargo:rerun-if-changed={}", directory.display());
    let mut files: Vec<_> = fs::read_dir(directory)
        .unwrap()
        .map(|f| f.unwrap().path())
        .filter(|p| p.extension().is_some_and(|s| s == "D"))
        .collect();
    files.sort();
    let mut source = String::from("pub const CALIBRANTS: &[(&str, &str)] = &[\n");
    for path in files {
        let name = path.file_stem().unwrap().to_str().unwrap();
        let path = path.canonicalize().unwrap();
        source.push_str(&format!(
            "({name:?}, include_str!({:?})),\n",
            path.to_str().unwrap()
        ));
    }
    source.push_str("];\n");
    fs::write(
        Path::new(&env::var("OUT_DIR").unwrap()).join("calibrants.rs"),
        source,
    )
    .unwrap();
}
