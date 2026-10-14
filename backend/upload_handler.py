"""
Upload handler: validates and extracts ZIP files to a temporary directory.
Security: rejects path traversal, limits size/count, skips venv folders.
"""

import os
import zipfile
import tempfile
import shutil
from pathlib import Path
from flask import Request

from backend.session_store import new_session, update_session

MAX_ZIP_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_FILES = 500

SKIP_DIRS = {
    '__pycache__', '.git', 'node_modules', '.venv', 'venv',
    'env', '.env', 'site-packages', 'dist', 'build', '.mypy_cache',
    '.pytest_cache', 'eggs', '.eggs',
}

ALLOWED_EXTENSIONS = {'.py', '.txt', '.md', '.cfg', '.toml', '.ini', '.json', '.yaml', '.yml'}


def _is_safe_path(base: Path, target: Path) -> bool:
    """Return True if target is within base (no path traversal)."""
    try:
        target.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def _should_skip(parts) -> bool:
    return any(p in SKIP_DIRS for p in parts)


def scan_project_files(project_dir: str):
    """Walk project_dir and return lists of source and test files."""
    source_files = []
    test_files = []
    base = Path(project_dir)

    for root, dirs, files in os.walk(project_dir):
        rel_root = Path(root).relative_to(base)
        parts = rel_root.parts

        # Prune skip dirs in place
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for fname in files:
            if not fname.endswith('.py'):
                continue
            rel_path = str(rel_root / fname).replace('\\', '/')
            abs_path = os.path.join(root, fname)
            size = os.path.getsize(abs_path)

            entry = {
                'rel_path': rel_path,
                'abs_path': abs_path,
                'size': size,
            }

            if fname.startswith('test_') or fname.endswith('_test.py') or 'test' in rel_root.parts:
                test_files.append(entry)
            else:
                source_files.append(entry)

    return source_files, test_files


def handle_upload(request: Request) -> dict:
    """Handle a ZIP upload request. Returns session info + file list."""
    if 'file' not in request.files:
        raise ValueError('No file part in request')

    f = request.files['file']
    if not f.filename:
        raise ValueError('No filename')
    if not f.filename.lower().endswith('.zip'):
        raise ValueError('Only ZIP files are accepted')

    # Read into memory first to check size
    data = f.read()
    if len(data) > MAX_ZIP_BYTES:
        raise ValueError(f'ZIP file exceeds maximum size of {MAX_ZIP_BYTES // (1024*1024)} MB')

    # Create temp dir
    tmp_dir = tempfile.mkdtemp(prefix='codemedic_')
    project_dir = os.path.join(tmp_dir, 'project')
    os.makedirs(project_dir)

    tmp_zip = os.path.join(tmp_dir, 'upload.zip')
    with open(tmp_zip, 'wb') as zf:
        zf.write(data)

    # Extract safely
    extracted_count = 0
    base_path = Path(project_dir)

    with zipfile.ZipFile(tmp_zip, 'r') as zf:
        for member in zf.infolist():
            # Reject path traversal
            member_path = Path(project_dir) / member.filename
            if not _is_safe_path(base_path, member_path):
                continue

            parts = Path(member.filename).parts
            if _should_skip(parts):
                continue

            if member.is_dir():
                os.makedirs(member_path, exist_ok=True)
                continue

            # Only extract allowed extensions
            ext = Path(member.filename).suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                continue

            if extracted_count >= MAX_FILES:
                break

            os.makedirs(member_path.parent, exist_ok=True)
            with zf.open(member) as src, open(member_path, 'wb') as dst:
                dst.write(src.read())
            extracted_count += 1

    # Detect if all files are nested under a single top-level dir (common in ZIPs)
    top_entries = os.listdir(project_dir)
    if len(top_entries) == 1 and os.path.isdir(os.path.join(project_dir, top_entries[0])):
        project_dir = os.path.join(project_dir, top_entries[0])

    source_files, test_files = scan_project_files(project_dir)

    sid = new_session()
    update_session(sid,
                   project_dir=project_dir,
                   source_files=source_files,
                   test_files=test_files,
                   project_name=f.filename.replace('.zip', ''))

    return {
        'session_id': sid,
        'project_name': f.filename.replace('.zip', ''),
        'source_files': source_files,
        'test_files': test_files,
        'file_count': len(source_files) + len(test_files),
        'extracted_count': extracted_count,
    }
