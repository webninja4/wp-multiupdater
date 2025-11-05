# WP Multi-Updater GUI

A web-based interface for managing WordPress plugin updates across multiple sites.

## Status

**Sprint 1 Complete:** Basic site management functionality is implemented and ready to test.

### Implemented Features (Sprint 1)

- ✅ Flask application with Bootstrap 5 UI
- ✅ Dashboard with system statistics
- ✅ Site management (list, add, edit, delete)
- ✅ Sites grouped by server IP address
- ✅ SSH connection testing
- ✅ Search/filter sites
- ✅ Form validation
- ✅ YAML inventory integration

### Coming Soon (Sprint 2-4)

- ⏳ Plugin update interface
- ⏳ Real-time progress updates via SocketIO
- ⏳ Update history view
- ⏳ CSV/Markdown report downloads

## Quick Start

### 1. Install Dependencies

The GUI dependencies are already included in requirements.txt:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Start the Server

```bash
python app.py
```

The server will start at http://localhost:5000

### 3. Access the GUI

Open your browser and navigate to:
- Dashboard: http://localhost:5000/
- Manage Sites: http://localhost:5000/sites
- Add Site: http://localhost:5000/sites/add

## Features

### Dashboard

- Quick statistics (total sites, servers)
- Quick action cards for common tasks
- System status indicators

### Site Management

**List Sites:**
- Sites grouped by Cloudways server
- Search and filter functionality
- Quick actions: Test SSH, Edit, Delete

**Add/Edit Site:**
- Form validation
- SSH connection testing
- Helper documentation

**Test SSH Connection:**
- One-click SSH connectivity test
- Displays WordPress version on success
- Toast notifications for results

### Navigation

- Responsive Bootstrap navbar
- Flash messages for user feedback
- Mobile-friendly design

## Architecture

```
wp-multi-updater/
├── app.py                          # Flask application entry point
├── gui/
│   ├── __init__.py                 # Package initialization
│   ├── routes.py                   # HTTP routes
│   ├── site_manager.py             # Site CRUD operations
│   ├── templates/
│   │   ├── base.html               # Base template
│   │   ├── index.html              # Dashboard
│   │   ├── sites.html              # Site list
│   │   ├── site_form.html          # Add/edit form
│   │   ├── update.html             # Update interface (placeholder)
│   │   └── history.html            # History view (placeholder)
│   └── static/
│       ├── css/
│       │   └── style.css           # Custom styles
│       └── js/
│           └── sites.js            # Site management JS
└── GUI-README.md                   # This file
```

## Configuration

Configuration is set in `app.py`:

```python
app.config['SITES_YAML'] = 'inventory/sites.yaml'
app.config['JOBS_DIR'] = 'jobs/'
app.config['REPORTS_DIR'] = 'reports/'
app.config['DB_PATH'] = 'state/results.sqlite'
app.config['SSH_KEY_DEFAULT'] = '~/.ssh/id_rsa_cloudways'
```

## API Endpoints

### HTTP Routes

- `GET /` - Dashboard
- `GET /sites` - List all sites
- `GET /sites/add` - Add site form
- `POST /sites/add` - Create new site
- `GET /sites/<name>/edit` - Edit site form
- `POST /sites/<name>/edit` - Update site
- `POST /sites/<name>/delete` - Delete site
- `GET /update` - Update interface (coming soon)
- `GET /history` - Update history (coming soon)

### API Routes

- `POST /api/sites/<name>/test` - Test SSH connection

## Development

### Running in Development Mode

```bash
python app.py
```

The app runs with:
- Debug mode enabled
- Auto-reload on code changes
- Detailed error pages
- Accessible on all interfaces (0.0.0.0:5000)

### Testing SSH Connections

The GUI uses the same SSH key as the CLI (`~/.ssh/id_rsa_cloudways` by default).

Test command format:
```bash
ssh -i ~/.ssh/id_rsa_cloudways \
  -o ConnectTimeout=10 \
  user@host \
  "cd /path && wp core version"
```

## Security Notes

### For Local Development

- Default SECRET_KEY is `dev-secret-key-change-in-production`
- Server listens on 0.0.0.0 (all interfaces)
- Debug mode is enabled
- No authentication required

### For Production Deployment

Before deploying to production:

1. **Set a secure SECRET_KEY:**
   ```bash
   export SECRET_KEY='your-random-secret-key-here'
   ```

2. **Disable debug mode** (edit app.py):
   ```python
   socketio.run(app, debug=False, ...)
   ```

3. **Use a production server:**
   - Deploy with gunicorn + nginx
   - Or use Docker container
   - See GUI-PLAN.md for deployment options

4. **Add authentication:**
   - Implement Flask-Login or basic auth
   - Restrict to internal network only

## Troubleshooting

### Port 5000 Already in Use

**macOS Issue:** AirPlay Receiver uses port 5000 by default.

**Solution 1:** Disable AirPlay Receiver
- System Preferences → General → AirDrop & Handoff → Uncheck "AirPlay Receiver"

**Solution 2:** Use a different port (edit app.py):
```python
socketio.run(app, debug=True, allow_unsafe_werkzeug=True, host='0.0.0.0', port=8080)
```

### SSH Connection Test Fails

1. **Check SSH key permissions:**
   ```bash
   chmod 600 ~/.ssh/id_rsa_cloudways
   ```

2. **Test manually:**
   ```bash
   ssh -i ~/.ssh/id_rsa_cloudways user@host "wp core version"
   ```

3. **Verify site details:**
   - Host (IP address)
   - User (SSH username)
   - Path (application path)

### Flask Dependencies Not Found

```bash
source venv/bin/activate
pip install -r requirements.txt
```

## Next Steps

### Immediate Tasks (Sprint 2)

1. Implement plugin update interface
2. Add file upload for plugin ZIPs
3. Site selection with checkboxes
4. Integration with orchestrator.py

### Future Enhancements

- Real-time progress updates (Sprint 3)
- Update history from SQLite database (Sprint 4)
- Email/Slack notifications
- Scheduled updates
- User authentication

## Resources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [Bootstrap 5 Documentation](https://getbootstrap.com/docs/5.3/)
- [Flask-SocketIO Documentation](https://flask-socketio.readthedocs.io/)
- [GUI-PLAN.md](GUI-PLAN.md) - Complete implementation plan

## Support

For issues or questions about the GUI, refer to:
- [GUI-PLAN.md](GUI-PLAN.md) - Detailed architecture
- [README.md](README.md) - CLI documentation
- [SESSION-NOTES.md](SESSION-NOTES.md) - Development notes
