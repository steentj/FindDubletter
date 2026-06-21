import os
import hashlib
import datetime
from collections import defaultdict
from pathlib import Path
from tqdm import tqdm

# --- CONFIGURATION ---
# Add the paths to your cloud folders and local directories here
# Example: [ '/Users/yourname/Documents', '/Users/yourname/Library/CloudStorage/OneDrive' ]
SEARCH_PATHS = [
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Users/steen"),
    os.path.expanduser("~/Library/CloudStorage/OneDrive"),
    os.path.expanduser("~/Library/Mobile Documents"),
    # Add specific paths for iCloud/Dropbox/OneDrive as needed
]

# Hash algorithm (MD5 is fast and sufficient for duplicate detection)
HASH_ALGO = "md5"
# Size threshold for "Likely" vs "Defined" (e.g., only consider files > 1KB)
MIN_SIZE_BYTES = 1024 

def get_file_hash(file_path):
    """Generate a hash for a file."""
    hasher = hashlib.new(HASH_ALGO)
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (PermissionError, OSError):
        return None

def get_file_info(path):
    """Extract metadata for the markdown table."""
    try:
        stat = path.stat()
    except (PermissionError, OSError):
        return None
    return {
        "name": path.name,
        "size": f"{stat.st_size:,} bytes",
        "raw_size": stat.st_size,
        "date_added": datetime.datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M'),
        "date_updated": datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
        "full_path": str(path.absolute())
    }

def main():
    # Dictionary structure: { (size, name): [list_of_paths] }
    potential_dupes = defaultdict(list)
    
    # Step 1: Scan files and group by (Size, Name)
    print(f"Scanning directories: {SEARCH_PATHS}")
    all_files = []
    for root_path in SEARCH_PATHS:
        for root, dirs, files in os.walk(root_path):
            for name in files:
                all_files.append(os.path.join(root, name))

    print(f"Found {len(all_files)} files. Grouping by Size and Name...")
    for file_path in tqdm(all_files, desc="Grouping files"):
        try:
            p = Path(file_path)
            if p.is_file() and p.stat().st_size >= MIN_SIZE_BYTES:
                potential_dupes[(p.stat().st_size, p.name)].append(file_path)
        except (PermissionError, OSError):
            continue

    # Step 2: Verify duplicates using Hashes
    # Defined Duplicates: Same Size + Name + Hash
    # Likely Duplicates: Same Size + Name (Hash differs or fails)
    defined_duplicates = defaultdict(list)
    likely_duplicates = defaultdict(list)

    print("\nVerifying hashes for potential matches...")
    for (size, name), paths in tqdm(potential_dupes.items(), desc="Verifying hashes"):
        if len(paths) < 2:
            continue
        
        # Group these specific paths by their hash
        hash_groups = defaultdict(list)
        failed_paths = []
        for p_str in paths:
            h = get_file_hash(p_str)
            if h:
                hash_groups[h].append(p_str)
            else:
                # Can't read hash — candidate for likely duplicates
                failed_paths.append(p_str)

        # Defined duplicates: same name + size + hash
        defined_path_set = set()
        for h_val, h_paths in hash_groups.items():
            if len(h_paths) > 1:
                defined_duplicates[(size, name, h_val)].extend(h_paths)
                defined_path_set.update(h_paths)
        
        # Likely duplicates: same name+size but hash differs or unreadable.
        # Include any path not confirmed as a defined duplicate.
        likely_paths = failed_paths + [
            p for h_paths in hash_groups.values()
            for p in h_paths
            if p not in defined_path_set
        ]
        if len(likely_paths) >= 2:
            likely_duplicates[(size, name)].extend(likely_paths)

    # Step 3: Generate Markdown
    output_file = "duplicate_report.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# Duplicate Files Report\n\n")
        
        f.write("## Defined Duplicates (Identical Hash, Name, & Size)\n")
        f.write("| File Name | Size | Date Added | Date Updated | Full Path |\n")
        f.write("| --- | --- | --- | --- | --- |\n")
        
        for key, paths in defined_duplicates.items():
            for p_str in paths:
                info = get_file_info(Path(p_str))
                if info:
                    f.write(f"| {info['name']} | {info['size']} | {info['date_added']} | {info['date_updated']} | `{info['full_path']}` |\n")
            f.write("| --- | --- | --- | --- | --- |\n")  # group separator
        
        f.write("\n## Likely Duplicates (Matching Name & Size, Hash Differs)\n")
        f.write("| File Name | Size | Date Added | Date Updated | Full Path |\n")
        f.write("| --- | --- | --- | --- | --- |\n")
        
        for key, paths in likely_duplicates.items():
            for p_str in paths:
                info = get_file_info(Path(p_str))
                if info:
                    f.write(f"| {info['name']} | {info['size']} | {info['date_added']} | {info['date_updated']} | `{info['full_path']}` |\n")
            f.write("| --- | --- | --- | --- | --- |\n")  # group separator

    print(f"\nSuccess! Report generated: {os.path.abspath(output_file)}")

if __name__ == "__main__":
    main()
