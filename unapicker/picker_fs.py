"""FUSE filesystem for file picker integration."""

import errno
import logging
import os
import stat
import subprocess
import time
from pathlib import Path
from typing import List, Optional, Tuple

from fuse import FUSE, FuseOSError, Operations

logger = logging.getLogger(__name__)


class PickerFS(Operations):
    """FUSE filesystem that triggers file picker on read."""

    def __init__(self, pickers: List[str], cache_timeout: int = 5):
        """
        Initialize picker filesystem.

        Args:
            pickers: List of picker commands to try in order (with fallbacks)
            cache_timeout: Cache result for N seconds (0 to disable)
        """
        self.pickers = pickers
        self.pending_result: Optional[bytes] = None
        self.cache_timeout = cache_timeout
        self.cache: Optional[Tuple[bytes, float]] = None  # (content, timestamp)

    def _trigger_picker(self) -> Optional[bytes]:
        """
        Try each picker command in order until one succeeds.
        Returns the contents of the selected file.

        Returns:
            File contents as bytes, or None if all pickers fail
        """
        logger.info("File picker accessed")
        for picker_cmd in self.pickers:
            logger.info(f"Trying picker: {picker_cmd}")
            try:
                result = subprocess.run(
                    picker_cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0 and result.stdout.strip():
                    selected_file = result.stdout.strip()
                    logger.info(f"Picker selected: {selected_file}")

                    # Read the selected file's contents
                    try:
                        with open(selected_file, 'rb') as f:
                            contents = f.read()
                        logger.info(f"Read {len(contents)} bytes from {selected_file}")
                        return contents
                    except Exception as e:
                        logger.error(f"Failed to read {selected_file}: {e}")
                        continue
                else:
                    logger.debug(f"Picker failed with code {result.returncode}")
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                logger.debug(f"Picker error: {e}")
                continue

        logger.warning("All pickers failed")
        return None

    def open(self, path, flags):
        """Handle file open - trigger picker or return cached result."""
        if path == "/picker":
            # Check cache first
            if self.cache_timeout > 0 and self.cache:
                contents, timestamp = self.cache
                if time.time() - timestamp < self.cache_timeout:
                    logger.info("Using cached picker result")
                    self.pending_result = contents
                    return 0

            # Run picker
            contents = self._trigger_picker()
            self.pending_result = contents if contents else b""

            # Cache the result
            if self.cache_timeout > 0 and contents:
                self.cache = (contents, time.time())
                logger.info(f"Cached result for {self.cache_timeout}s")

            return 0
        raise FuseOSError(errno.ENOENT)

    def read(self, path, size, offset, fh):
        """Return the picker result."""
        if self.pending_result is None:
            return b""
        return self.pending_result[offset : offset + size]

    def getattr(self, path, fh=None):
        """Return file attributes."""
        if path == "/":
            return {
                "st_mode": stat.S_IFDIR | 0o755,
                "st_nlink": 2,
                "st_uid": os.getuid(),
                "st_gid": os.getgid(),
                "st_size": 4096,
            }
        elif path == "/picker":
            size = len(self.pending_result) if self.pending_result else 0
            return {
                "st_mode": stat.S_IFREG | 0o644,
                "st_nlink": 1,
                "st_uid": os.getuid(),
                "st_gid": os.getgid(),
                "st_size": size,
            }
        raise FuseOSError(errno.ENOENT)

    def readdir(self, path, fh):
        """List directory contents."""
        if path == "/":
            return [".", "..", "picker"]
        raise FuseOSError(errno.ENOTDIR)

    def statfs(self, path):
        """Return filesystem stats."""
        return {
            "f_bsize": 4096,
            "f_frsize": 4096,
            "f_blocks": 1000,
            "f_bfree": 1000,
            "f_bavail": 1000,
            "f_files": 10,
            "f_ffree": 10,
            "f_favail": 10,
        }


def mount_picker_fs(mount_point: str, pickers: List[str], foreground: bool = False, cache_timeout: int = 5):
    """
    Mount the picker filesystem.

    Args:
        mount_point: Path where to create symlink to the picker file
        pickers: List of picker commands to try
        foreground: If True, run in foreground (for debugging)
        cache_timeout: Cache picker result for N seconds (0 to disable)
    """
    # Mount FUSE at a hidden location
    fuse_mount_path = Path("/tmp/.picker-fuse")

    # Unmount any existing FUSE mount
    import subprocess as sp
    sp.run(["fusermount", "-u", str(fuse_mount_path)], capture_output=True)

    fuse_mount_path.mkdir(parents=True, exist_ok=True)

    # Remove old symlink/directory if it exists
    symlink_path = Path(mount_point)
    if symlink_path.is_symlink():
        symlink_path.unlink()
    elif symlink_path.is_dir():
        import shutil as sh
        sh.rmtree(symlink_path)
    elif symlink_path.exists():
        symlink_path.unlink()
    symlink_path.parent.mkdir(parents=True, exist_ok=True)

    fs = PickerFS(pickers, cache_timeout=cache_timeout)
    logger.info(f"Mounting FUSE filesystem at {fuse_mount_path} (cache: {cache_timeout}s)")

    # Create symlink BEFORE mounting
    symlink_path.symlink_to(str(fuse_mount_path / "picker"))
    logger.info(f"Created symlink {symlink_path} -> {fuse_mount_path}/picker")

    # Force foreground=True to keep the process alive for systemd
    FUSE(fs, str(fuse_mount_path), foreground=True)
