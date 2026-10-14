"""
Demo loader: copies the built-in demo project into a temp directory
and creates a session for it.
"""

import os
import shutil
import tempfile
from pathlib import Path

from backend.session_store import new_session, update_session
from backend.upload_handler import scan_project_files

DEMO_DIR = Path(__file__).parent.parent / 'demo_project'


def load_demo_project() -> dict:
    """Copy demo_project to a temp dir and return session info."""
    if not DEMO_DIR.exists():
        raise FileNotFoundError(f'Demo project not found at {DEMO_DIR}')

    tmp_dir = tempfile.mkdtemp(prefix='codemedic_demo_')
    project_dir = os.path.join(tmp_dir, 'demo_project')
    shutil.copytree(str(DEMO_DIR), project_dir)

    source_files, test_files = scan_project_files(project_dir)

    sid = new_session()
    update_session(sid,
                   project_dir=project_dir,
                   source_files=source_files,
                   test_files=test_files,
                   project_name='Demo: Price-Discount Calculator')

    return {
        'session_id': sid,
        'project_name': 'Demo: Price-Discount Calculator',
        'source_files': source_files,
        'test_files': test_files,
        'file_count': len(source_files) + len(test_files),
        'description': (
            'Built-in demo project: a price-discount calculator with two '
            'reproducible bugs — a ZeroDivisionError on 100% discount and a '
            'mutable default argument in batch_discount().'
        ),
    }
