"""
Report generator: creates a structured final investigation report.
"""

import datetime
from backend.session_store import get_session, update_session


def generate_report(session_id: str) -> dict:
    sess = get_session(session_id)
    if not sess:
        raise ValueError('Unknown session')

    findings = sess.get('findings', [])
    patches_applied = sess.get('patches_applied', [])
    test_runs = sess.get('test_runs', [])
    files_analyzed = sess.get('files_analyzed', [])
    project_name = sess.get('project_name', 'Unknown Project')

    fixed = [f for f in findings if f.get('patch_applied') or f.get('status') == 'fixed']
    unresolved = [f for f in findings if not f.get('patch_applied') and f.get('status') != 'fixed']

    # Aggregate test results
    total_passed = 0
    total_failed = 0
    total_error = 0
    last_exit_code = None
    all_runs = []

    for run_data in test_runs:
        for r in run_data.get('runs', []):
            c = r.get('counts', {})
            total_passed += c.get('passed', 0)
            total_failed += c.get('failed', 0)
            total_error += c.get('error', 0)
            last_exit_code = r.get('exit_code')
            all_runs.append({
                'label': r.get('label', ''),
                'command': r.get('command', ''),
                'exit_code': r.get('exit_code'),
                'passed': r.get('passed', False),
                'duration': r.get('duration', 0),
                'counts': c,
            })

    uncertainties = []
    if unresolved:
        uncertainties.append(f'{len(unresolved)} issue(s) detected but not patched.')
    if total_failed > 0 or total_error > 0:
        uncertainties.append(f'{total_failed} test failure(s) and {total_error} error(s) remain.')
    for f in findings:
        if f.get('confidence') == 'suspected' and not f.get('patch_applied'):
            uncertainties.append(f'"{f["title"]}" at {f["file"]}:{f["line"]} is suspected but not confirmed by a failing test.')

    if not uncertainties:
        uncertainties.append('No significant uncertainty identified. All patched issues have passing tests.')

    report = {
        'generated_at': datetime.datetime.now().isoformat(),
        'project_name': project_name,
        'summary': {
            'files_analyzed': len(files_analyzed),
            'total_findings': len(findings),
            'fixed': len(fixed),
            'unresolved': len(unresolved),
            'patches_applied': len(patches_applied),
            'test_runs_executed': len(all_runs),
            'tests_passed': total_passed,
            'tests_failed': total_failed,
            'tests_error': total_error,
            'last_exit_code': last_exit_code,
        },
        'files_inspected': files_analyzed,
        'fixed_issues': [
            {
                'title': f['title'],
                'file': f['file'],
                'line': f['line'],
                'severity': f['severity'],
                'fix': f.get('fix', ''),
            }
            for f in fixed
        ],
        'unresolved_issues': [
            {
                'title': f['title'],
                'file': f['file'],
                'line': f['line'],
                'severity': f['severity'],
                'confidence': f.get('confidence', ''),
                'reason': f.get('reason', ''),
            }
            for f in unresolved
        ],
        'test_runs': all_runs,
        'uncertainties': uncertainties,
        'disclaimer': (
            'This investigation was performed by static analysis (AST inspection). '
            'Static analysis identifies suspected issues; it does not guarantee bugs exist. '
            'Test execution results reflect actual command output. '
            'This MVP is for trusted demo projects only — not a hardened multi-tenant sandbox.'
        ),
    }

    update_session(session_id, report=report)
    return report
