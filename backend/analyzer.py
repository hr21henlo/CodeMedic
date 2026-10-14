"""
Bug analyzer: uses Python's ast module + source inspection to detect
common bug patterns. Does NOT execute uploaded code.
"""

import ast
import os
import textwrap
import uuid
from pathlib import Path
from typing import Optional

from backend.session_store import get_session, update_session


# ─── AST Visitor ─────────────────────────────────────────────────────────────

class BugVisitor(ast.NodeVisitor):
    """AST visitor that detects multiple bug pattern categories."""

    def __init__(self, source_lines: list[str], filepath: str):
        self.source_lines = source_lines
        self.filepath = filepath
        self.findings: list[dict] = []

    def _snippet(self, lineno: int, context: int = 2) -> str:
        start = max(0, lineno - 1 - context)
        end = min(len(self.source_lines), lineno + context)
        lines = self.source_lines[start:end]
        return textwrap.dedent(''.join(lines)).strip()

    def _add(self, *, title, severity, confidence, lineno, code_snippet,
             reason, fix, fix_code=None, pattern):
        self.findings.append({
            'id': str(uuid.uuid4()),
            'title': title,
            'severity': severity,       # critical / high / medium / low
            'confidence': confidence,   # confirmed / suspected
            'status': 'suspected' if confidence == 'suspected' else 'confirmed',
            'file': self.filepath,
            'line': lineno,
            'snippet': code_snippet,
            'reason': reason,
            'fix': fix,
            'fix_code': fix_code,
            'pattern': pattern,
            'test_verified': False,
            'patch_applied': False,
        })

    # ── Division by zero (literal) ──────────────────────────────────────────

    def visit_BinOp(self, node):
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            right = node.right
            # Literal zero
            if isinstance(right, ast.Constant) and right.value == 0:
                snip = self._snippet(node.lineno)
                self._add(
                    title='Division by Literal Zero',
                    severity='critical',
                    confidence='confirmed',
                    lineno=node.lineno,
                    code_snippet=snip,
                    reason='The denominator is the literal `0`. This raises `ZeroDivisionError` at runtime unconditionally.',
                    fix='Remove or correct this expression. If this is intentional, raise a `ZeroDivisionError` explicitly.',
                    pattern='div_zero_literal',
                )
            # Division where denominator is a subtraction that might equal zero
            elif isinstance(right, ast.BinOp) and isinstance(right.op, ast.Sub):
                snip = self._snippet(node.lineno)
                self._add(
                    title='Potential Division by Zero (Subtraction Denominator)',
                    severity='high',
                    confidence='suspected',
                    lineno=node.lineno,
                    code_snippet=snip,
                    reason='The denominator is a subtraction expression that could evaluate to 0 if both operands are equal.',
                    fix='Add a guard: `if denominator == 0: raise ValueError(...) or return a safe default`.',
                    pattern='div_zero_subtraction',
                )
            # Division where denominator is a variable named discount/rate/factor
            elif isinstance(right, ast.Name) and right.id in {
                'discount', 'rate', 'factor', 'divisor', 'n', 'count', 'total',
                'denominator', 'denom', 'qty', 'quantity',
                'discount_rate', 'tax_rate', 'interest_rate', 'percent', 'ratio',
                'multiplier', 'scale', 'weight', 'frequency',
            }:
                snip = self._snippet(node.lineno)
                self._add(
                    title=f'Unsafe Division by Variable `{right.id}`',
                    severity='high',
                    confidence='suspected',
                    lineno=node.lineno,
                    code_snippet=snip,
                    reason=f'`{right.id}` is divided against without a zero-check. If `{right.id}` is 0, this raises `ZeroDivisionError`.',
                    fix=f'Guard with: `if {right.id} == 0: raise ValueError(...) or return safe_default`.',
                    pattern='div_zero_variable',
                )
        self.generic_visit(node)

    # ── Mutable default arguments ────────────────────────────────────────────

    def visit_FunctionDef(self, node):
        for default in node.args.defaults + node.args.kw_defaults:
            if default is None:
                continue
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                type_name = type(default).__name__.lower()
                snip = self._snippet(node.lineno)
                self._add(
                    title=f'Mutable Default Argument ({type_name})',
                    severity='medium',
                    confidence='confirmed',
                    lineno=node.lineno,
                    code_snippet=snip,
                    reason=f'Default argument is a mutable `{type_name}`. Python creates this object once at function definition time, so mutations persist across calls.',
                    fix=f'Use `None` as default and create the `{type_name}` inside the function body.',
                    pattern='mutable_default_arg',
                )
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    # ── Suspicious comparisons ───────────────────────────────────────────────

    def visit_Compare(self, node):
        for op, comparator in zip(node.ops, node.comparators):
            # `is` instead of `==` for non-None/bool
            if isinstance(op, ast.Is):
                if not (isinstance(comparator, ast.Constant) and
                        comparator.value in (None, True, False)):
                    snip = self._snippet(node.lineno)
                    self._add(
                        title='Identity Comparison with Non-Singleton',
                        severity='medium',
                        confidence='suspected',
                        lineno=node.lineno,
                        code_snippet=snip,
                        reason='`is` checks object identity, not equality. For non-singleton values this is likely a bug.',
                        fix='Replace `is` with `==` for value equality.',
                        pattern='suspicious_is_comparison',
                    )
            # Comparing float with ==
            if isinstance(op, ast.Eq):
                if isinstance(comparator, ast.Constant) and isinstance(comparator.value, float):
                    snip = self._snippet(node.lineno)
                    self._add(
                        title='Float Equality Comparison',
                        severity='low',
                        confidence='suspected',
                        lineno=node.lineno,
                        code_snippet=snip,
                        reason='Comparing floats with `==` is unreliable due to floating-point representation errors.',
                        fix='Use `math.isclose(a, b)` or compare within a tolerance.',
                        pattern='float_equality',
                    )
        self.generic_visit(node)

    # ── Bare except ─────────────────────────────────────────────────────────

    def visit_ExceptHandler(self, node):
        if node.type is None:
            snip = self._snippet(node.lineno)
            self._add(
                title='Bare except Clause',
                severity='medium',
                confidence='confirmed',
                lineno=node.lineno,
                code_snippet=snip,
                reason='`except:` catches all exceptions including `SystemExit` and `KeyboardInterrupt`, masking real errors.',
                fix='Replace with `except Exception as e:` or a specific exception type.',
                pattern='bare_except',
            )
        self.generic_visit(node)

    # ── assert used for validation ───────────────────────────────────────────

    def visit_Assert(self, node):
        snip = self._snippet(node.lineno)
        # Only flag if assert appears in non-test files and looks like validation
        if 'test' not in self.filepath.lower():
            self._add(
                title='assert Used for Input Validation',
                severity='low',
                confidence='suspected',
                lineno=node.lineno,
                code_snippet=snip,
                reason='`assert` statements are stripped out when Python is run with the `-O` flag, making validation unreliable.',
                fix='Replace with an explicit `if not condition: raise ValueError(...)` check.',
                pattern='assert_validation',
            )
        self.generic_visit(node)

    # ── Off-by-one in range ──────────────────────────────────────────────────

    def visit_Call(self, node):
        # range(len(x)) – often a code smell; sometimes leads to off-by-one
        if (isinstance(node.func, ast.Name) and node.func.id == 'range'
                and len(node.args) == 1
                and isinstance(node.args[0], ast.Call)
                and isinstance(node.args[0].func, ast.Name)
                and node.args[0].func.id == 'len'):
            snip = self._snippet(node.lineno)
            self._add(
                title='range(len(x)) Pattern',
                severity='low',
                confidence='suspected',
                lineno=node.lineno,
                code_snippet=snip,
                reason='`range(len(x))` is error-prone and unidiomatic. Consider using `enumerate(x)` or iterating directly.',
                fix='Replace with `for item in x:` or `for i, item in enumerate(x):`.',
                pattern='range_len',
            )
        self.generic_visit(node)


