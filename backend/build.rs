use std::{env, fs, path::Path};
/// "PhaseSmith <version> / <short commit>" of the linked
/// phasesmith-single-crystal, read from the workspace Cargo.lock.
fn phasesmith_engine(root: &str) -> String {
    let lock = Path::new(root).join("../Cargo.lock");
    println!("cargo:rerun-if-changed={}", lock.display());
    let text = fs::read_to_string(lock).unwrap_or_default();
    let mut lines = text.lines();
    while let Some(line) = lines.next() {
        if line.trim() == "name = \"phasesmith-single-crystal\"" {
            let field = |line: Option<&str>, key: &str| {
                line.and_then(|l| l.trim().strip_prefix(key))
                    .map(|v| v.trim_matches('"').to_owned())
            };
            let version = field(lines.next(), "version = ").unwrap_or_default();
            let commit = field(lines.next(), "source = ")
                .and_then(|s| s.rsplit_once('#').map(|(_, c)| c.chars().take(8).collect()))
                .unwrap_or_else(|| "local".to_owned());
            return format!("PhaseSmith {version} / {commit}");
        }
    }
    "PhaseSmith (unknown)".to_owned()
}
fn main() {
    let root = env::var("CARGO_MANIFEST_DIR").unwrap();
    println!(
        "cargo:rustc-env=PHASESMITH_ENGINE={}",
        phasesmith_engine(&root)
    );
    let directory = Path::new(&root).join("../resources/calibrants");
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
