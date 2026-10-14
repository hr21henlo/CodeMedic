"""
CodeMedic: Software Delivery Agent
Main Flask application
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, request, jsonify, send_from_directory
from backend.upload_handler import handle_upload
from backend.analyzer import analyze_project
from backend.patcher import get_patch, apply_patch
from backend.test_runner import run_tests
from backend.reporter import generate_report
from backend.demo_loader import load_demo_project

app = Flask(__name__, static_folder='frontend/static', template_folder='frontend/templates')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload

# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload():
    """Upload a ZIP file and extract it to a temp directory."""
    try:
        result = handle_upload(request)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/demo', methods=['POST'])
def demo():
    """Load the built-in demo project."""
    try:
        result = load_demo_project()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """Run bug investigation on a loaded project."""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        if not session_id:
            return jsonify({'error': 'session_id required'}), 400
        result = analyze_project(session_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/patch', methods=['POST'])
def patch():
    """Get or apply a patch for a finding."""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        finding_id = data.get('finding_id')
        action = data.get('action', 'preview')  # 'preview' or 'apply'
        if action == 'apply':
            result = apply_patch(session_id, finding_id)
        else:
            result = get_patch(session_id, finding_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/run-tests', methods=['POST'])
def run_tests_route():
    """Execute the test suite for the loaded project."""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        scope = data.get('scope', 'full')  # 'targeted' or 'full'
        finding_id = data.get('finding_id')
        result = run_tests(session_id, scope=scope, finding_id=finding_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/report', methods=['POST'])
def report():
    """Generate the final investigation report."""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        result = generate_report(session_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("  CodeMedic: Software Delivery Agent")
    print("  http://127.0.0.1:5000")
    print("=" * 60)
    app.run(debug=True, port=5000)