# ─── Analyzer entry point ─────────────────────────────────────────────────────

def _analyze_file(abs_path: str, rel_path: str) -> list[dict]:
    """Parse one Python file and return findings."""
    try:
        with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
            source = f.read()
    except OSError:
        return []

    try:
        tree = ast.parse(source, filename=rel_path)
    except SyntaxError as e:
        return [{
            'id': str(uuid.uuid4()),
            'title': 'Syntax Error',
            'severity': 'critical',
            'confidence': 'confirmed',
            'status': 'confirmed',
            'file': rel_path,
            'line': e.lineno or 0,
            'snippet': str(e.text or '').strip(),
            'reason': f'The file contains a syntax error: {e.msg}',
            'fix': 'Fix the syntax error.',
            'fix_code': None,
            'pattern': 'syntax_error',
            'test_verified': False,
            'patch_applied': False,
        }]

    source_lines = source.splitlines(keepends=True)
    visitor = BugVisitor(source_lines, rel_path)
    visitor.visit(tree)

    # Attach full source for patch generation
    for f_item in visitor.findings:
        f_item['_source_lines'] = source_lines
        f_item['_abs_path'] = abs_path

    return visitor.findings


def analyze_project(session_id: str) -> dict:
    """Analyze all source files in a session's project directory."""
    sess = get_session(session_id)
    if not sess:
        raise ValueError(f'Unknown session: {session_id}')

    all_findings = []
    files_analyzed = []

    for entry in sess['source_files']:
        findings = _analyze_file(entry['abs_path'], entry['rel_path'])
        all_findings.extend(findings)
        files_analyzed.append(entry['rel_path'])

    # Sort by severity
    severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    all_findings.sort(key=lambda f: severity_order.get(f['severity'], 99))

    # Strip internal fields for storage (keep for patch use)
    update_session(session_id, findings=all_findings, files_analyzed=files_analyzed)

    # Return clean version (no internal fields)
    clean = []
    for f in all_findings:
        c = {k: v for k, v in f.items() if not k.startswith('_')}
        clean.append(c)

    return {
        'session_id': session_id,
        'files_analyzed': files_analyzed,
        'finding_count': len(clean),
        'findings': clean,
    }
