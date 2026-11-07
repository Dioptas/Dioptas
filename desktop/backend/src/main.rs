use std::{
    io,
    path::{Path, PathBuf},
};

fn run() -> Result<(), String> {
    let mut args = std::env::args().skip(1);
    let mut root = Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .parent()
        .unwrap()
        .to_path_buf();
    let mut example = false;
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--example" => example = true,
            "--source-root" => {
                root = PathBuf::from(args.next().ok_or("--source-root requires a directory")?)
            }
            _ => return Err(format!("Unknown processor argument {arg}")),
        }
    }
    dioptas_backend::transport::serve(
        &mut io::stdin().lock(),
        &mut io::BufWriter::new(io::stdout()),
        root,
        example,
    )
}
fn main() {
    if let Err(error) = run() {
        eprintln!("Native Dioptas processor: {error}");
        std::process::exit(1);
    }
}
