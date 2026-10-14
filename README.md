# CodeMedic: Software Delivery Agent

> AI-powered bug investigation, focused patching, and real test execution for Python codebases.

---

## ⚡ Quick Start (Windows)

### 1 · Prerequisites

- Python 3.10 or newer (`python --version`)
- pip

### 2 · Install dependencies

```powershell
cd codemedic
pip install -r requirements.txt
```

### 3 · Run the application

```powershell
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

---

## 🎯 Demo Walkthrough (1-minute demo)

1. Click **"Load Demo Project"** on the Project Setup screen.
2. Navigate to **Codebase Overview** — you'll see `pricing.py` (source) and `test_pricing.py` (tests).
3. Click **"🔍 Investigate Codebase"** — CodeMedic runs static analysis and shows findings.
4. In **Bug Findings**, expand the *Division by Literal Zero* finding — see the snippet, root cause, and suggested fix.
5. Click **"🩹 View Patch"** — review the before/after diff.
6. Click **"✅ Apply Patch"** — the patch is validated, backed up, then written.
7. Go to **Test Console** → **"▶ Run Full Test Suite"** — actual test output appears.
8. Go to **Final Report** → **"📋 Generate Report"** — see fixed issues, test counts, and remaining uncertainty.

---

## 🗂 Project Structure

```
codemedic/
├── app.py                    ← Flask entry point
├── requirements.txt
├── README.md
├── backend/
│   ├── __init__.py
│   ├── session_store.py      ← In-memory session management
│   ├── upload_handler.py     ← Secure ZIP extraction
│   ├── analyzer.py           ← AST-based bug detection
│   ├── patcher.py            ← Patch generation & application
│   ├── test_runner.py        ← Real test execution (pytest / unittest)
│   ├── reporter.py           ← Final report generation
│   └── demo_loader.py        ← Built-in demo project loader
├── frontend/
│   ├── templates/index.html  ← Single-page dashboard
│   └── static/
│       ├── css/main.css      ← Dark developer theme
│       └── js/app.js         ← All frontend logic
└── demo_project/
    ├── pricing.py            ← Source with two reproducible bugs
    └── test_pricing.py       ← Tests that fail before fix, pass after
```

---

## 🐛 Built-in Demo Bugs

### Bug 1 — Division by Zero (Critical · Confirmed)

**File:** `pricing.py`, function `apply_discount()`

```python
# BUGGY — raises ZeroDivisionError when discount_rate == 1.0
discounted = original_price * discount_rate / (1 - discount_rate)
```

**Fix:** Replace with:
```python
discounted = original_price * (1 - discount_rate)
```

### Bug 2 — Mutable Default Argument (Medium · Confirmed)

**File:** `pricing.py`, function `batch_discount()`

```python
# BUGGY — results=[] is shared across all calls
def batch_discount(prices: list, discount_rate: float, results=[]) -> list:
```

**Fix:**
```python
def batch_discount(prices: list, discount_rate: float, results=None) -> list:
    if results is None:
        results = []
```

---

## 🔍 What CodeMedic Detects

| Pattern | Severity | Confidence |
|---------|----------|------------|
| Division by literal zero | Critical | Confirmed |
| Unsafe division (variable denominator) | High | Suspected |
| Mutable default arguments | Medium | Confirmed |
| Bare `except:` clauses | Medium | Confirmed |
| Identity comparison (`is`) with non-singleton | Medium | Suspected |
| Float equality comparison | Low | Suspected |
| `assert` used for validation | Low | Suspected |
| `range(len(x))` pattern | Low | Suspected |

---

## ⚠ Security Notice

This MVP is designed for **local, trusted demo projects only**.
- Uploaded code is analyzed statically (AST) — never executed during analysis.
- Tests are only run after an **explicit user action**.
- ZIP uploads are validated against path traversal and size/count limits.
- This is **not** a hardened multi-tenant sandbox. Do not deploy publicly.

---

## 🔧 Troubleshooting

**Port already in use:**
```powershell
python app.py  # defaults to 5000
# or change the port in app.py
```

**pytest not found:**
CodeMedic falls back to `python -m unittest` automatically.

**No test results shown:**
Ensure your project has files named `test_*.py` or `*_test.py`.
