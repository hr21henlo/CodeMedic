"""
Session store: maps session_id -> project metadata dict
Stored in memory for this MVP.
"""

import uuid
import os
import shutil
import tempfile

_sessions: dict[str, dict] = {}


def new_session() -> str:
    sid = str(uuid.uuid4())
    _sessions[sid] = {
        'session_id': sid,
        'project_dir': None,
        'source_files': [],
        'test_files': [],
        'findings': [],
        'patches_applied': [],
        'test_runs': [],
        'report': None,
    }
    return sid


def get_session(sid: str) -> dict | None:
    return _sessions.get(sid)


def update_session(sid: str, **kwargs):
    if sid in _sessions:
        _sessions[sid].update(kwargs)


def cleanup_session(sid: str):
    """Remove temp directory and session data."""
    sess = _sessions.pop(sid, None)
    if sess and sess.get('project_dir'):
        shutil.rmtree(sess['project_dir'], ignore_errors=True)
