"""Shared utilities for FindDubletter and FindDubleredeFoldere."""

import os
import hashlib
import datetime
from pathlib import Path

# --- CONFIGURATION ---
# Add the paths to your cloud folders and local directories here
# Example: [ '/Users/yourname/Documents', '/Users/yourname/Library/CloudStorage/OneDrive' ]
SEARCH_PATHS = [
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~"),
    os.path.expanduser("~/Library/CloudStorage/OneDrive"),
    os.path.expanduser("~/Library/Mobile Documents"),
    # Add specific paths for iCloud/Dropbox/OneDrive as needed
]

# Hash algorithm (MD5 is fast and sufficient for duplicate detection)
HASH_ALGO = "md5"
# Size threshold — only consider files >= this size (bytes)
MIN_SIZE_BYTES = 1024


def get_file_hash(file_path):
    """Return an MD5 hash string for the given file, or None on failure."""
    hasher = hashlib.new(HASH_ALGO)
    try:
        path_obj = Path(file_path)
        stat = path_obj.stat()
        
        # Ensure it is a regular file and not a FIFO, socket, device, etc.
        if (stat.st_mode & 0o170000) != 0o100000:
            return None
            
        # Skip dataless cloud placeholders on macOS (size > 0 but 0 disk blocks allocated).
        # This prevents triggering a synchronous cloud download from iCloud/OneDrive.
        if hasattr(stat, "st_blocks") and stat.st_size > 0 and stat.st_blocks == 0:
            return None

        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (PermissionError, OSError):
        return None


def get_file_info(path: Path):
    """Return a dict of file metadata for use in markdown tables."""
    try:
        stat = path.stat()
    except (PermissionError, OSError):
        return None
    
    # On macOS/BSD, st_birthtime is the creation date. On Windows, st_ctime is the creation date.
    # On Linux, st_ctime is metadata change, and st_birthtime is sometimes available in stat_result or not.
    created_time = getattr(stat, "st_birthtime", stat.st_ctime)
    return {
        "name": path.name,
        "size": f"{stat.st_size:,} bytes",
        "raw_size": stat.st_size,
        "date_added": datetime.datetime.fromtimestamp(created_time).strftime("%Y-%m-%d %H:%M"),
        "date_updated": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
        "full_path": str(path.absolute()),
    }


def format_size(num_bytes: int) -> str:
    """Return a human-readable size string."""
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024:
            return f"{num_bytes:,.0f} {unit}" if unit == "bytes" else f"{num_bytes:,.1f} {unit}"
        num_bytes //= 1024
    return f"{num_bytes:,.1f} PB"
