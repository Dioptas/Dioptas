use std::{io, path::PathBuf};

// Stdout's text-oriented line writer inspects binary image payloads for newline
// bytes. Write to an owned duplicate of the same pipe on Unix instead.
fn binary_stdout() -> Result<impl io::Write + Send, String> {
    #[cfg(unix)]
    {
        use std::os::fd::AsFd;
        io::stdout()
            .as_fd()
            .try_clone_to_owned()
            .map(std::fs::File::from)
            .map_err(|e| e.to_string())
    }
    #[cfg(not(unix))]
    {
        Ok(io::stdout())
    }
}
fn run() -> Result<(), String> {
    let mut args = std::env::args().skip(1);
    let mut root = None;
    let mut example = false;
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--example" => example = true,
            "--resource-dir" | "--source-root" => {
                if root.is_some() {
                    return Err("Specify the resource directory once.".into());
                }
                root = Some(PathBuf::from(
                    args.next()
                        .ok_or("Resource directory argument requires a path")?,
                ))
            }
            _ => return Err(format!("Unknown processor argument {arg}")),
        }
    }
    dioptas_backend::transport::serve(
        &mut io::stdin().lock(),
        &mut io::BufWriter::with_capacity(64 * 1024, binary_stdout()?),
        root.unwrap_or_else(|| {
            let executable = std::env::current_exe().expect("processor executable path");
            let directory = executable.parent().expect("processor directory");
            let bundled = directory.join("../Resources/dioptas");
            if cfg!(target_os = "macos") && bundled.is_dir() {
                bundled
            } else {
                directory.join("dioptas")
            }
        }),
        example,
    )
}
fn main() {
    if let Err(error) = run() {
        eprintln!("Native Dioptas processor: {error}");
        std::process::exit(1);
    }
}
