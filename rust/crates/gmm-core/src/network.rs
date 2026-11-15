//! Erkennung von Netzlaufwerken (Port von `platform_support.is_network_path`).

use std::path::Path;

pub const NETWORK_FILESYSTEM_TYPES: &[&str] = &[
    "9p",
    "afs",
    "ceph",
    "cifs",
    "davfs",
    "davfs2",
    "fuse.curlftpfs",
    "fuse.davfs",
    "fuse.gvfsd-fuse",
    "fuse.rclone",
    "fuse.sshfs",
    "fuseblk",
    "glusterfs",
    "nfs",
    "nfs4",
    "smb3",
    "sshfs",
];

/// Momentaufnahme der Mount-Tabelle, damit ein Scan sie nur einmal liest.
#[derive(Debug, Clone, Default)]
pub struct MountTable {
    #[allow(dead_code)]
    mounts: Vec<(std::path::PathBuf, String)>,
}

impl MountTable {
    pub fn load() -> Self {
        #[cfg(target_os = "linux")]
        {
            let Ok(content) = std::fs::read_to_string("/proc/self/mountinfo") else {
                return Self::default();
            };
            Self::parse_mountinfo(&content)
        }
        #[cfg(not(target_os = "linux"))]
        {
            Self::default()
        }
    }

    /// Parst `/proc/self/mountinfo` (Feld 5 = Mountpunkt, nach ` - ` = Dateisystem).
    pub fn parse_mountinfo(content: &str) -> Self {
        let mounts = content
            .lines()
            .filter_map(|line| {
                let (left, right) = line.split_once(" - ")?;
                let mount_point = left.split(' ').nth(4)?;
                let fs_type = right.split(' ').next()?;
                Some((unescape_octal(mount_point).into(), fs_type.to_string()))
            })
            .collect();
        Self { mounts }
    }

    pub fn filesystem_type(&self, path: &Path) -> Option<&str> {
        let candidate = crate::paths::normalize(&crate::paths::absolute(path));
        self.mounts
            .iter()
            .filter(|(mount, _)| candidate.starts_with(mount))
            .max_by_key(|(mount, _)| mount.as_os_str().len())
            .map(|(_, fs)| fs.as_str())
    }

    pub fn is_network_path(&self, path: &Path) -> bool {
        #[cfg(windows)]
        {
            let _ = self;
            windows_is_network_path(path)
        }
        #[cfg(not(windows))]
        {
            self.filesystem_type(path)
                .map(|fs| NETWORK_FILESYSTEM_TYPES.contains(&fs.to_lowercase().as_str()))
                .unwrap_or(false)
        }
    }
}

pub fn is_network_path(path: &Path) -> bool {
    MountTable::load().is_network_path(path)
}

/// `\040` usw. in mountinfo-Pfaden zurückwandeln.
fn unescape_octal(value: &str) -> String {
    let bytes = value.as_bytes();
    let mut output = Vec::with_capacity(bytes.len());
    let mut index = 0;
    while index < bytes.len() {
        if bytes[index] == b'\\' && index + 3 < bytes.len() {
            let digits = &bytes[index + 1..index + 4];
            if digits.iter().all(|b| (b'0'..=b'7').contains(b)) {
                if let Ok(byte) = u8::from_str_radix(std::str::from_utf8(digits).unwrap_or(""), 8) {
                    output.push(byte);
                    index += 4;
                    continue;
                }
            }
        }
        output.push(bytes[index]);
        index += 1;
    }
    String::from_utf8_lossy(&output).into_owned()
}

#[cfg(windows)]
fn windows_is_network_path(path: &Path) -> bool {
    use std::os::windows::ffi::OsStrExt;
    let text = path.to_string_lossy().replace('/', "\\");
    if text.starts_with("\\\\") {
        // \\server\share und \\?\UNC\server\share; \\?\C:\ ist lokal.
        return !text.starts_with("\\\\?\\") || text.to_lowercase().starts_with("\\\\?\\unc\\");
    }
    let mut chars = text.chars();
    let (Some(letter), Some(':')) = (chars.next(), chars.next()) else { return false };
    if !letter.is_ascii_alphabetic() {
        return false;
    }
    let root: Vec<u16> = std::ffi::OsStr::new(&format!("{letter}:\\")).encode_wide().chain(Some(0)).collect();
    // DRIVE_REMOTE = 4
    unsafe { windows_sys::Win32::Storage::FileSystem::GetDriveTypeW(root.as_ptr()) == 4 }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[cfg(unix)]
    #[test]
    fn longest_mount_wins() {
        let table = MountTable::parse_mountinfo(
            "22 1 0:21 / / rw - ext4 /dev/sda1 rw\n\
             40 22 0:35 / /mnt/nas\\040share rw - cifs //nas/share rw\n",
        );
        assert!(table.is_network_path(Path::new("/mnt/nas share/mods")));
        assert!(!table.is_network_path(Path::new("/home/user")));
    }
}
