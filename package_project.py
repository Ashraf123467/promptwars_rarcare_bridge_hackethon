"""Packager script for LabTrace AI.

Creates a clean, lightweight distributable ZIP file excluding virtual environments,
caches, git histories, local databases, and temporary artifacts.
Calculates and verifies the exact byte and megabyte size.
"""

import os
from pathlib import Path
import zipfile

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_ZIP = PROJECT_ROOT / "labtrace_ai_prototype.zip"

# Exact directories and files to include
INCLUDED_FILES = [
    "app.py",
    "requirements.txt",
    "pytest.ini",
    "README.md",
    "package_project.py",
]

INCLUDED_DIRS = [
    "core",
    "agents",
    "storage",
    "data",
    "evaluation",
    "tests",
]

# Excluded patterns
EXCLUDED_EXTENSIONS = {".pyc", ".db", ".log", ".tmp"}
EXCLUDED_DIR_NAMES = {"__pycache__", ".pytest_cache", ".venv", "venv", ".git", ".system_generated"}


def is_allowed_file(filepath: Path) -> bool:
    if filepath.suffix in EXCLUDED_EXTENSIONS:
        return False
    for part in filepath.parts:
        if part in EXCLUDED_DIR_NAMES:
            return False
    return True


def create_distributable_zip() -> Path:
    if OUTPUT_ZIP.exists():
        OUTPUT_ZIP.unlink()

    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Include top-level files
        for fname in INCLUDED_FILES:
            fpath = PROJECT_ROOT / fname
            if fpath.exists() and is_allowed_file(fpath):
                zipf.write(fpath, arcname=fname)

        # Include specified directories
        for dname in INCLUDED_DIRS:
            dir_path = PROJECT_ROOT / dname
            if dir_path.exists():
                for root, dirs, files in os.walk(dir_path):
                    # Filter out excluded subdirs in-place
                    dirs[:] = [d for d in dirs if d not in EXCLUDED_DIR_NAMES]
                    for f in files:
                        fp = Path(root) / f
                        if is_allowed_file(fp):
                            rel_path = fp.relative_to(PROJECT_ROOT)
                            zipf.write(fp, arcname=str(rel_path))

    size_bytes = OUTPUT_ZIP.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    print("=" * 60)
    print("DISTRIBUTABLE ZIP PACKAGE REPORT")
    print("=" * 60)
    print(f"Archive Path: {OUTPUT_ZIP}")
    print(f"Total Files Packed: {len(zipf.filelist)}")
    print(f"Actual Archive Size: {size_bytes:,} bytes ({size_mb:.3f} MB)")
    print(f"Size Requirement (< 10 MB): {'PASSED [OK]' if size_mb < 10.0 else 'FAILED'}")
    print(f"Target Requirement (< 3 MB):  {'PASSED [OK]' if size_mb < 3.0 else 'WARNING'}")
    print("=" * 60)

    return OUTPUT_ZIP


if __name__ == "__main__":
    create_distributable_zip()
