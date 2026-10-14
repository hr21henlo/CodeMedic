"""
Patch generator and applier.
Generates before/after diffs and applies user-approved patches.
"""

import ast
import os
import shutil
import textwrap
import difflib
from pathlib import Path

from backend.session_store import get_session, update_session


def _get_finding(sess: dict, finding_id: str) -> dict | None:
    for f in sess['findings']:
        if f['id'] == finding_id:
            return f
    return None


def _read_source(abs_path: str) -> list[str]:
    with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
        return f.readlines()


def _generate_patch_for_finding(finding: dict, source_lines: list[str]) -> dict | None:
    """
    Generate a targeted patch for a finding based on its pattern.
    Returns dict with 'original_lines', 'patched_lines', 'line_start', 'line_end'
    or None if no automatic patch can be generated.
    """
    pattern = finding.get('pattern', '')
    lineno = finding.get('line', 0)  # 1-indexed
    abs_path = finding.get('_abs_path', '')

    if not source_lines or lineno < 1 or lineno > len(source_lines):
        return None

    idx = lineno - 1  # 0-indexed

    if pattern == 'mutable_default_arg':
        return _patch_mutable_default(source_lines, idx, abs_path)
    elif pattern == 'bare_except':
        return _patch_bare_except(source_lines, idx)
    elif pattern in ('div_zero_variable', 'div_zero_subtraction'):
        return _patch_div_zero_guard(source_lines, idx, finding)
    else:
        # Return informational-only patch (show snippet, suggest fix)
        return None


def _patch_mutable_default(source_lines: list[str], func_line_idx: int, abs_path: str) -> dict | None:
    """Replace mutable default arguments with None and add guard inside function."""
    try:
        source = ''.join(source_lines)
        tree = ast.parse(source)
    except SyntaxError:
        return None

    # Find the function node at this line
    target_func = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno - 1 == func_line_idx:
                target_func = node
                break

    if not target_func:
        return None

    # We'll generate a textual suggestion rather than a code rewrite
    # (safe for MVP — show what needs changing without full AST rewrite)
    orig_line = source_lines[func_line_idx].rstrip('\n')
    # Replace [] with None, {} with None, set() with None in the def line
    import re
    patched = re.sub(r'=\s*\[\]', '=None', orig_line)
    patched = re.sub(r'=\s*\{\}', '=None', patched)

    if patched == orig_line:
        return None

    # For the body, suggest adding a guard after the docstring
    # Find the first statement in the body
    body_start = target_func.body[0].lineno - 1  # 0-indexed

    original_lines = source_lines[func_line_idx:body_start + 1]
    patched_lines = [patched + '\n']

    # Add None guards for each mutable default
    for arg_node, default in zip(
        target_func.args.args[-len(target_func.args.defaults):],
        target_func.args.defaults
    ):
        if isinstance(default, (ast.List, ast.Dict, ast.Set)):
            type_str = '[]' if isinstance(default, ast.List) else ('{}' if isinstance(default, ast.Dict) else 'set()')
            guard = f'    if {arg_node.arg} is None:\n        {arg_node.arg} = {type_str}\n'
            patched_lines.append(guard)

    # Append existing body first line
    if body_start < len(source_lines):
        patched_lines.append(source_lines[body_start])

    return {
        'line_start': func_line_idx + 1,
        'line_end': body_start + 1,
        'original_lines': original_lines,
        'patched_lines': patched_lines,
    }


def _patch_bare_except(source_lines: list[str], except_line_idx: int) -> dict | None:
    """Replace bare `except:` with `except Exception as e:`."""
    line = source_lines[except_line_idx]
    import re
    patched = re.sub(r'except\s*:', 'except Exception as e:', line)
    if patched == line:
        return None
    return {
        'line_start': except_line_idx + 1,
        'line_end': except_line_idx + 1,
        'original_lines': [line],
        'patched_lines': [patched],
    }


def _patch_div_zero_guard(source_lines: list[str], lineno_idx: int, finding: dict) -> dict | None:
    """
    Fix an unsafe division by replacing the buggy expression.
    For known patterns (e.g. dividing by discount_rate instead of multiplying),
    replaces the whole expression. Otherwise adds a zero-guard.
    """
    import re as _re
    line = source_lines[lineno_idx]
    indent = len(line) - len(line.lstrip())
    ind = ' ' * indent

    try:
        tree = ast.parse(line.strip())
    except SyntaxError:
        return None

    denom_name = None
    lhs_name = None
    numer_name = None

    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv)):
            if isinstance(node.right, ast.Name):
                denom_name = node.right.id
            if isinstance(node.left, ast.Name):
                numer_name = node.left.id

    # Find LHS assignment target if any
    assign_match = _re.match(r'\s*(\w+)\s*=', line)
    if assign_match:
        lhs_name = assign_match.group(1)

    if not denom_name:
        return None

    # Heuristic: if the variable is named discount_rate / rate / factor and
    # we're computing something like `x / discount_rate`, the likely correct
    # formula is `x * discount_rate`. Replace the division with multiplication.
    rate_like = {'discount_rate', 'rate', 'factor', 'discount', 'percent'}
    if denom_name in rate_like and numer_name and lhs_name:
        # Build corrected line: lhs = numer * (1 - denom) — standard discount
        fixed_expr = f'{numer_name} * (1 - {denom_name})'
        patched_line = f'{ind}{lhs_name} = {fixed_expr}\n'
        return {
            'line_start': lineno_idx + 1,
            'line_end': lineno_idx + 1,
            'original_lines': [line],
            'patched_lines': [patched_line],
        }

    # Generic fallback: add a zero-guard before the line
    guard = f'{ind}if {denom_name} == 0:\n{ind}    raise ValueError(f"{denom_name} cannot be zero")\n'
    patched_lines = [guard, line]

    return {
        'line_start': lineno_idx + 1,
        'line_end': lineno_idx + 1,
        'original_lines': [line],
        'patched_lines': patched_lines,
    }


