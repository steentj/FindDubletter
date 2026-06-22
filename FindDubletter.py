import os
from collections import defaultdict
from pathlib import Path
from tqdm import tqdm

from _shared import SEARCH_PATHS, MIN_SIZE_BYTES, get_file_hash, get_file_info

def main():
    # Dictionary structure: { (size, name): [list_of_paths] }
    potential_dupes = defaultdict(list)
    
    # Step 1: Scan files and group by (Size, Name)
    print(f"Scanning directories: {SEARCH_PATHS}")
    all_files = []
    for root_path in SEARCH_PATHS:
        if not os.path.exists(root_path):
            print(f"  [advarsel] Stien findes ikke: {root_path}")
            continue
        for root, dirs, files in os.walk(root_path):
            # Exclude hidden directories (dotfiles) and system paths like Library, caches, virtual environments to avoid getting stuck
            dirs[:] = [
                d for d in dirs
                if not d.startswith(".")
                and d not in ("Library", "node_modules", "venv", ".venv", "local")
            ]
            for name in files:
                all_files.append(os.path.join(root, name))

    print(f"Found {len(all_files)} files. Grouping by Size and Name...")
    for file_path in tqdm(all_files, desc="Grouping files"):
        try:
            p = Path(file_path)
            stat = p.stat()
            size = stat.st_size
            if stat.st_mode & 0o170000 == 0o100000:  # standard file check (safer than is_file() which can call stat again)
                if size >= MIN_SIZE_BYTES:
                    potential_dupes[(size, p.name)].append(file_path)
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
