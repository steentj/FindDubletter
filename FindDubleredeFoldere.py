"""
FindDubleredeFoldere.py
-----------------------
Finder alle foldere, hvor det SAMLEDE indhold (filer og understruktur) er identisk.
Genererer en Markdown-rapport: folder_duplicate_report.md
"""

import os
import hashlib
import datetime
from collections import defaultdict
from pathlib import Path
from tqdm import tqdm

from _shared import SEARCH_PATHS, HASH_ALGO, get_file_hash, format_size


# ---------------------------------------------------------------------------
# Helpers & Caching
# ---------------------------------------------------------------------------

# Global cache to keep folder stats during tree hashing and avoid repeating full os.walk.
# Structure: { folder_path: (total_size, file_count) }
_folder_stats_cache = {}


def get_folder_hash(folder_path: str) -> str | None:
    """
    Compute a single hash that represents the complete recursive content of a
    folder — both the relative file-tree structure and every file's bytes.
    Returns None if the folder is empty or any file cannot be read.
    Also caches file size and count to optimize later report generation.
    """
    entries: list[tuple[str, str]] = []  # (relative_path, file_hash)
    total_size = 0
    file_count = 0

    try:
        for root, dirs, files in os.walk(folder_path):
            # Consistent filtering of system/hidden directories, preventing entering Library
            dirs[:] = [
                d for d in dirs
                if not d.startswith(".")
                and d not in ("Library", "node_modules", "venv", ".venv", "local")
            ]
            dirs.sort()  # deterministic traversal order
            for fname in sorted(files):
                fpath = Path(root) / fname
                if fpath.is_symlink():
                    continue
                
                # Cross-platform compatibility check: convert backslashes to forward slashes
                rel = Path(fpath.relative_to(folder_path)).as_posix()
                
                # Retrieve hash and metadata in fewer/cached calls
                file_hash = get_file_hash(fpath)
                if file_hash is None:
                    return None  # unreadable file → can't fully verify
                
                try:
                    total_size += fpath.stat().st_size
                    file_count += 1
                except (PermissionError, OSError):
                    pass
                    
                entries.append((rel, file_hash))
    except (PermissionError, OSError):
        return None

    if not entries:
        return None  # skip empty folders

    hasher = hashlib.new(HASH_ALGO)
    for rel_path, file_hash in entries:
        hasher.update(rel_path.encode("utf-8"))
        hasher.update(file_hash.encode("utf-8"))
        
    _folder_stats_cache[folder_path] = (total_size, file_count)
    return hasher.hexdigest()


def get_folder_info(folder_path: str) -> dict | None:
    """Return metadata for a folder for use in the markdown table."""
    path = Path(folder_path)
    try:
        stat = path.stat()
        # Retrieve from cache to avoid recursive os.walk again
        if folder_path in _folder_stats_cache:
            total_size, file_count = _folder_stats_cache[folder_path]
        else:
            total_size = 0
            file_count = 0
            for root, _dirs, files in os.walk(folder_path):
                for fname in files:
                    try:
                        total_size += (Path(root) / fname).stat().st_size
                        file_count += 1
                    except (PermissionError, OSError):
                        pass
    except (PermissionError, OSError):
        return None

    created_time = getattr(stat, "st_birthtime", stat.st_ctime)
    return {
        "name": path.name,
        "file_count": file_count,
        "total_size": format_size(total_size),
        "date_added": datetime.datetime.fromtimestamp(created_time).strftime("%Y-%m-%d %H:%M"),
        "date_updated": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
        "full_path": str(path.absolute()),
    }


