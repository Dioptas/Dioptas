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
fn home_path(path: &str) -> Result<PathBuf, String> {
    if path == "~" || path.starts_with("~/") {
        let home = std::env::var_os("HOME").ok_or("Home directory is unavailable.")?;
        Ok(PathBuf::from(home).join(path.strip_prefix("~/").unwrap_or("")))
    } else {
        Ok(PathBuf::from(path))
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
        json!({"id":id,"name":name,"program":program,"arguments":args,"enabled":enabled,"icon":icon}),
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
                let reservation = crate::custom_action_output::reserve()?;
                let mut cmd = Command::new(&program);
                cmd.args(&arguments)
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
                    cmd.creation_flags(0x08000000);
                }
                let child = crate::child_process::spawn(cmd).map_err(|e| e.to_string())?;
                let args = std::iter::once(program.to_string_lossy().into_owned())
                    .chain(arguments)
                    .collect::<Vec<_>>();
                let run = Arc::new(Mutex::new(
                    json!({"running":true,"exitCode":null,"outputPending":true,"output":"","name":command["name"],"arguments":args}),
                ));
                crate::custom_action_output::monitor(child, run.clone(), reservation)?;
                runs.insert(id.into(), run);
            }
            _ => return Err("Unknown custom-action operation.".into()),
        }
        Ok(
            json!({"ok":true,"customCommands":commands,"customCommandRuns":self.runs.lock().unwrap().iter().map(|(id, run)| (id.clone(), run.lock().unwrap().clone())).collect::<BTreeMap<_,_>>(),"customCommandContext":context}),
        )
    }
}
