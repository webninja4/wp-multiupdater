# GUI Application Plan - WP Multi-Updater

## Overview

A web-based GUI for managing WordPress plugin updates across multiple sites. The GUI will provide an intuitive interface for adding sites to inventory and executing plugin updates with real-time progress tracking.

## Technology Stack

### Backend
- **Flask** - Lightweight Python web framework
- **Flask-SocketIO** - Real-time bidirectional communication for progress updates
- **Existing orchestrator.py** - Core update logic (no changes needed)

### Frontend
- **HTML5 + CSS3** - Structure and styling
- **JavaScript (Vanilla or Vue.js)** - Interactive UI
- **Socket.IO Client** - Real-time progress updates
- **Bootstrap 5** - Responsive UI components

### Why These Choices?
- Flask integrates seamlessly with existing Python codebase
- SocketIO enables real-time progress without polling
- No heavy frameworks needed (keeps it simple)
- Can run locally or deploy to internal server

## Features

### Phase 1: Core Functionality

#### 1. Site Management
- **View Sites**
  - List all sites from inventory/sites.yaml
  - Grouped by server (IP address)
  - Show: name, host, URL, path
  - Search/filter sites

- **Add New Site**
  - Form with fields: name, host, user, path, url, wp_cli
  - Validation: Test SSH connection before saving
  - Auto-detect wp_cli path if possible
  - Append to inventory/sites.yaml
  - Organize by server IP automatically

- **Edit Site**
  - Modify existing site details
  - Re-validate SSH connection
  - Update YAML file

- **Delete Site**
  - Remove from inventory with confirmation

#### 2. Plugin Update Interface
- **Select Sites**
  - Checkbox selection (single or multiple)
  - Select all sites on a server
  - Filter by client/project

- **Plugin Configuration**
  - Upload plugin ZIP OR provide URL
  - Enter plugin slug (auto-detect from ZIP if possible)
  - Choose: activate or keep deactivated
  - Option to use multiple plugins (CSV-like interface)

- **Update Options**
  - Concurrency/parallelism slider (1-10)
  - Enable cache clearing (checkbox - recommended)
  - SSH options (optional)
  - Timeout setting

- **Execute Updates**
  - "Start Update" button
  - Confirmation dialog showing what will be updated

#### 3. Real-Time Progress Display
- **Progress Dashboard**
  - Overall progress bar (X/Y sites completed)
  - Per-site status cards:
    - Site name and URL
    - Current status: pending, in_progress, completed
    - Plugin being updated
    - Live logs (truncated)
    - Result: success ✅, needs_attention ⚠️, failed ❌
  
- **Live Console Output**
  - Scrolling console showing orchestrator output
  - Color-coded: info (blue), success (green), warning (yellow), error (red)
  - Auto-scroll with option to pause

#### 4. Results and Reporting
- **Summary View**
  - Total sites updated
  - Success count
  - Needs attention count
  - Failed count

- **Detailed Results**
  - Per-site results table
  - Download CSV report
  - Download Markdown summary
  - Link to view full logs

- **History**
  - List recent update runs
  - View past results from SQLite database

### Phase 2: Enhanced Features (Future)

- **Scheduling**: Schedule updates for specific times
- **Notifications**: Email/Slack on completion
- **Rollback**: One-click rollback interface
- **Dashboard**: Analytics and trending
- **User Authentication**: Multi-user access with permissions

## Architecture

### Application Structure

```
wp-multi-updater/
├── app.py                       # Flask application entry point
├── gui/
│   ├── __init__.py
│   ├── routes.py                # Web routes
│   ├── socketio_events.py       # SocketIO event handlers
│   ├── site_manager.py          # Site CRUD operations
│   ├── update_runner.py         # Orchestrator wrapper
│   └── templates/
│       ├── base.html            # Base template
│       ├── index.html           # Dashboard/home
│       ├── sites.html           # Site management
│       ├── update.html          # Update interface
│       └── history.html         # Update history
│   └── static/
│       ├── css/
│       │   └── style.css
│       ├── js/
│       │   ├── sites.js         # Site management logic
│       │   ├── update.js        # Update interface logic
│       │   └── progress.js      # Real-time progress updates
│       └── images/
├── orchestrator.py              # Existing (no changes)
├── scripts/
│   └── update-with-cache-clear.py  # Existing
└── ...
```

### Data Flow

```
User Browser
    ↓ HTTP
Flask Routes (routes.py)
    ↓
Site Manager / Update Runner
    ↓
orchestrator.py / update-with-cache-clear.py
    ↓ stdout/stderr
SocketIO Events (socketio_events.py)
    ↓ WebSocket
User Browser (Real-time updates)
```

## UI Mockup (Text Description)

