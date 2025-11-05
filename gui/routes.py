"""
Flask routes for the WP Multi-Updater GUI.

Handles all HTTP endpoints for the web interface.
"""

from flask import render_template, request, jsonify, current_app, redirect, url_for, flash
from gui.site_manager import SiteManager
import os


def init_routes(app):
    """Initialize all routes for the application."""

    @app.route('/')
    def index():
        """Dashboard home page."""
        manager = SiteManager(app.config['SITES_YAML'])
        sites = manager.load_sites()

        return render_template('index.html',
                               total_sites=len(sites),
                               total_servers=len(set(s.get('host') for s in sites)))

    @app.route('/sites')
    def sites_list():
        """List all sites, grouped by server."""
        manager = SiteManager(app.config['SITES_YAML'])
        sites_by_server = manager.get_sites_by_server()

        return render_template('sites.html', sites_by_server=sites_by_server)

    @app.route('/sites/add', methods=['GET', 'POST'])
    def site_add():
        """Add a new site."""
        if request.method == 'POST':
            # Get form data
            site_data = {
                'name': request.form.get('name', '').strip(),
                'host': request.form.get('host', '').strip(),
                'user': request.form.get('user', '').strip(),
                'path': request.form.get('path', '').strip(),
                'url': request.form.get('url', '').strip(),
                'wp_cli': request.form.get('wp_cli', 'wp').strip(),
            }

            # Add site
            manager = SiteManager(app.config['SITES_YAML'])
            success, message = manager.add_site(site_data)

            if success:
                flash(message, 'success')
                return redirect(url_for('sites_list'))
            else:
                flash(message, 'error')

        return render_template('site_form.html', mode='add', site={})

    @app.route('/sites/<site_name>/edit', methods=['GET', 'POST'])
    def site_edit(site_name):
        """Edit an existing site."""
        manager = SiteManager(app.config['SITES_YAML'])

        if request.method == 'POST':
            # Get form data
            site_data = {
                'name': request.form.get('name', '').strip(),
                'host': request.form.get('host', '').strip(),
                'user': request.form.get('user', '').strip(),
                'path': request.form.get('path', '').strip(),
                'url': request.form.get('url', '').strip(),
                'wp_cli': request.form.get('wp_cli', 'wp').strip(),
            }

            # Update site
            success, message = manager.update_site(site_name, site_data)

            if success:
                flash(message, 'success')
                return redirect(url_for('sites_list'))
            else:
                flash(message, 'error')

        # Load site for editing
        site = manager.get_site_by_name(site_name)
        if not site:
            flash(f"Site '{site_name}' not found", 'error')
            return redirect(url_for('sites_list'))

        return render_template('site_form.html', mode='edit', site=site, original_name=site_name)

    @app.route('/sites/<site_name>/delete', methods=['POST'])
    def site_delete(site_name):
        """Delete a site."""
        manager = SiteManager(app.config['SITES_YAML'])
        success, message = manager.delete_site(site_name)

        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')

        return redirect(url_for('sites_list'))

    @app.route('/api/sites/<site_name>/test', methods=['POST'])
    def site_test_ssh(site_name):
        """Test SSH connection to a site (API endpoint)."""
        manager = SiteManager(app.config['SITES_YAML'])
        site = manager.get_site_by_name(site_name)

        if not site:
            return jsonify({'success': False, 'message': f"Site '{site_name}' not found"}), 404

        # Get SSH key from request or use default
        ssh_key = request.json.get('ssh_key') if request.json else None
        if not ssh_key:
            ssh_key = app.config['SSH_KEY_DEFAULT']

        # Test connection
        success, message = manager.test_ssh_connection(site, ssh_key)

        return jsonify({'success': success, 'message': message})

    @app.route('/update')
    def update_interface():
        """Plugin update interface."""
        manager = SiteManager(app.config['SITES_YAML'])
        sites = manager.load_sites()

        return render_template('update.html', sites=sites)

    @app.route('/history')
    def history_list():
        """Update history from SQLite database."""
        # TODO: Implement history view
        return render_template('history.html')
