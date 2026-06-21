# FindDubletter

A Python script that scans your Mac for duplicate files and generates a Markdown report.

## How It Works

The script uses a two-pass strategy to find duplicates:

1. **Grouping pass** — Walks all configured directories and groups files by `(size, filename)`. Files below the size threshold are ignored.
2. **Verification pass** — For each candidate group, computes an MD5 hash to confirm whether files are truly identical.

Results are classified as:

| Category | Criteria |
| --- | --- |
| **Defined Duplicates** | Same filename + size + MD5 hash — byte-for-byte identical files |
| **Likely Duplicates** | Same filename + size but different hash (or unreadable) — probable duplicates worth investigating |

A report is written to `duplicate_report.md` in the current working directory.

## Requirements

- Python 3.12+
- [`tqdm`](https://github.com/tqdm/tqdm) (progress bars)

Install dependencies with [uv](https://github.com/astral-sh/uv):

```bash
uv sync
```

Or with pip:

```bash
pip install tqdm
```

## Usage

```bash
python FindDubletter.py
```

The script prints progress to the terminal and writes the report when finished:

```
Scanning directories: ['/Users/you/Documents', '/Users/you/Desktop']
Found 12,345 files. Grouping by Size and Name...
Grouping files: 100%|████████████| 12345/12345 [00:03<00:00]
Verifying hashes for potential matches...
Verifying hashes: 100%|█████████| 200/200 [00:01<00:00]

Success! Report generated: /Users/you/Projects/FindDubletter/duplicate_report.md
```

## Configuration

Edit the top of `FindDubletter.py` to customise behaviour:

```python
# Directories to scan
SEARCH_PATHS = [
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Desktop"),
    # Uncomment / add paths for cloud folders:
    # os.path.expanduser("~/Library/CloudStorage/OneDrive-Personal"),
    # os.path.expanduser("~/Dropbox"),
]

# Hash algorithm — md5 is fast and sufficient for duplicate detection
HASH_ALGO = "md5"

# Ignore files smaller than this (bytes). Default: 1 KB
MIN_SIZE_BYTES = 1024
```

### Common Paths on macOS

| Service | Typical Path |
| --- | --- |
| iCloud Drive | `~/Library/Mobile Documents/com~apple~CloudDocs` |
| OneDrive (Personal) | `~/Library/CloudStorage/OneDrive-Personal` |
| Dropbox | `~/Dropbox` |
| Google Drive | `~/Library/CloudStorage/GoogleDrive-*/My Drive` |

## Output Format

`duplicate_report.md` contains two sections. Each group of duplicates is separated by a horizontal row so you can clearly see which files are copies of one another.

```markdown
## Defined Duplicates (Identical Hash, Name, & Size)
| File Name | Size | Date Added | Date Updated | Full Path |
| report.pdf | 245,120 bytes | 2024-03-01 09:12 | 2024-03-01 09:12 | `/Users/you/Documents/report.pdf` |
| report.pdf | 245,120 bytes | 2024-05-10 14:33 | 2024-03-01 09:12 | `/Users/you/Desktop/report.pdf` |
| --- | ...
```

## Notes

- The script skips files it cannot read (permission errors) rather than crashing.
- Symlinks are not followed; only regular files are hashed.
- No files are modified or deleted — the script is read-only.
