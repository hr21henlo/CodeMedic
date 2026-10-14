"""
Test runner: discovers and executes tests in the project directory.
Captures stdout, stderr, exit code, duration, test counts.
Never fabricates results.

⚠️  WARNING: This MVP runs tests from user-supplied code.
    Only use with trusted projects during demos.
"""

import os
import subprocess
import sys
import time
import re
import shutil
from pathlib import Path

from backend.session_store import get_session, update_session

TEST_TIMEOUT = 60  # seconds


def _find_test_files(project_dir: str) -> list[str]:
    """Return list of test file paths relative to project_dir."""
    test_files = []
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git', 'venv', '.venv', 'env')]
        for fname in files:
            if fname.startswith('test_') or fname.endswith('_test.py'):
                rel = os.path.relpath(os.path.join(root, fname), project_dir)
                test_files.append(rel)
    return test_files


def _detect_frameworks(project_dir: str) -> dict:
    """Detect available test frameworks."""
    pytest_available = shutil.which('pytest') is not None
    # Also check if pytest is importable
    if not pytest_available:
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', '--version'],
            capture_output=True, text=True, timeout=10
        )
        pytest_available = result.returncode == 0

    return {
        'pytest': pytest_available,
        'unittest': True,  # always available in stdlib
    }


def _parse_pytest_output(stdout: str, stderr: str) -> dict:
    """Extract pass/fail/error counts from pytest output."""
    counts = {'passed': 0, 'failed': 0, 'error': 0, 'skipped': 0}
    # Match "X passed, Y failed, Z error" pattern
    summary_re = re.compile(
        r'(\d+)\s+passed|(\d+)\s+failed|(\d+)\s+error|(\d+)\s+skipped'
    )
    for m in summary_re.finditer(stdout + stderr):
        if m.group(1):
            counts['passed'] = int(m.group(1))
        if m.group(2):
            counts['failed'] = int(m.group(2))
        if m.group(3):
            counts['error'] = int(m.group(3))
        if m.group(4):
            counts['skipped'] = int(m.group(4))
    return counts


def _parse_unittest_output(stdout: str, stderr: str) -> dict:
    """Extract pass/fail counts from unittest output."""
    counts = {'passed': 0, 'failed': 0, 'error': 0, 'skipped': 0}
    # "Ran X tests in Y.Zs"
    ran_m = re.search(r'Ran (\d+) test', stderr + stdout)
    if ran_m:
        total = int(ran_m.group(1))
        fail_m = re.search(r'FAILED \(.*?failures=(\d+)', stderr + stdout)
        err_m = re.search(r'errors=(\d+)', stderr + stdout)
        failures = int(fail_m.group(1)) if fail_m else 0
        errors = int(err_m.group(1)) if err_m else 0
        counts['failed'] = failures
        counts['error'] = errors
        counts['passed'] = total - failures - errors
    elif 'OK' in (stderr + stdout):
        # "OK" with no failures
        ok_m = re.search(r'Ran (\d+) test', stderr + stdout)
        if ok_m:
            counts['passed'] = int(ok_m.group(1))
    return counts


def run_tests(session_id: str, scope: str = 'full', finding_id: str = None) -> dict:
    """
    Run tests for the project.
    scope: 'full' or 'targeted'
    """
    sess = get_session(session_id)
    if not sess:
        raise ValueError('Unknown session')

    project_dir = sess.get('project_dir')
    if not project_dir or not os.path.isdir(project_dir):
        return {
            'success': False,
            'error': 'Project directory not found',
            'runs': [],
        }

    test_files = _find_test_files(project_dir)
    frameworks = _detect_frameworks(project_dir)
    runs = []

    if not test_files:
        result = {
            'success': False,
            'error': 'No test files found in the project.',
            'test_files': [],
            'runs': [],
            'frameworks': frameworks,
        }
        _append_test_run(session_id, result)
        return result

    # Choose test runner
    use_pytest = frameworks['pytest']

    if scope == 'targeted' and finding_id:
        # Run only the test file most relevant to the finding
        finding = next((f for f in sess['findings'] if f['id'] == finding_id), None)
        if finding:
            # Find test files that mention the source file name
            src_name = Path(finding['file']).stem
            relevant = [t for t in test_files if src_name in t or 'test_' + src_name in t]
            if relevant:
                test_files_to_run = relevant
            else:
                test_files_to_run = test_files[:1]  # fallback: first test
        else:
            test_files_to_run = test_files
    else:
        test_files_to_run = test_files

    for test_file in test_files_to_run:
        run_result = _run_single_test(
            project_dir, test_file, use_pytest, frameworks
        )
        runs.append(run_result)

    # Also run full suite if targeted was run
    if scope == 'targeted' and test_files_to_run != test_files:
        full_run = _run_all_tests(project_dir, test_files, use_pytest)
        full_run['label'] = 'Full Test Suite'
        runs.append(full_run)

    overall_passed = all(r.get('exit_code', 1) == 0 for r in runs)

    result = {
        'success': True,
        'overall_passed': overall_passed,
        'test_files_discovered': test_files,
        'test_files_run': test_files_to_run,
        'frameworks': frameworks,
        'runs': runs,
    }

    _append_test_run(session_id, result)

    # Mark findings as test_verified if tests passed
    if overall_passed:
        for f in sess['findings']:
            if f.get('patch_applied'):
                f['test_verified'] = True
                f['status'] = 'fixed'

    return result


