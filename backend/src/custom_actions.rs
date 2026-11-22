//! Explicit user-configured external actions, independent of numerical processing.
use serde_json::{Value, json};
use std::{
    collections::BTreeMap,
    path::PathBuf,
    process::{Command, Stdio},
    sync::{Arc, Mutex},
};
const FIELDS: [&str; 9] = [
    "image_path",
    "image_name",
    "image_directory",
    "frame_index",
    "frame_number",
    "dataset",
    "calibration_path",
    "project_path",
    "wavelength_angstrom",
];
#[derive(Default)]
pub(crate) struct Actions {
    runs: Arc<Mutex<BTreeMap<String, crate::custom_action_output::Run>>>,
}
/// Expands a leading `~` to the user's home directory. `std::env::home_dir`
/// reads `HOME` on Unix and `USERPROFILE` on Windows, where `HOME` is
/// normally not set.
fn home_path(path: &str) -> Result<PathBuf, String> {
    let rest = if path == "~" {
        Some("")
    } else {
        path.strip_prefix("~/")
            .or_else(|| cfg!(windows).then(|| path.strip_prefix("~\\")).flatten())
    };
    match rest {
        Some(rest) => {
            let home = std::env::home_dir()
                .filter(|h| !h.as_os_str().is_empty())
                .ok_or("Home directory is unavailable.")?;
            Ok(home.join(rest))
        }
        None => Ok(PathBuf::from(path)),
    }
}
fn settings_path() -> Result<PathBuf, String> {
    std::env::var("DIOPTAS_CUSTOM_COMMANDS_FILE").map_or_else(
        |_| home_path("~/.Dioptas/desktop-custom-commands.json"),
        |p| home_path(&p),
    )
}
fn expand(text: &str, context: Option<&Value>) -> Result<String, String> {
    let mut out = String::new();
    let mut remaining = text;
    while let Some(start) = remaining.find('{') {
        out.push_str(&remaining[..start]);
        let rest = &remaining[start + 1..];
        let Some(end) = rest.find('}') else {
            out.push_str(&remaining[start..]);
            return Ok(out);
        };
        let token = &rest[..end];
        if !token.is_empty()
            && token
                .bytes()
                .enumerate()
                .all(|(i, b)| b == b'_' || b.is_ascii_lowercase() || (i > 0 && b.is_ascii_digit()))
        {
            if !FIELDS.contains(&token) {
                return Err(format!("Unknown action input: {{{token}}}."));
            }
            if let Some(context) = context {
                let v = &context[token];
                if v.is_null() || v == "" {
                    return Err(format!(
                        "{} is unavailable for the current image or session.",
                        token.replace('_', " ")
                    ));
                }
                out.push_str(
                    &v.as_str()
                        .map(str::to_string)
                        .unwrap_or_else(|| v.to_string()),
                );
            } else {
                out.push('{');
                out.push_str(token);
                out.push('}');
            }
        } else {
            out.push('{');
            out.push_str(token);
            out.push('}');
        }
        remaining = &rest[end + 1..];
    }
    out.push_str(remaining);
    Ok(out)
}
fn validate(value: &Value) -> Result<Value, String> {
    let name = value["name"].as_str().unwrap_or("").trim();
    let program = value["program"].as_str().unwrap_or("").trim();
    if name.is_empty() || name.chars().count() > 80 {
        return Err("Give the button a name, up to 80 characters.".into());
    }
    if program.is_empty() || program.contains('\0') {
        return Err("Enter a program or executable script path.".into());
    }
    let args = value["arguments"]
        .as_array()
        .filter(|a| a.len() <= 100)
        .ok_or("Provide up to 100 text arguments.")?;
    for arg in args {
        let arg = arg
            .as_str()
            .filter(|s| !s.contains('\0') && s.len() <= 65536)
            .ok_or("Provide bounded text arguments without NUL bytes.")?;
        expand(arg, None)?;
    }
    let enabled = value.get("enabled").map_or(Ok(true), |v| {
        v.as_bool().ok_or("Enabled must be a boolean.")
    })?;
    let detached = value.get("detached").map_or(Ok(false), |v| {
        v.as_bool().ok_or("Detached must be a boolean.")
    })?;
    let icon = value
        .get("icon")
        .and_then(Value::as_str)
        .unwrap_or("terminal");
    let icons: Vec<String> = serde_json::from_str(include_str!("../resources/action-icons.json"))
        .expect("checked icons");
    if !icons.iter().any(|i| i == icon) {
        return Err("Choose an available action icon.".into());
    }
    let id = value["id"].as_str().map(str::to_string).unwrap_or_else(|| {
        format!(
            "rust-{:x}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        )
    });
    if id.is_empty() || id.len() > 100 {
        return Err("Invalid command ID.".into());
    }
    Ok(
        json!({"id":id,"name":name,"program":program,"arguments":args,"enabled":enabled,"icon":icon,"detached":detached}),
    )
}
fn read_commands() -> Result<Vec<Value>, String> {
    let path = settings_path()?;
    if !path.exists() {
        return Ok(vec![]);
    }
    if std::fs::metadata(&path).map_err(|e| e.to_string())?.len() > 4 * 1024 * 1024 {
        return Err("Custom-action settings exceed four MiB.".into());
    }
    let data: Value = serde_json::from_slice(&std::fs::read(path).map_err(|e| e.to_string())?)
        .map_err(|e| e.to_string())?;
    if data["version"] != 1 {
        return Err("Unsupported custom-action settings.".into());
    }
    let commands = data["commands"]
        .as_array()
        .filter(|a| a.len() <= 1000)
        .ok_or("Invalid custom-action settings.")?
        .iter()
        .map(validate)
        .collect::<Result<Vec<_>, _>>()?;
    let mut ids = std::collections::BTreeSet::new();
    if commands
        .iter()
        .any(|c| !ids.insert(c["id"].as_str().unwrap()))
    {
        return Err("Duplicate custom-action IDs.".into());
    }
    Ok(commands)
}
impl Actions {
    pub fn invoke(&self, args: &Value, context: Value) -> Result<Value, String> {
        let mut commands = read_commands()?;
        let operation = args["operation"].as_str().unwrap_or("list");
        match operation {
            "list" => {}
            "save" | "delete" => {
                if operation == "save" {
                    let c = validate(&args["command"])?;
                    if let Some(i) = commands.iter().position(|x| x["id"] == c["id"]) {
                        commands[i] = c;
                    } else {
                        commands.push(c);
                    }
                } else {
                    let id = args["identifier"]
                        .as_str()
                        .ok_or("Choose a custom action.")?;
                    if self
                        .runs
                        .lock()
                        .unwrap()
                        .get(id)
                        .is_some_and(|r| r.lock().unwrap()["running"] == true)
                    {
                        return Err("Wait for this action to finish before deleting it.".into());
                    }
                    commands.retain(|c| c["id"] != id);
                }
                let path = settings_path()?;
                std::fs::create_dir_all(path.parent().ok_or("Invalid settings path.")?)
                    .map_err(|e| e.to_string())?;
                crate::session::atomic_write(
                    &path,
                    &serde_json::to_vec_pretty(&json!({"version":1,"commands":commands}))
                        .map_err(|e| e.to_string())?,
                )?;
            }
            "run" => {
                let id = args["identifier"]
                    .as_str()
                    .ok_or("Choose an enabled custom action.")?;
                let command = commands
                    .iter()
                    .find(|c| c["id"] == id && c["enabled"] == true)
                    .ok_or("Choose an enabled custom action.")?;
                let mut runs = self.runs.lock().unwrap();
                if runs
                    .get(id)
                    .is_some_and(|r| r.lock().unwrap()["running"] == true)
                {
                    return Err("This action is already running.".into());
                }
                let program = home_path(command["program"].as_str().unwrap())?;
                let arguments = command["arguments"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .map(|a| expand(a.as_str().unwrap(), Some(&context)))
                    .collect::<Result<Vec<_>, _>>()?;
                let shown = std::iter::once(program.to_string_lossy().into_owned())
                    .chain(arguments.iter().cloned())
                    .collect::<Vec<_>>();
                if command["detached"] == true {
                    launch_detached(&program, &arguments)?;
                    let run = json!({"running":false,"detached":true,"exitCode":null,"outputPending":false,"output":"","name":command["name"],"arguments":shown});
                    runs.insert(id.into(), Arc::new(Mutex::new(run)));
                } else {
                    let run = Arc::new(Mutex::new(
                        json!({"running":true,"exitCode":null,"outputPending":true,"output":"","name":command["name"],"arguments":shown}),
                    ));
                    // Admission precedes the launch, so a refused run starts nothing.
                    let reservation = crate::custom_action_output::reserve()?;
                    let child = spawn_captured(&program, &arguments)?;
                    crate::custom_action_output::monitor(child, run.clone(), reservation)?;
                    runs.insert(id.into(), run);
                }
            }
            _ => return Err("Unknown custom-action operation.".into()),
        }
        Ok(
            json!({"ok":true,"customCommands":commands,"customCommandRuns":self.runs.lock().unwrap().iter().map(|(id, run)| (id.clone(), run.lock().unwrap().clone())).collect::<BTreeMap<_,_>>()}),
        )
    }
}

/// Start a program with captured output and no console window.
fn spawn_captured(
    program: &std::path::Path,
    arguments: &[String],
) -> Result<std::process::Child, String> {
    let mut cmd = Command::new(program);
    cmd.args(arguments)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    #[cfg(unix)]
    {
        use std::os::unix::process::CommandExt;
        cmd.process_group(0);
    }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        // CREATE_NO_WINDOW: captured runs never flash a console.
        cmd.creation_flags(0x08000000);
    }
    crate::child_process::spawn(cmd).map_err(|e| e.to_string())
}

/// Start a program without capturing its output or tracking its exit, so it can
/// outlive the action and keep its own window. Console programs get their own
/// console on Windows; on Unix the child runs in its own process group with
/// null stdio, and a short-lived thread reaps it.
#[cfg(unix)]
fn launch_detached(program: &std::path::Path, arguments: &[String]) -> Result<(), String> {
    use std::os::unix::process::CommandExt;
    let mut cmd = Command::new(program);
    cmd.args(arguments)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .process_group(0);
    let mut child = crate::child_process::spawn(cmd).map_err(|e| e.to_string())?;
    std::thread::spawn(move || {
        let _ = child.wait();
    });
    Ok(())
}

/// Rust's `Command` always passes standard handles to the child: the worker's
/// protocol pipes or NUL, so a console program such as cmd.exe would exit at
/// once instead of opening a window. Call CreateProcessW directly, without
/// handle inheritance or STARTF_USESTDHANDLES, so a new console owns its stdio.
#[cfg(windows)]
fn launch_detached(program: &std::path::Path, arguments: &[String]) -> Result<(), String> {
    use windows_sys::Win32::Foundation::CloseHandle;
    use windows_sys::Win32::System::Threading::{
        CREATE_NEW_CONSOLE, CREATE_NEW_PROCESS_GROUP, CreateProcessW, PROCESS_INFORMATION,
        STARTUPINFOW,
    };
    let script = program
        .to_str()
        .ok_or("The program path is not valid Unicode.")?;
    // Batch scripts run through cmd.exe, which parses the whole command line
    // again: MSVC quoting would let `&`, `^` or `%` in an image path split the
    // command or expand variables. Start cmd.exe explicitly with batch quoting,
    // as Rust's `Command` does for captured runs.
    let (application, line) = if is_batch_script(program) {
        let root = std::env::var_os("SystemRoot").unwrap_or_else(|| r"C:\Windows".into());
        let cmd = std::path::Path::new(&root).join(r"System32\cmd.exe");
        let cmd = cmd
            .to_str()
            .ok_or("The cmd.exe path is not valid Unicode.")?;
        let line = windows_batch_command_line(cmd, script, arguments)?;
        let application: Vec<u16> = cmd.encode_utf16().chain(std::iter::once(0)).collect();
        (Some(application), line)
    } else {
        (None, windows_command_line(script, arguments)?)
    };
    let mut line: Vec<u16> = line.encode_utf16().chain(std::iter::once(0)).collect();
    // SAFETY: zeroed STARTUPINFOW/PROCESS_INFORMATION are valid initial states;
    // `line` is a mutable, NUL-terminated buffer and `application`, when set, a
    // NUL-terminated path; both outlive the call.
    unsafe {
        let mut startup: STARTUPINFOW = std::mem::zeroed();
        startup.cb = std::mem::size_of::<STARTUPINFOW>() as u32;
        let mut info: PROCESS_INFORMATION = std::mem::zeroed();
        if CreateProcessW(
            application
                .as_ref()
                .map_or(std::ptr::null(), |a| a.as_ptr()),
            line.as_mut_ptr(),
            std::ptr::null(),
            std::ptr::null(),
            0,
            CREATE_NEW_CONSOLE | CREATE_NEW_PROCESS_GROUP,
            std::ptr::null(),
            std::ptr::null(),
            &startup,
            &mut info,
        ) == 0
        {
            return Err(std::io::Error::last_os_error().to_string());
        }
        CloseHandle(info.hThread);
        CloseHandle(info.hProcess);
    }
    Ok(())
}

/// Quote a command line with the MSVC C runtime rules that Rust's `Command`
/// uses; the program name is always quoted and cannot contain quotes.
#[cfg(any(windows, test))]
fn windows_command_line(program: &str, arguments: &[String]) -> Result<String, String> {
    if program.contains('"') {
        return Err("The program path cannot contain quotation marks.".into());
    }
    let mut line = format!("\"{program}\"");
    for argument in arguments {
        line.push(' ');
        if !argument.is_empty() && !argument.contains([' ', '\t', '\n', '\u{0b}', '"']) {
            line.push_str(argument);
            continue;
        }
        line.push('"');
        let mut backslashes = 0;
        for c in argument.chars() {
            match c {
                '\\' => backslashes += 1,
                '"' => {
                    line.extend(std::iter::repeat_n('\\', backslashes * 2 + 1));
                    line.push('"');
                    backslashes = 0;
                }
                _ => {
                    line.extend(std::iter::repeat_n('\\', backslashes));
                    line.push(c);
                    backslashes = 0;
                }
            }
        }
        line.extend(std::iter::repeat_n('\\', backslashes * 2));
        line.push('"');
    }
    Ok(line)
}

#[cfg(any(windows, test))]
fn is_batch_script(program: &std::path::Path) -> bool {
    program
        .extension()
        .and_then(|e| e.to_str())
        .is_some_and(|e| e.eq_ignore_ascii_case("bat") || e.eq_ignore_ascii_case("cmd"))
}

/// Build `cmd.exe /c` for a batch script with the rules Rust's `Command` uses:
/// the command after /c gets an extra pair of quotes, arguments containing cmd
/// metacharacters are quoted, and `%` is broken up with the empty `%cd:~,%`
/// substring so that `%NAME%` is never expanded. Quotes and line breaks have no
/// reliable batch escaping and are refused.
#[cfg(any(windows, test))]
fn windows_batch_command_line(
    cmd: &str,
    script: &str,
    arguments: &[String],
) -> Result<String, String> {
    if script.contains('"') || script.ends_with('\\') {
        return Err("The batch script path cannot contain quotation marks.".into());
    }
    let mut line = format!("\"{cmd}\" /e:ON /v:OFF /d /c \"\"{script}\"");
    for argument in arguments {
        if argument.contains(['"', '\r', '\n']) {
            return Err(
                "Batch script arguments cannot contain quotation marks or line breaks.".into(),
            );
        }
        line.push(' ');
        let quote = argument.is_empty()
            || argument.contains([
                ' ', '\t', '&', '(', ')', '[', ']', '{', '}', '^', '=', ';', '!', '\'', '+', ',',
                '`', '~', '|', '<', '>',
            ]);
        if quote {
            line.push('"');
        }
        for c in argument.chars() {
            if c == '%' {
                line.push_str("%%cd:~,");
            }
            line.push(c);
        }
        if quote {
            line.push('"');
        }
    }
    line.push('"');
    Ok(line)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn windows_command_lines_follow_msvc_quoting() {
        let args = |a: &[&str]| a.iter().map(|s| s.to_string()).collect::<Vec<_>>();
        assert_eq!(
            windows_command_line(r"C:\Windows\system32\cmd.exe", &[]).unwrap(),
            r#""C:\Windows\system32\cmd.exe""#
        );
        assert_eq!(
            windows_command_line(
                "py",
                &args(&[
                    r"G:\data dir\a.tif",
                    "0",
                    "",
                    r#"say "hi""#,
                    r"trail\",
                    r"x\ y\"
                ])
            )
            .unwrap(),
            r#""py" "G:\data dir\a.tif" 0 "" "say \"hi\"" trail\ "x\ y\\""#
        );
        assert!(windows_command_line("a\"b", &[]).is_err());
    }
    #[cfg(unix)]
    #[test]
    fn detached_launch_runs_the_program_without_capturing_it() {
        let directory = tempfile::tempdir().unwrap();
        let marker = directory.path().join("started");
        launch_detached(
            std::path::Path::new("/bin/sh"),
            &[
                "-c".into(),
                "printf started > \"$1\"".into(),
                "sh".into(),
                marker.to_string_lossy().into_owned(),
            ],
        )
        .unwrap();
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(10);
        while std::fs::read_to_string(&marker).ok().as_deref() != Some("started") {
            assert!(
                std::time::Instant::now() < deadline,
                "detached program did not run"
            );
            std::thread::sleep(std::time::Duration::from_millis(20));
        }
        assert!(launch_detached(std::path::Path::new("/nonexistent/dioptas-action"), &[]).is_err());
    }
    #[cfg(windows)]
    #[test]
    fn detached_console_program_runs_with_its_own_console() {
        let directory = tempfile::tempdir().unwrap();
        let marker = directory.path().join("started.txt");
        let cmd = std::path::PathBuf::from(std::env::var_os("ComSpec").unwrap());
        // cmd.exe exits at once without its own console; with one, it runs /C.
        launch_detached(
            &cmd,
            &[
                "/D".into(),
                "/C".into(),
                // One quoted argument; cmd.exe strips its outer quotes for /C.
                format!("echo started> {}", marker.display()),
            ],
        )
        .unwrap();
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(20);
        while !std::fs::read_to_string(&marker).is_ok_and(|s| s.trim() == "started") {
            assert!(
                std::time::Instant::now() < deadline,
                "detached cmd.exe did not run"
            );
            std::thread::sleep(std::time::Duration::from_millis(50));
        }
        assert!(launch_detached(std::path::Path::new(r"C:\nonexistent\dioptas.exe"), &[]).is_err());
    }
    #[test]
    fn batch_command_lines_quote_metacharacters_and_break_up_percent() {
        let args = |a: &[&str]| a.iter().map(|s| s.to_string()).collect::<Vec<_>>();
        assert!(is_batch_script(std::path::Path::new(r"G:\a b\run.BAT")));
        assert!(is_batch_script(std::path::Path::new("run.cmd")));
        assert!(!is_batch_script(std::path::Path::new("run.exe")));
        assert_eq!(
            windows_batch_command_line(
                r"C:\Windows\System32\cmd.exe",
                r"G:\my tools\run.bat",
                &args(&[r"G:\a&b.tif", "0", "", r"50%PATH%", r"c^d"])
            )
            .unwrap(),
            r#""C:\Windows\System32\cmd.exe" /e:ON /v:OFF /d /c ""G:\my tools\run.bat" "G:\a&b.tif" 0 "" 50%%cd:~,%PATH%%cd:~,% "c^d"""#
        );
        assert!(windows_batch_command_line("cmd.exe", "run.bat", &args(&[r#"say "hi""#])).is_err());
        assert!(windows_batch_command_line("cmd.exe", "run.bat", &args(&["a\nb"])).is_err());
        assert!(windows_batch_command_line("cmd.exe", "r\"un.bat", &[]).is_err());
    }
    #[cfg(windows)]
    #[test]
    fn detached_batch_scripts_receive_metacharacters_literally() {
        let directory = tempfile::tempdir().unwrap();
        let folder = directory.path().join("tools & scripts");
        std::fs::create_dir(&folder).unwrap();
        let script = folder.join("record args.bat");
        // Delayed expansion prints each argument without cmd parsing it again.
        std::fs::write(
            &script,
            "@echo off\r\nset \"A=%~2\"\r\nset \"B=%~3\"\r\nset \"C=%~4\"\r\nset \"D=%~5\"\r\nset \"E=%~6\"\r\nsetlocal EnableDelayedExpansion\r\n> \"%~1.tmp\" (echo(!A!& echo(!B!& echo(!C!& echo(!D!& echo(!E!)\r\nmove /y \"%~1.tmp\" \"%~1\" > nul\r\n",
        )
        .unwrap();
        let marker = directory.path().join("received.txt");
        let sent = [
            r"G:\data\Fe&Ni (1).tif",
            r"G:\data\c^d.tif",
            r"G:\data\50%PATH%.tif",
            r"G:\data dir\trail\",
            "0",
        ];
        let mut arguments = vec![marker.to_string_lossy().into_owned()];
        arguments.extend(sent.iter().map(|s| s.to_string()));
        launch_detached(&script, &arguments).unwrap();
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(20);
        let received = loop {
            if let Ok(text) = std::fs::read_to_string(&marker) {
                break text;
            }
            assert!(
                std::time::Instant::now() < deadline,
                "detached batch script did not run"
            );
            std::thread::sleep(std::time::Duration::from_millis(50));
        };
        assert_eq!(received.lines().collect::<Vec<_>>(), sent);
    }
    #[test]
    fn detached_flag_defaults_off_and_rejects_non_booleans() {
        let base = json!({"id":"a","name":"A","program":"p","arguments":[]});
        assert_eq!(validate(&base).unwrap()["detached"], false);
        let mut on = base.clone();
        on["detached"] = json!(true);
        assert_eq!(validate(&on).unwrap()["detached"], true);
        on["detached"] = json!("yes");
        assert!(validate(&on).is_err());
    }
}
