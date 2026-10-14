/* ═══════════════════════════════════════════════════════
   CodeMedic — Frontend Application Logic
   ═══════════════════════════════════════════════════════ */

'use strict';

// ─── State ────────────────────────────────────────────────────────────────────
const state = {
  sessionId: null,
  projectName: null,
  sourceFiles: [],
  testFiles: [],
  findings: [],
  selectedFindingId: null,
  patchPreviews: {},   // findingId -> patch preview data
  appliedPatches: new Set(),
};

// ─── Utilities ────────────────────────────────────────────────────────────────
function $(id) { return document.getElementById(id); }

function showToast(msg, type = 'info', duration = 3500) {
  const container = $('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = msg;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), duration);
}

function setSpinner(spinnerId, visible) {
  const el = $(spinnerId);
  if (el) el.style.display = visible ? 'inline-block' : 'none';
}

function setDisabled(btnId, disabled) {
  const el = $(btnId);
  if (el) el.disabled = disabled;
}

function fmtBytes(b) {
  if (b < 1024) return b + ' B';
  if (b < 1024 * 1024) return (b / 1024).toFixed(1) + ' KB';
  return (b / (1024 * 1024)).toFixed(1) + ' MB';
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function apiFetch(url, body = null) {
  const opts = {
    method: body ? 'POST' : 'GET',
    headers: { 'Content-Type': 'application/json' },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(url, opts);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

// ─── Navigation ───────────────────────────────────────────────────────────────
function navTo(sectionId) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const section = $(`section-${sectionId}`);
  if (section) section.classList.add('active');
  const navItem = $(`nav-${sectionId}`);
  if (navItem) navItem.classList.add('active');
}

document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', e => {
    e.preventDefault();
    navTo(item.dataset.section);
  });
});

// ─── Section 1: Upload ────────────────────────────────────────────────────────
const dropzone   = $('upload-dropzone');
const fileInput  = $('file-input');
const browseBtn  = $('browse-btn');
const uploadBtn  = $('upload-btn');
const demoBtn    = $('demo-btn');
const uploadFn   = $('upload-filename');

browseBtn.addEventListener('click', () => fileInput.click());
dropzone.addEventListener('click', e => { if (e.target === dropzone) fileInput.click(); });

fileInput.addEventListener('change', () => {
  if (fileInput.files.length) {
    uploadFn.textContent = fileInput.files[0].name;
    uploadBtn.style.display = 'inline-flex';
  }
});

// Drag & drop
dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('drag-over'); });
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
dropzone.addEventListener('drop', e => {
  e.preventDefault();
  dropzone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file && file.name.endsWith('.zip')) {
    fileInput.files = e.dataTransfer.files;
    uploadFn.textContent = file.name;
    uploadBtn.style.display = 'inline-flex';
  } else {
    showToast('Please drop a .zip file', 'error');
  }
});