def _run_single_test(project_dir: str, test_file: str, use_pytest: bool, frameworks: dict) -> dict:
    """Run a single test file."""
    start = time.time()
    cmd_display = ''

    if use_pytest:
        cmd = [sys.executable, '-m', 'pytest', test_file, '-v', '--tb=short', '--no-header']
        cmd_display = f'python -m pytest {test_file} -v --tb=short'
    else:
        # unittest discover
        module = test_file.replace(os.sep, '.').replace('/', '.').replace('.py', '')
        cmd = [sys.executable, '-m', 'unittest', module, '-v']
        cmd_display = f'python -m unittest {module} -v'

    try:
        proc = subprocess.run(
            cmd,
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=TEST_TIMEOUT,
            env={**os.environ, 'PYTHONPATH': project_dir},
        )
        duration = time.time() - start

        if use_pytest:
            counts = _parse_pytest_output(proc.stdout, proc.stderr)
        else:
            counts = _parse_unittest_output(proc.stdout, proc.stderr)

        return {
            'label': f'Test: {test_file}',
            'command': cmd_display,
            'test_file': test_file,
            'exit_code': proc.returncode,
            'passed': proc.returncode == 0,
            'duration': round(duration, 3),
            'stdout': proc.stdout,
            'stderr': proc.stderr,
            'counts': counts,
            'framework': 'pytest' if use_pytest else 'unittest',
        }

    except subprocess.TimeoutExpired:
        duration = time.time() - start
        return {
            'label': f'Test: {test_file}',
            'command': cmd_display,
            'test_file': test_file,
            'exit_code': -1,
            'passed': False,
            'duration': round(duration, 3),
            'stdout': '',
            'stderr': f'Test timed out after {TEST_TIMEOUT} seconds.',
            'counts': {'passed': 0, 'failed': 0, 'error': 1, 'skipped': 0},
            'framework': 'pytest' if use_pytest else 'unittest',
        }


def _run_all_tests(project_dir: str, test_files: list[str], use_pytest: bool) -> dict:
    """Run all tests in the project directory."""
    start = time.time()

    if use_pytest:
        cmd = [sys.executable, '-m', 'pytest', '.', '-v', '--tb=short', '--no-header']
        cmd_display = 'python -m pytest . -v --tb=short'
    else:
        cmd = [sys.executable, '-m', 'unittest', 'discover', '-v']
        cmd_display = 'python -m unittest discover -v'

    try:
        proc = subprocess.run(
            cmd,
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=TEST_TIMEOUT,
            env={**os.environ, 'PYTHONPATH': project_dir},
        )
        duration = time.time() - start

        if use_pytest:
            counts = _parse_pytest_output(proc.stdout, proc.stderr)
        else:
            counts = _parse_unittest_output(proc.stdout, proc.stderr)

        return {
            'label': 'Full Test Suite',
            'command': cmd_display,
            'exit_code': proc.returncode,
            'passed': proc.returncode == 0,
            'duration': round(duration, 3),
            'stdout': proc.stdout,
            'stderr': proc.stderr,
            'counts': counts,
            'framework': 'pytest' if use_pytest else 'unittest',
        }

    except subprocess.TimeoutExpired:
        duration = time.time() - start
        return {
            'label': 'Full Test Suite',
            'command': cmd_display,
            'exit_code': -1,
            'passed': False,
            'duration': round(duration, 3),
            'stdout': '',
            'stderr': f'Tests timed out after {TEST_TIMEOUT} seconds.',
            'counts': {'passed': 0, 'failed': 0, 'error': 1, 'skipped': 0},
            'framework': 'pytest' if use_pytest else 'unittest',
        }


def _append_test_run(session_id: str, run_data: dict):
    sess = get_session(session_id)
    if sess:
        runs = sess.get('test_runs', [])
        runs.append(run_data)
        update_session(session_id, test_runs=runs)