### Dashboard (index.html)
```
+--------------------------------------------------+
|  WP Multi-Updater                    [Settings]  |
+--------------------------------------------------+
|                                                  |
|  Quick Actions:                                  |
|  [Manage Sites]  [Update Plugins]  [View History]
|                                                  |
|  Recent Updates:                                 |
|  +--------------------------------------------+  |
|  | 2025-01-05 14:32 | 3 sites | ✅ Success    |  |
|  | 2025-01-05 12:15 | 5 sites | ⚠️  Attention |  |
|  +--------------------------------------------+  |
|                                                  |
|  System Status:                                  |
|  • 35 sites in inventory                         |
|  • 15 Cloudways servers                          |
|  • SSH: Connected ✅                             |
+--------------------------------------------------+
```

### Site Management (sites.html)
```
+--------------------------------------------------+
|  Manage Sites                      [+ Add Site]  |
+--------------------------------------------------+
| Search: [_______________]    Group by: [Server▼] |
+--------------------------------------------------+
|                                                  |
| 📦 Server 1: 104.207.159.106 (4 sites)          |
|   ├─ craterian-staging    [Edit] [Delete]       |
|   ├─ craterian            [Edit] [Delete]       |
|   ├─ ashland-new-plays    [Edit] [Delete]       |
|   └─ guildedesfromagers   [Edit] [Delete]       |
|                                                  |
| 📦 Server 2: 45.77.210.64 (6 sites)             |
|   ├─ crystalballroom      [Edit] [Delete]       |
|   └─ ...                                         |
+--------------------------------------------------+
```

### Update Interface (update.html)
```
+--------------------------------------------------+
|  Update Plugins                                  |
+--------------------------------------------------+
| Step 1: Select Sites                             |
| +----------------------------------------------+ |
| | [x] craterian-staging                        | |
| | [x] travelashland-staging                    | |
| | [ ] 1000museums-staging                      | |
| | ...                                          | |
| +----------------------------------------------+ |
|                                                  |
| Step 2: Plugin Configuration                     |
| Plugin Slug: [events-calendar-pro________]       |
| Source:  (•) URL  ( ) Upload File               |
| URL: [https://...____________________]           |
| [x] Activate after install                       |
| [+ Add Another Plugin]                           |
|                                                  |
| Step 3: Options                                  |
| [x] Clear cache before/after (recommended)       |
| Max Parallel: [====|====] 3                      |
| SSH Key: [~/.ssh/id_rsa_cloudways____]           |
|                                                  |
| [Cancel]              [Start Update →]           |
+--------------------------------------------------+
```

### Progress View (update.html - after starting)
```
+--------------------------------------------------+
|  Update in Progress...                 [Pause]  |
+--------------------------------------------------+
| Overall: ████████░░░░░░░░ 2/3 sites (67%)       |
|                                                  |
| +----------------------------------------------+ |
| | ✅ craterian-staging                         | |
| |    3/3 plugins updated | Duration: 42s       | |
| +----------------------------------------------+ |
| | 🔄 travelashland-staging (in progress)       | |
| |    Installing events-calendar-pro...         | |
| |    Clearing cache...                         | |
| +----------------------------------------------+ |
| | ⏳ 1000museums-staging (pending)             | |
| +----------------------------------------------+ |
|                                                  |
| Console Output:                      [📋 Copy]  |
| +----------------------------------------------+ |
| | [14:32:15] Starting update for 3 sites       | |
| | [14:32:16] craterian-staging: Clearing cache | |
| | [14:32:18] craterian-staging: Installing... | |
| | [14:32:35] craterian-staging: ✅ Success     | |
| | [14:32:36] travelashland-staging: Starting... |
| +----------------------------------------------+ |
|                                                  |
| [View Detailed Report]                           |
+--------------------------------------------------+
```

## Implementation Plan

### Sprint 1: Basic Site Management (2-3 days)
1. Set up Flask application structure
2. Create base templates with Bootstrap
3. Implement site list view (read from YAML)
4. Implement add site form with validation
5. SSH connection testing
6. Save to YAML functionality

### Sprint 2: Update Interface (3-4 days)
1. Site selection UI with checkboxes
2. Plugin configuration form
3. Upload/URL handling for plugins
4. Integration with orchestrator.py
5. Basic progress display (polling-based)

### Sprint 3: Real-Time Progress (2-3 days)
1. Integrate Flask-SocketIO
2. Wrap orchestrator output streaming
3. Emit progress events via WebSocket
4. Update frontend to display live progress
5. Per-site status cards

### Sprint 4: Results and Polish (2-3 days)
1. Results summary page
2. Download CSV/Markdown reports
3. History view from SQLite
4. Error handling and user feedback
5. UI polish and responsive design

**Total Estimated Time:** 9-13 days

## Technical Details

### Flask Routes

