#!/usr/bin/env python3
"""
Flask application entry point for WP Multi-Updater GUI.

This provides a web-based interface for managing WordPress plugin updates
across multiple sites.
"""

from flask import Flask, render_template
from flask_socketio import SocketIO
import os

# Initialize Flask app
app = Flask(__name__, template_folder='gui/templates', static_folder='gui/static')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SITES_YAML'] = 'inventory/sites.yaml'
app.config['JOBS_DIR'] = 'jobs/'
app.config['REPORTS_DIR'] = 'reports/'
app.config['DB_PATH'] = 'state/results.sqlite'
app.config['SSH_KEY_DEFAULT'] = '~/.ssh/id_rsa_cloudways'

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Import routes module to register all routes
from gui.routes import init_routes
init_routes(app)

if __name__ == '__main__':
    print("\n" + "="*60)
    print("WP Multi-Updater GUI")
    print("="*60)
    print(f"Starting server at http://localhost:5000")
    print("Press CTRL+C to stop")
    print("="*60 + "\n")

    socketio.run(app, debug=True, allow_unsafe_werkzeug=True, host='0.0.0.0', port=5000)