def _make_unified_diff(original_lines: list[str], patched_lines: list[str],
                       filename: str, line_start: int) -> str:
    """Create a unified diff string."""
    diff = difflib.unified_diff(
        original_lines,
        patched_lines,
        fromfile=f'a/{filename}',
        tofile=f'b/{filename}',
        lineterm='\n',
        n=3,
    )
    return ''.join(diff)


def get_patch(session_id: str, finding_id: str) -> dict:
    """Preview a patch for a finding without applying it."""
    sess = get_session(session_id)
    if not sess:
        raise ValueError('Unknown session')

    finding = _get_finding(sess, finding_id)
    if not finding:
        raise ValueError('Unknown finding')

    abs_path = finding.get('_abs_path')
    if not abs_path or not os.path.exists(abs_path):
        return {
            'finding_id': finding_id,
            'patchable': False,
            'message': 'Source file not available for patching.',
            'suggested_fix': finding.get('fix', ''),
        }

    source_lines = _read_source(abs_path)
    patch_info = _generate_patch_for_finding(finding, source_lines)

    if not patch_info:
        return {
            'finding_id': finding_id,
            'patchable': False,
            'message': 'No automatic patch available for this pattern.',
            'suggested_fix': finding.get('fix', ''),
            'snippet': finding.get('snippet', ''),
        }

    diff = _make_unified_diff(
        patch_info['original_lines'],
        patch_info['patched_lines'],
        finding['file'],
        patch_info['line_start'],
    )

    return {
        'finding_id': finding_id,
        'patchable': True,
        'file': finding['file'],
        'line_start': patch_info['line_start'],
        'line_end': patch_info['line_end'],
        'original': ''.join(patch_info['original_lines']),
        'patched': ''.join(patch_info['patched_lines']),
        'diff': diff,
        'patch_info': patch_info,  # stored internally
    }


def apply_patch(session_id: str, finding_id: str) -> dict:
    """Apply the patch for a finding after user approval."""
    sess = get_session(session_id)
    if not sess:
        raise ValueError('Unknown session')

    finding = _get_finding(sess, finding_id)
    if not finding:
        raise ValueError('Unknown finding')

    abs_path = finding.get('_abs_path')
    if not abs_path or not os.path.exists(abs_path):
        return {'success': False, 'error': 'Source file not available'}

    source_lines = _read_source(abs_path)
    patch_info = _generate_patch_for_finding(finding, source_lines)

    if not patch_info:
        return {
            'success': False,
            'error': 'No automatic patch available for this pattern.',
            'suggested_fix': finding.get('fix', ''),
        }

    # Validate the patch (parse the patched result)
    start_idx = patch_info['line_start'] - 1  # 0-indexed
    end_idx = patch_info['line_end']           # exclusive

    new_lines = (
        source_lines[:start_idx] +
        patch_info['patched_lines'] +
        source_lines[end_idx:]
    )
    new_source = ''.join(new_lines)

    try:
        ast.parse(new_source)
    except SyntaxError as e:
        return {
            'success': False,
            'error': f'Patched code has a syntax error: {e}. Patch was NOT applied.',
        }

    # Backup original
    backup_path = abs_path + '.bak'
    shutil.copy2(abs_path, backup_path)

    # Write patched file
    try:
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(new_source)
    except OSError as e:
        # Restore backup
        shutil.copy2(backup_path, abs_path)
        return {'success': False, 'error': f'Failed to write file: {e}'}

    # Mark finding as patched
    finding['patch_applied'] = True
    finding['status'] = 'patch_applied'

    patches_applied = sess.get('patches_applied', [])
    patches_applied.append({
        'finding_id': finding_id,
        'file': finding['file'],
        'backup': backup_path,
        'original_lines': patch_info['original_lines'],
        'patched_lines': patch_info['patched_lines'],
    })
    update_session(session_id, patches_applied=patches_applied)

    return {
        'success': True,
        'file': finding['file'],
        'backup': backup_path,
        'original': ''.join(patch_info['original_lines']),
        'patched': ''.join(patch_info['patched_lines']),
        'diff': _make_unified_diff(
            patch_info['original_lines'],
            patch_info['patched_lines'],
            finding['file'],
            patch_info['line_start'],
        ),
    }