```python
# gui/routes.py
@app.route('/')
def index():
    """Dashboard with recent updates"""

@app.route('/sites')
def sites_list():
    """List all sites"""

@app.route('/sites/add', methods=['GET', 'POST'])
def site_add():
    """Add new site form"""

@app.route('/sites/<site_name>/edit', methods=['GET', 'POST'])
def site_edit(site_name):
    """Edit site"""

@app.route('/sites/<site_name>/delete', methods=['POST'])
def site_delete(site_name):
    """Delete site"""

@app.route('/sites/<site_name>/test', methods=['POST'])
def site_test_ssh(site_name):
    """Test SSH connection via AJAX"""

@app.route('/update')
def update_interface():
    """Plugin update interface"""

@app.route('/update/run', methods=['POST'])
def update_run():
    """Start update process"""

@app.route('/history')
def history_list():
    """Update history from SQLite"""

@app.route('/history/<run_id>')
def history_detail(run_id):
    """Detailed results for a run"""
```

### SocketIO Events

```python
# gui/socketio_events.py
@socketio.on('connect')
def handle_connect():
    """Client connected"""

@socketio.on('start_update')
def handle_start_update(data):
    """Start update in background thread"""
    # Run orchestrator in thread
    # Emit progress events

def emit_progress(site, status, message):
    """Emit progress update to all clients"""
    socketio.emit('update_progress', {
        'site': site,
        'status': status,  # pending, in_progress, completed
        'message': message,
        'timestamp': datetime.now().isoformat()
    })

def emit_complete(summary):
    """Emit completion event"""
    socketio.emit('update_complete', summary)
```

### Site Manager

```python
# gui/site_manager.py
class SiteManager:
    def __init__(self, yaml_path='inventory/sites.yaml'):
        self.yaml_path = yaml_path
    
    def load_sites(self):
        """Load sites from YAML"""
    
    def save_sites(self, sites):
        """Save sites to YAML"""
    
    def add_site(self, site_data):
        """Add new site and save"""
    
    def update_site(self, site_name, site_data):
        """Update existing site"""
    
    def delete_site(self, site_name):
        """Remove site from inventory"""
    
    def test_ssh_connection(self, site):
        """Test SSH connectivity"""
        # Run: ssh user@host "wp core version"
    
    def get_sites_by_server(self):
        """Group sites by server IP"""
```

### Update Runner

```python
# gui/update_runner.py
class UpdateRunner:
    def __init__(self, socketio):
        self.socketio = socketio
    
    def run_update(self, sites, plugins, options):
        """
        Run orchestrator/update-with-cache-clear.py
        Stream output via SocketIO
        """
        # Build command
        # Run subprocess with Popen
        # Read stdout/stderr in real-time
        # Emit progress events
        # Return final result
    
    def parse_orchestrator_output(self, line):
        """Parse MARKER lines and status updates"""
```

## Security Considerations

1. **Local Development**: Run on localhost:5000 only
2. **Internal Deployment**: If deployed, restrict to internal network
3. **SSH Keys**: Never expose private keys through the GUI
4. **Input Validation**: Validate all site data before saving to YAML
5. **Command Injection**: Use subprocess.run with list args, never shell=True with user input
6. **File Upload**: Validate plugin ZIPs, scan for malware if accepting uploads
7. **Authentication**: Add basic auth if deployed (Phase 2)

## Configuration

```python
# config.py
class Config:
    SECRET_KEY = 'your-secret-key-here'  # For session management
    SITES_YAML = 'inventory/sites.yaml'
    JOBS_DIR = 'jobs/'
    REPORTS_DIR = 'reports/'
    DB_PATH = 'state/results.sqlite'
    SSH_KEY_DEFAULT = '~/.ssh/id_rsa_cloudways'
    MAX_PARALLEL_DEFAULT = 3
```

## Testing Strategy

1. **Unit Tests**: Site manager, YAML parsing
2. **Integration Tests**: Flask routes, SocketIO events
3. **Manual Testing**: Full workflow with staging sites
4. **Edge Cases**: 
   - Invalid SSH credentials
   - Network timeout during update
   - Plugin ZIP not found
   - YAML syntax errors

## Deployment Options

### Option 1: Local Development (Simplest)
```bash
# Run locally
python app.py
# Open browser to http://localhost:5000
```

### Option 2: Internal Server (Recommended)
- Deploy to internal Ubuntu server
- Use systemd service for auto-start
- Nginx reverse proxy
- Restrict to internal network

### Option 3: Docker Container
- Containerize with Dockerfile
- Mount inventory/ and state/ as volumes
- Easy deployment anywhere

## Next Steps

1. Create `app.py` entry point
2. Set up Flask project structure
3. Implement Sprint 1 features
4. Test with existing sites
5. Iterate based on feedback

---

**Status:** Ready to implement
**Priority:** High - Will significantly improve usability
