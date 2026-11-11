const MANUAL: &str = "https://peritheos.readthedocs.io/en/latest/";

fn valid_manual_url(url: &str) -> bool {
    url.starts_with(MANUAL) && !url.chars().any(char::is_control)
}

#[tauri::command]
pub fn open_peritheos_manual(url: String) -> Result<(), String> {
    if !valid_manual_url(&url) {
        return Err("Choose a link in the PeriTheos manual.".into());
    }
    open_system_browser(&url)
}

pub fn open_system_browser(url: &str) -> Result<(), String> {
    if !(url.starts_with("https://") || url.starts_with("http://"))
        || url.chars().any(char::is_control)
    {
        return Err("Invalid documentation URL.".into());
    }
    #[cfg(target_os = "macos")]
    let mut command = std::process::Command::new("open");
    #[cfg(target_os = "linux")]
    let mut command = std::process::Command::new("xdg-open");
    #[cfg(target_os = "windows")]
    let mut command = {
        let mut command = std::process::Command::new("rundll32");
        command.arg("url.dll,FileProtocolHandler");
        command
    };
    command
        .arg(url)
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .spawn()
        .map(|_| ())
        .map_err(|error| format!("The system browser could not open the documentation: {error}"))
}

#[cfg(test)]
mod tests {
    use super::valid_manual_url;

    #[test]
    fn manual_links_stay_on_the_documented_origin() {
        assert!(valid_manual_url("https://peritheos.readthedocs.io/en/latest/equation-reference/#variable-exponent-debye-temperature-law"));
        for url in [
            "https://peritheos.readthedocs.io.example.org/en/latest/",
            "https://peritheos.readthedocs.io@other.example/en/latest/",
            "https://other.example/",
            "file:///tmp/help.html",
            "javascript:alert(1)",
            "https://peritheos.readthedocs.io/en/latest/\n",
        ] {
            assert!(!valid_manual_url(url), "{url}");
        }
    }
}
