//! Atomic file publication with one permissions policy for scientific outputs.
//! Content is staged in a private directory on the destination filesystem. New
//! files use the kernel's umask; replacements retain the target's permissions.
use std::{fs::File, io::Write, path::Path};

fn builder() -> tempfile::Builder<'static, 'static> {
    let mut builder = tempfile::Builder::new();
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        // The kernel applies umask at creation. Never inspect/change the
        // process-global mask in a multithreaded application.
        builder.permissions(std::fs::Permissions::from_mode(0o666));
    }
    builder
}

pub(crate) struct StagedOutput {
    file: tempfile::NamedTempFile,
    _directory: tempfile::TempDir,
}
impl StagedOutput {
    pub(crate) fn new(target: &Path) -> Result<Self, String> {
        let parent = target
            .parent()
            .filter(|p| !p.as_os_str().is_empty())
            .unwrap_or(Path::new("."));
        let mut directory = tempfile::Builder::new();
        directory.prefix(".dioptas-output-");
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            directory.permissions(std::fs::Permissions::from_mode(0o700));
        }
        let directory = directory.tempdir_in(parent).map_err(|e| e.to_string())?;
        let file = builder()
            .tempfile_in(directory.path())
            .map_err(|e| e.to_string())?;
        Ok(Self {
            file,
            _directory: directory,
        })
    }
    pub(crate) fn path(&self) -> &Path {
        self.file.path()
    }
    pub(crate) fn as_file(&self) -> &File {
        self.file.as_file()
    }
    pub(crate) fn as_file_mut(&mut self) -> &mut File {
        self.file.as_file_mut()
    }
    pub(crate) fn commit(self, target: &Path) -> Result<(), String> {
        match std::fs::metadata(target) {
            Ok(metadata) => self
                .file
                .as_file()
                .set_permissions(metadata.permissions())
                .map_err(|e| e.to_string())?,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
            Err(error) => return Err(error.to_string()),
        }
        self.file.as_file().sync_all().map_err(|e| e.to_string())?;
        self.file.persist(target).map_err(|e| e.to_string())?;
        Ok(())
    }
}
impl Write for StagedOutput {
    fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
        self.as_file_mut().write(bytes)
    }
    fn flush(&mut self) -> std::io::Result<()> {
        self.as_file_mut().flush()
    }
}

/// Reserve a unique companion filename. It is empty until a private stage is
/// committed over it, and is removed on failure until its owner calls keep().
pub(crate) fn resource_path(
    parent: &Path,
    prefix: &str,
    suffix: &str,
) -> Result<tempfile::TempPath, String> {
    builder()
        .prefix(prefix)
        .suffix(suffix)
        .tempfile_in(parent)
        .map(tempfile::NamedTempFile::into_temp_path)
        .map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn aborted_output_preserves_original_and_removes_stage() {
        let directory = tempfile::tempdir().unwrap();
        let target = directory.path().join("result.xy");
        std::fs::write(&target, b"original").unwrap();
        let mut staged = StagedOutput::new(&target).unwrap();
        let stage = staged.path().to_owned();
        staged.write_all(b"partial").unwrap();
        drop(staged);
        assert_eq!(std::fs::read(&target).unwrap(), b"original");
        assert!(!stage.exists());
        assert_eq!(std::fs::read_dir(directory.path()).unwrap().count(), 1);
    }
    #[cfg(unix)]
    #[test]
    fn overwrite_preserves_target_mode() {
        use std::os::unix::fs::PermissionsExt;
        let directory = tempfile::tempdir().unwrap();
        let target = directory.path().join("result.poni");
        std::fs::write(&target, b"original").unwrap();
        std::fs::set_permissions(&target, std::fs::Permissions::from_mode(0o664)).unwrap();
        let mut staged = StagedOutput::new(&target).unwrap();
        staged.write_all(b"complete").unwrap();
        staged.commit(&target).unwrap();
        assert_eq!(
            std::fs::metadata(&target).unwrap().permissions().mode() & 0o777,
            0o664
        );
        assert_eq!(std::fs::read(&target).unwrap(), b"complete");
    }
    #[cfg(unix)]
    #[test]
    fn umask_child() {
        use std::os::unix::fs::PermissionsExt;
        let Ok(mode) = std::env::var("DIOPTAS_OUTPUT_TEST_MODE") else {
            return;
        };
        let expected = u32::from_str_radix(&mode, 8).unwrap();
        let directory = tempfile::tempdir().unwrap();
        let target = directory.path().join("new.xy");
        let mut staged = StagedOutput::new(&target).unwrap();
        assert_eq!(
            std::fs::metadata(staged.path().parent().unwrap())
                .unwrap()
                .permissions()
                .mode()
                & 0o777,
            0o700
        );
        staged.write_all(b"complete").unwrap();
        staged.commit(&target).unwrap();
        assert_eq!(
            std::fs::metadata(&target).unwrap().permissions().mode() & 0o777,
            expected
        );
        let resource = resource_path(directory.path(), "detector-", ".nxs").unwrap();
        let mut staged = StagedOutput::new(&resource).unwrap();
        staged.write_all(b"resource").unwrap();
        staged.commit(&resource).unwrap();
        assert_eq!(
            std::fs::metadata(&resource).unwrap().permissions().mode() & 0o777,
            expected
        );
        drop(resource);
        assert_eq!(std::fs::read_dir(directory.path()).unwrap().count(), 1);
    }
    #[cfg(unix)]
    #[test]
    fn new_outputs_honor_umask_without_changing_the_parent_mask() {
        for (mask, expected) in [("022", "644"), ("077", "600")] {
            let status = std::process::Command::new("/bin/sh")
                .args([
                    "-c",
                    "umask \"$1\"; exec \"$2\" --exact output::tests::umask_child",
                    "output-test",
                    mask,
                ])
                .arg(std::env::current_exe().unwrap())
                .env("DIOPTAS_OUTPUT_TEST_MODE", expected)
                .status()
                .unwrap();
            assert!(status.success());
        }
    }
}