uploadBtn.addEventListener('click', async () => {
  if (!fileInput.files.length) return;
  setSpinner('upload-spinner', true);
  setDisabled('upload-btn', true);
  try {
    const fd = new FormData();
    fd.append('file', fileInput.files[0]);
    const res = await fetch('/api/upload', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Upload failed');
    onProjectLoaded(data);
    showToast(`Loaded ${data.file_count} files from "${data.project_name}"`, 'success');
  } catch (err) {
    showToast('Upload failed: ' + err.message, 'error');
  } finally {
    setSpinner('upload-spinner', false);
    setDisabled('upload-btn', false);
  }
});

demoBtn.addEventListener('click', async () => {
  setSpinner('demo-spinner', true);
  setDisabled('demo-btn', true);
  try {
    const data = await apiFetch('/api/demo', {});
    onProjectLoaded(data);
    showToast('Demo project loaded!', 'success');
  } catch (err) {
    showToast('Failed to load demo: ' + err.message, 'error');
  } finally {
    setSpinner('demo-spinner', false);
    setDisabled('demo-btn', false);
  }
});

function onProjectLoaded(data) {
  state.sessionId   = data.session_id;
  state.projectName = data.project_name;
  state.sourceFiles = data.source_files || [];
  state.testFiles   = data.test_files || [];

  // Update session status pill
  $('session-status').textContent = data.project_name;
  $('session-status').classList.add('loaded');
  $('test-cwd-display').textContent = data.project_name;

  renderOverview();
  navTo('overview');
}

// ─── Section 2: Overview ──────────────────────────────────────────────────────
function renderOverview() {
  $('overview-project-name').textContent = state.projectName;

  // Stats
  $('overview-stats').innerHTML = `
    <div class="stat-card">
      <div class="stat-value">${state.sourceFiles.length}</div>
      <div class="stat-label">Source Files</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">${state.testFiles.length}</div>
      <div class="stat-label">Test Files</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">${state.sourceFiles.length + state.testFiles.length}</div>
      <div class="stat-label">Total Python Files</div>
    </div>
  `;

  // File lists
  $('source-file-list').innerHTML = state.sourceFiles.length
    ? state.sourceFiles.map(f => `
        <div class="file-item">
          <span>🐍</span>
          <span>${escapeHtml(f.rel_path)}</span>
          <span class="file-item-size">${fmtBytes(f.size)}</span>
        </div>`).join('')
    : '<div class="empty-state"><div class="empty-state-icon">🗂</div>No source files found</div>';

  $('test-file-list').innerHTML = state.testFiles.length
    ? state.testFiles.map(f => `
        <div class="file-item">
          <span>🧪</span>
          <span>${escapeHtml(f.rel_path)}</span>
          <span class="file-item-size">${fmtBytes(f.size)}</span>
        </div>`).join('')
    : '<div class="empty-state"><div class="empty-state-icon">🔎</div>No test files found</div>';
}

$('investigate-btn').addEventListener('click', async () => {
  if (!state.sessionId) return showToast('Load a project first', 'error');
  setSpinner('investigate-spinner', true);
  setDisabled('investigate-btn', true);
  try {
    const data = await apiFetch('/api/analyze', { session_id: state.sessionId });
    state.findings = data.findings || [];
    renderFindings();

    // Update badge
    const badge = $('findings-badge');
    badge.textContent = state.findings.length;
    badge.style.display = state.findings.length ? 'inline-block' : 'none';

    showToast(`Found ${state.findings.length} issue(s) across ${data.files_analyzed.length} file(s)`,
      state.findings.length ? 'info' : 'success');
    navTo('findings');
  } catch (err) {
    showToast('Analysis failed: ' + err.message, 'error');
  } finally {
    setSpinner('investigate-spinner', false);
    setDisabled('investigate-btn', false);
  }
});

// ─── Section 3: Findings ──────────────────────────────────────────────────────
function severityIcon(sev) {
  return { critical: '🔴', high: '🟠', medium: '🟡', low: '🔵' }[sev] || '⚪';
}

function statusLabel(status) {
  const map = {
    suspected:     'Suspected',
    confirmed:     'Confirmed',
    patch_applied: 'Patch Applied',
    fixed:         'Fixed',
    not_verified:  'Not Verified',
  };
  return map[status] || status;
}

function renderFindings() {
  $('findings-summary').textContent =
    `${state.findings.length} issue(s) detected across ${state.sourceFiles.length} file(s).`;

  const container = $('findings-list');

  if (!state.findings.length) {
    container.innerHTML = `
      <div class="card">
        <div class="empty-state">
          <div class="empty-state-icon">✅</div>
          No issues detected. The codebase looks clean!
        </div>
      </div>`;
    return;
  }

  container.innerHTML = state.findings.map((f, i) => `
    <div class="finding-card" id="finding-card-${f.id}">
      <div class="finding-header" onclick="toggleFinding('${f.id}')">
        <span class="sev-badge sev-${f.severity}">${f.severity}</span>
        <span class="finding-title">${escapeHtml(f.title)}</span>
        <span class="finding-status status-${f.status}">${statusLabel(f.status)}</span>
        <span class="finding-loc">${escapeHtml(f.file)}:${f.line}</span>
        <span class="finding-chevron">▼</span>
      </div>
      <div class="finding-body" id="finding-body-${f.id}">
        <div class="finding-section">
          <div class="finding-section-label">📍 Location</div>
          <p><code class="code-inline">${escapeHtml(f.file)}</code> — Line ${f.line}</p>
        </div>
        <div class="finding-section">
          <div class="finding-section-label">🔎 Code Snippet</div>
          <pre class="code-block">${escapeHtml(f.snippet)}</pre>
        </div>
        <div class="finding-section">
          <div class="finding-section-label">💡 Why This May Be Incorrect</div>
          <p>${escapeHtml(f.reason)}</p>
        </div>
        <div class="finding-section">
          <div class="finding-section-label">🛠 Suggested Fix</div>
          <p>${escapeHtml(f.fix)}</p>
        </div>
        <div class="finding-section">
          <div class="finding-section-label">🔬 Confidence</div>
          <p>${f.confidence === 'confirmed'
            ? '✅ Confirmed — static analysis identified a definite bug pattern.'
            : '⚠ Suspected — this pattern <em>may</em> be a bug; verify with tests.'}</p>
        </div>
        <div class="finding-actions">
          <button class="btn btn-primary btn-sm" onclick="previewPatch('${f.id}')">
            🩹 View Patch
          </button>
          <button class="btn btn-secondary btn-sm" onclick="runTargetedTests('${f.id}')">
            🧪 Run Targeted Tests
          </button>
        </div>
      </div>
    </div>
  `).join('');

  // Also populate patch selector
  renderPatchSelector();
}

function toggleFinding(id) {
  const card = $(`finding-card-${id}`);
  if (card) card.classList.toggle('expanded');
}

function previewPatch(findingId) {
  state.selectedFindingId = findingId;
  navTo('patch');
  loadPatchPreview(findingId);

  // Highlight in selector
  document.querySelectorAll('.patch-item').forEach(el => el.classList.remove('selected'));
  const item = document.querySelector(`[data-finding-id="${findingId}"]`);
  if (item) item.classList.add('selected');
}

$('run-tests-btn-findings').addEventListener('click', () => {
  navTo('tests');
  runFullTests();
});

// ─── Section 4: Patch Review ──────────────────────────────────────────────────
function renderPatchSelector() {
  const list = $('patch-finding-list');
  if (!state.findings.length) {
    list.innerHTML = '<div class="empty-state">Run investigation first.</div>';
    return;
  }
  list.innerHTML = state.findings.map(f => `
    <div class="patch-item" data-finding-id="${f.id}" onclick="previewPatch('${f.id}')">
      <span class="sev-badge sev-${f.severity}">${f.severity}</span>
      <span class="patch-item-title">${escapeHtml(f.title)}</span>
      <span class="finding-loc">${escapeHtml(f.file)}:${f.line}</span>
      ${state.appliedPatches.has(f.id)
        ? '<span class="finding-status status-patch_applied">Applied</span>'
        : ''}
    </div>
  `).join('');
}

async function loadPatchPreview(findingId) {
  const finding = state.findings.find(f => f.id === findingId);
  if (!finding) return;

  $('patch-finding-title').textContent = finding.title;
  $('patch-meta').textContent = `${finding.file} · Line ${finding.line} · ${finding.severity} severity`;
  $('patch-detail').style.display = 'block';
  $('patch-success-msg').style.display = 'none';
  $('patch-error-msg').style.display = 'none';
  $('patch-not-auto').style.display = 'none';
  $('patch-before').textContent = '';
  $('patch-after').textContent = '';
  $('apply-patch-btn').style.display = 'inline-flex';
  $('reject-patch-btn').style.display = 'inline-flex';

  // Check cache
  if (state.patchPreviews[findingId]) {
    renderPatchDetail(state.patchPreviews[findingId], findingId);
    return;
  }

  $('patch-before').textContent = 'Loading…';
  $('patch-after').textContent = 'Loading…';

  try {
    const data = await apiFetch('/api/patch', {
      session_id: state.sessionId,
      finding_id: findingId,
      action: 'preview',
    });
    state.patchPreviews[findingId] = data;
    renderPatchDetail(data, findingId);
  } catch (err) {
    $('patch-before').textContent = 'Error loading patch: ' + err.message;
    $('patch-after').textContent = '';
  }
}

function renderPatchDetail(data, findingId) {
  if (data.patchable) {
    $('patch-before').textContent = data.original;
    $('patch-after').textContent = data.patched;
    $('patch-not-auto').style.display = 'none';
  } else {
    $('patch-before').textContent = data.snippet || '(see finding for code)';
    $('patch-after').textContent = '(Manual fix required)';
    $('patch-not-auto').style.display = 'block';
    $('patch-suggested-fix').textContent = data.suggested_fix || data.message || '';
    $('apply-patch-btn').style.display = 'none';
  }

  if (state.appliedPatches.has(findingId)) {
    $('patch-actions').style.display = 'none';
    $('patch-success-msg').style.display = 'block';
    $('patch-success-msg').textContent = '✅ Patch has already been applied.';
  }
}

$('apply-patch-btn').addEventListener('click', async () => {
  if (!state.selectedFindingId || !state.sessionId) return;
  if (!confirm('Apply this patch to the source file? A backup will be created automatically.')) return;

  setSpinner('apply-spinner', true);
  setDisabled('apply-patch-btn', true);
  setDisabled('reject-patch-btn', true);

  try {
    const data = await apiFetch('/api/patch', {
      session_id: state.sessionId,
      finding_id: state.selectedFindingId,
      action: 'apply',
    });
    if (data.success) {
      state.appliedPatches.add(state.selectedFindingId);
      // Update finding status in local state
      const f = state.findings.find(x => x.id === state.selectedFindingId);
      if (f) { f.patch_applied = true; f.status = 'patch_applied'; }

      $('patch-actions').style.display = 'none';
      $('patch-success-msg').style.display = 'block';
      $('patch-success-msg').textContent =
        `✅ Patch applied to ${data.file}. Backup saved as ${data.file}.bak`;
      showToast('Patch applied successfully!', 'success');

      // Refresh findings display
      renderFindings();
    } else {
      $('patch-error-msg').style.display = 'block';
      $('patch-error-msg').textContent = '❌ ' + (data.error || 'Patch failed.');
      showToast('Patch failed: ' + data.error, 'error');
      setDisabled('apply-patch-btn', false);
      setDisabled('reject-patch-btn', false);
    }
  } catch (err) {
    $('patch-error-msg').style.display = 'block';
    $('patch-error-msg').textContent = '❌ ' + err.message;
    showToast('Error: ' + err.message, 'error');
    setDisabled('apply-patch-btn', false);
    setDisabled('reject-patch-btn', false);
  } finally {
    setSpinner('apply-spinner', false);
  }
});

$('reject-patch-btn').addEventListener('click', () => {
  $('patch-detail').style.display = 'none';
  state.selectedFindingId = null;
  document.querySelectorAll('.patch-item').forEach(el => el.classList.remove('selected'));
  showToast('Patch rejected.', 'info');
});

// ─── Section 5: Tests ─────────────────────────────────────────────────────────
$('run-full-tests-btn').addEventListener('click', runFullTests);

async function runFullTests() {
  if (!state.sessionId) return showToast('Load a project first', 'error');
  setSpinner('run-full-spinner', true);
  setDisabled('run-full-tests-btn', true);

  // Show loading placeholder
  const container = $('test-runs-container');
  container.innerHTML = `
    <div class="test-run-card">
      <div class="test-run-header">
        <span class="test-run-label">Running tests…</span>
      </div>
      <div class="test-output">Please wait…</div>
    </div>`;

  try {
    const data = await apiFetch('/api/run-tests', {
      session_id: state.sessionId,
      scope: 'full',
    });
    renderTestRuns(data);
    const overall = data.overall_passed;
    showToast(
      overall ? '✅ All tests passed!' : '❌ Some tests failed.',
      overall ? 'success' : 'error'
    );
  } catch (err) {
    container.innerHTML = `<div class="alert alert-error" style="margin-top:16px">Error: ${escapeHtml(err.message)}</div>`;
    showToast('Test run failed: ' + err.message, 'error');
  } finally {
    setSpinner('run-full-spinner', false);
    setDisabled('run-full-tests-btn', false);
  }
}

async function runTargetedTests(findingId) {
  if (!state.sessionId) return;
  navTo('tests');
  setSpinner('run-full-spinner', true);
  setDisabled('run-full-tests-btn', true);

  const container = $('test-runs-container');
  container.innerHTML = `
    <div class="test-run-card">
      <div class="test-run-header">
        <span class="test-run-label">Running targeted tests…</span>
      </div>
      <div class="test-output">Please wait…</div>
    </div>`;

  try {
    const data = await apiFetch('/api/run-tests', {
      session_id: state.sessionId,
      scope: 'targeted',
      finding_id: findingId,
    });
    renderTestRuns(data);
    showToast(
      data.overall_passed ? '✅ Tests passed!' : '❌ Tests failed.',
      data.overall_passed ? 'success' : 'error'
    );
  } catch (err) {
    container.innerHTML = `<div class="alert alert-error" style="margin-top:16px">Error: ${escapeHtml(err.message)}</div>`;
    showToast('Error: ' + err.message, 'error');
  } finally {
    setSpinner('run-full-spinner', false);
    setDisabled('run-full-tests-btn', false);
  }
}

function renderTestRuns(data) {
  const container = $('test-runs-container');

  if (data.error && !data.runs) {
    container.innerHTML = `<div class="alert alert-error" style="margin-top:16px">⚠ ${escapeHtml(data.error)}</div>`;
    return;
  }

  if (!data.runs || !data.runs.length) {
    container.innerHTML = `
      <div class="card" style="margin-top:16px">
        <div class="empty-state">
          <div class="empty-state-icon">🧪</div>
          ${data.error || 'No tests were executed.'}
        </div>
      </div>`;
    return;
  }

  container.innerHTML = data.runs.map((run, i) => {
    const c = run.counts || {};
    const passed = run.passed;
    const exitCode = run.exit_code;
    const output = (run.stdout || '') + (run.stderr ? '\n--- stderr ---\n' + run.stderr : '');
    const uid = `run-output-${i}`;

    return `
      <div class="test-run-card">
        <div class="test-run-header">
          <span class="test-run-label">${escapeHtml(run.label || run.test_file || 'Test Run')}</span>
          <span class="${passed ? 'test-pass-badge' : 'test-fail-badge'}">
            ${passed ? '✅ PASSED' : '❌ FAILED'}
          </span>
          <span class="duration-label">${run.duration}s</span>
          <span class="duration-label">exit ${exitCode}</span>
          <span class="duration-label">${run.framework || ''}</span>
        </div>
        <div class="test-run-cmd">$ ${escapeHtml(run.command || '')}</div>
        <div class="test-counts">
          <div class="count-item">
            <div class="count-dot count-passed"></div> ${c.passed || 0} passed
          </div>
          <div class="count-item">
            <div class="count-dot count-failed"></div> ${c.failed || 0} failed
          </div>
          <div class="count-item">
            <div class="count-dot count-error"></div> ${c.error || 0} errors
          </div>
          <div class="count-item">
            <div class="count-dot count-skipped"></div> ${c.skipped || 0} skipped
          </div>
        </div>
        <div class="output-toggle" onclick="toggleOutput('${uid}')">
          ▶ Toggle Output
        </div>
        <div class="test-output" id="${uid}" style="display:none">${escapeHtml(output.trim() || '(no output)')}</div>
      </div>
    `;
  }).join('');
}

function toggleOutput(uid) {
  const el = $(uid);
  if (el) el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

// ─── Section 6: Report ────────────────────────────────────────────────────────
$('generate-report-btn').addEventListener('click', async () => {
  if (!state.sessionId) return showToast('Load a project first', 'error');
  setSpinner('report-spinner', true);
  setDisabled('generate-report-btn', true);

  try {
    const data = await apiFetch('/api/report', { session_id: state.sessionId });
    renderReport(data);
    $('report-container').style.display = 'block';
    $('report-timestamp').textContent = 'Generated at ' + new Date(data.generated_at).toLocaleString();
  } catch (err) {
    showToast('Report generation failed: ' + err.message, 'error');
  } finally {
    setSpinner('report-spinner', false);
    setDisabled('generate-report-btn', false);
  }
});

function renderReport(data) {
  const s = data.summary;

  // Stats row
  const statusColor = (s.tests_failed + s.tests_error) === 0 && s.test_runs_executed > 0
    ? 'var(--success)' : s.test_runs_executed === 0 ? 'var(--text-muted)' : 'var(--danger)';

  $('report-stats').innerHTML = `
    <div class="stat-card">
      <div class="stat-value">${s.files_analyzed}</div>
      <div class="stat-label">Files Analyzed</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">${s.total_findings}</div>
      <div class="stat-label">Issues Found</div>
    </div>
    <div class="stat-card">
      <div class="stat-value" style="color:var(--success)">${s.fixed}</div>
      <div class="stat-label">Fixed</div>
    </div>
    <div class="stat-card">
      <div class="stat-value" style="color:var(--warning)">${s.unresolved}</div>
      <div class="stat-label">Unresolved</div>
    </div>
    <div class="stat-card">
      <div class="stat-value" style="color:${statusColor}">${s.tests_passed}</div>
      <div class="stat-label">Tests Passed</div>
    </div>
    <div class="stat-card">
      <div class="stat-value" style="color:var(--danger)">${s.tests_failed + s.tests_error}</div>
      <div class="stat-label">Tests Failed</div>
    </div>
  `;

  // Fixed issues
  $('report-fixed').innerHTML = data.fixed_issues.length
    ? data.fixed_issues.map(f => `
        <div class="report-finding-item">
          <span class="report-icon">✅</span>
          <div>
            <div class="report-issue-title">${escapeHtml(f.title)}</div>
            <div class="report-issue-meta">${escapeHtml(f.file)} · ${f.severity}</div>
            <div class="report-issue-text">${escapeHtml(f.fix)}</div>
          </div>
        </div>`).join('')
    : '<div class="empty-state">No issues were fixed in this session.</div>';

  // Unresolved issues
  $('report-unresolved').innerHTML = data.unresolved_issues.length
    ? data.unresolved_issues.map(f => `
        <div class="report-finding-item">
          <span class="report-icon">⚠</span>
          <div>
            <div class="report-issue-title">${escapeHtml(f.title)}</div>
            <div class="report-issue-meta">${escapeHtml(f.file)} · ${f.severity} · ${f.confidence}</div>
            <div class="report-issue-text">${escapeHtml(f.reason)}</div>
          </div>
        </div>`).join('')
    : '<div class="empty-state" style="color:var(--success)">✅ All detected issues have been addressed.</div>';

  // Test runs
  $('report-test-runs').innerHTML = data.test_runs.length
    ? data.test_runs.map(r => `
        <div class="report-finding-item">
          <span class="report-icon">${r.passed ? '✅' : '❌'}</span>
          <div>
            <div class="report-issue-title">${escapeHtml(r.label)}</div>
            <div class="report-issue-meta">
              <code>${escapeHtml(r.command)}</code> ·
              exit ${r.exit_code} · ${r.duration}s
            </div>
            <div class="report-issue-text">
              Passed: ${r.counts.passed} · Failed: ${r.counts.failed} · Errors: ${r.counts.error}
            </div>
          </div>
        </div>`).join('')
    : '<div class="empty-state">No tests were executed.</div>';

  // Uncertainties
  $('report-uncertainties').innerHTML = data.uncertainties.map(u =>
    `<li>${escapeHtml(u)}</li>`
  ).join('');

  $('report-disclaimer').textContent = data.disclaimer;
}