def remove_sub_duplicates(
    groups: dict[str, list[str]],
) -> dict[str, list[str]]:
    """
    When a parent folder is already reported as a duplicate, its sub-folders
    will trivially match too.  Remove those sub-duplicate groups so the report
    stays focused on the highest-level matches.
    """
    # Collect and resolve all duplicate folder paths (across all groups) into a lookup set
    all_dup_paths_resolved = {str(Path(p).resolve()) for paths in groups.values() for p in paths}

    filtered: dict[str, list[str]] = {}
    for h, paths in groups.items():
        # Check: is any path in this group a *strict* sub-path of a path in
        # another group?  If all paths are sub-paths, skip the whole group.
        def is_sub_of_other_dup(p: str) -> bool:
            p_resolved = Path(p).resolve()
            # Fast O(L) check: walk up the folder's parent folders and check if any are in the O(1) lookup set
            for parent in p_resolved.parents:
                if str(parent) in all_dup_paths_resolved:
                    return True
            return False

        if all(is_sub_of_other_dup(p) for p in paths):
            continue  # every instance is inside a higher-level duplicate
        filtered[h] = paths

    return filtered


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # ------------------------------------------------------------------
    # Step 1: Collect all directories
    # ------------------------------------------------------------------
    print(f"Søger i: {SEARCH_PATHS}")
    print("Indsamler foldere …")

    all_folders: list[str] = []
    for root_path in SEARCH_PATHS:
        if not os.path.isdir(root_path):
            print(f"  [advarsel] Stien findes ikke: {root_path}")
            continue
        for root, dirs, _files in os.walk(root_path):
            # Exclude hidden folders and system directories (e.g., Library) to avoid massive caches and hangs
            dirs[:] = [
                d for d in dirs
                if not d.startswith(".")
                and d not in ("Library", "node_modules", "venv", ".venv", "local")
            ]
            dirs.sort()
            all_folders.append(root)
            for d in dirs:
                all_folders.append(os.path.join(root, d))

    # Deduplicate (os.walk may yield the root itself)
    all_folders = list(dict.fromkeys(all_folders))
    print(f"Fandt {len(all_folders):,} foldere. Beregner indholds-hash …")

    # ------------------------------------------------------------------
    # Step 2: Hash every folder
    # ------------------------------------------------------------------
    hash_to_folders: dict[str, list[str]] = defaultdict(list)
    failed = 0

    for folder in tqdm(all_folders, desc="Hashing foldere"):
        h = get_folder_hash(folder)
        if h is None:
            failed += 1
            continue
        hash_to_folders[h].append(folder)

    if failed:
        print(f"  (kunne ikke hashe {failed:,} foldere — manglende rettigheder eller tomme foldere)")

    # ------------------------------------------------------------------
    # Step 3: Keep only groups with 2+ folders (actual duplicates)
    # ------------------------------------------------------------------
    duplicate_groups = {h: paths for h, paths in hash_to_folders.items() if len(paths) >= 2}
    print(f"\nFandt {len(duplicate_groups):,} grupper af identiske foldere.")

    # ------------------------------------------------------------------
    # Step 4: Remove sub-duplicates (sub-folders of already-reported dups)
    # ------------------------------------------------------------------
    print("Filtrerer under-dubletter væk …")
    top_level_groups = remove_sub_duplicates(duplicate_groups)
    removed = len(duplicate_groups) - len(top_level_groups)
    if removed:
        print(f"  ({removed:,} grupper fjernet fordi de er under-foldere af allerede rapporterede dubletter)")

    # ------------------------------------------------------------------
    # Step 5: Gather folder metadata for the report
    # ------------------------------------------------------------------
    print("Indsamler metadata til rapport …")

    # Sort groups by total_size of first folder (largest first)
    def group_sort_key(item):
        _h, paths = item
        folder_path = paths[0]
        # Retrieve from cache to avoid recursive os.walk again
        if folder_path in _folder_stats_cache:
            return _folder_stats_cache[folder_path][0]
        try:
            return sum(
                (Path(root) / f).stat().st_size
                for root, _dirs, files in os.walk(folder_path)
                for f in files
            )
        except (PermissionError, OSError):
            return 0

    sorted_groups = sorted(top_level_groups.items(), key=group_sort_key, reverse=True)

    # ------------------------------------------------------------------
    # Step 6: Write Markdown report
    # ------------------------------------------------------------------
    output_file = "folder_duplicate_report.md"
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# Rapport: Dublerede Foldere\n\n")
        f.write(f"_Genereret: {now}_\n\n")
        f.write(
            f"Søgt i {len(SEARCH_PATHS)} rod-sti(er). "
            f"Fandt **{len(sorted_groups):,}** grupper af identiske foldere "
            f"(under-dubletter er fjernet).\n\n"
        )

        if not sorted_groups:
            f.write("_Ingen dublerede foldere fundet._\n")
        else:
            f.write("## Identiske Foldere (samme indhold og struktur)\n\n")
            f.write("| Mappenavn | Filer | Samlet størrelse | Oprettet | Ændret | Fuld sti |\n")
            f.write("| --- | ---: | ---: | --- | --- | --- |\n")

            for h, paths in tqdm(sorted_groups, desc="Skriver rapport"):
                for p_str in paths:
                    info = get_folder_info(p_str)
                    if info:
                        f.write(
                            f"| {info['name']} "
                            f"| {info['file_count']:,} "
                            f"| {info['total_size']} "
                            f"| {info['date_added']} "
                            f"| {info['date_updated']} "
                            f"| `{info['full_path']}` |\n"
                        )
                f.write("| --- | --- | --- | --- | --- | --- |\n")  # group separator

    print(f"\nFærdig! Rapport gemt: {os.path.abspath(output_file)}")


if __name__ == "__main__":
    main()
