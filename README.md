# ProjectA WP Multi-Updater

A production-grade command-line tool for safely updating premium WordPress plugins across multiple sites via SSH and WP-CLI.

**Status:** ⚠️ **Active Development** - Core functionality working, Cloudways-specific fixes in progress.

## Features

- **Safe Updates**: Automatic database backups before each plugin update
- **Maintenance Mode**: Automatic cleanup on exit (even on failures)
- **Verification**: Pre/post version tracking and HTTP health checks
- **Concurrency**: Update multiple sites in parallel (default: 10 workers)
- **Retry Logic**: Re-run failed tasks without repeating successful ones
- **Detailed Reports**: SQLite database, CSV, and Markdown summaries
- **CI/CD Ready**: Exit codes and structured output for automation

## Quick Start

### Prerequisites

- Python 3.10 or higher
- SSH key access to target WordPress sites
- WP-CLI installed on all target sites
- Local `ssh`, `scp` commands available

### Installation

```bash
# Clone or navigate to the project
cd wp-multi-updater

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment (optional)
cp .env.sample .env
```

### Cloudways Users

If you're using Cloudways hosting, see [CLOUDWAYS_SETUP.md](CLOUDWAYS_SETUP.md) for specific configuration instructions and API integration.

### Basic Usage

1. **Configure your sites** in [inventory/sites.yaml](inventory/sites.yaml):

```yaml
- name: mysite-prod
  host: ssh.example.com
  user: appuser
  path: /home/app/public_html
  url: https://www.example.com
  wp_cli: wp
```

2. **Create a plugin update job** in [jobs/plugins.csv](jobs/plugins.csv):

```csv
plugin_slug,zip_source,type,activate
the-events-calendar-pro,https://signed-url/plugin.zip,url,false
document-library-pro,/path/to/local/plugin.zip,file,false
```

3. **Run the updater**:

```bash
# Dry run first (recommended)
python orchestrator.py --sites inventory/sites.yaml --plugins jobs/plugins.csv --dry-run

# Execute updates
python orchestrator.py --sites inventory/sites.yaml --plugins jobs/plugins.csv

# With concurrency control
python orchestrator.py --sites inventory/sites.yaml --plugins jobs/plugins.csv --concurrency 5
```

### Advanced Usage

```bash
# Update specific sites only
python orchestrator.py --sites inventory/sites.yaml --plugins jobs/plugins.csv \
  --only-sites mysite-prod,othersite-staging

# Update specific plugins only
python orchestrator.py --sites inventory/sites.yaml --plugins jobs/plugins.csv \
  --only-plugins the-events-calendar-pro

# Retry only failed tasks from previous run
python orchestrator.py --sites inventory/sites.yaml --plugins jobs/plugins.csv --retry-failed

# Custom SSH options
python orchestrator.py --sites inventory/sites.yaml --plugins jobs/plugins.csv \
  --ssh-opts "-o ConnectTimeout=30 -o ServerAliveInterval=60"

# Custom timeout per task (default: 900 seconds)
python orchestrator.py --sites inventory/sites.yaml --plugins jobs/plugins.csv --timeout-sec 1200
```

## Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--sites` | Path to sites YAML inventory | Required |
| `--plugins` | Path to plugins CSV job file | Required |
| `--concurrency` | Number of parallel workers | 10 |
| `--dry-run` | Print plan without executing | False |
| `--retry-failed` | Only retry failed tasks from last run | False |
| `--only-sites` | Comma-separated site names to target | All sites |
| `--only-plugins` | Comma-separated plugin slugs to update | All plugins |
| `--timeout-sec` | Timeout per task in seconds | 900 |
| `--report-dir` | Directory for output reports | reports |
| `--ssh-opts` | Additional SSH options | "" |

## Safety Features

### Automatic Database Backups

Every plugin update triggers a database export before making changes:

```
./backups/pre-update-20250104-153045-plugin-slug.sql
```

Backups are stored on the remote site for manual rollback if needed.

### Maintenance Mode Guard

The remote script ensures maintenance mode is always cleared, even if the update fails:

- Checks and clears maintenance mode before starting
- Uses bash `trap` to guarantee cleanup on exit
- Prevents site lockout from stuck maintenance pages

### Idempotent Execution

You can safely re-run the same command multiple times:

- Existing backups are preserved
- Version checks prevent unnecessary work
- `--force` flag ensures plugin install is reproducible

## Reports and Observability

After each run, three artifacts are generated:

1. **SQLite Database** (`state/results.sqlite`):
   - Complete task history with timestamps
   - Searchable by run, site, plugin, status
   - Useful for analytics and trending

2. **CSV Report** (`reports/run-<timestamp>.csv`):
   - Spreadsheet-friendly format
   - Columns: site, plugin, status, versions, duration, errors

3. **Markdown Summary** (`reports/run-<timestamp>.md`):
   - Human-readable overview
   - Summary statistics (OK / Needs Attention / Failed)
   - Quick scan of any problems

## Status Codes

Tasks are marked with one of three status values:

- **`ok`**: Plugin updated successfully, HTTP check passed
- **`needs_attention`**: Plugin updated but HTTP check returned non-200 or maintenance mode not cleared
- **`failed`**: Update failed (SSH error, WP-CLI error, etc.)

## Exit Codes

- **0**: All tasks completed with `ok` status
- **1**: One or more tasks have `needs_attention` or `failed` status

Perfect for CI/CD pipelines:

```bash
python orchestrator.py --sites inventory/sites.yaml --plugins jobs/plugins.csv || \
  { echo "Updates failed!"; exit 1; }
```

## Rollback Procedure

If an update causes issues:

1. **Locate the backup** on the remote site:
   ```bash
   ssh user@host
   cd /home/app/public_html
   ls -lh backups/pre-update-*
   ```

2. **Restore the database**:
   ```bash
   wp db import backups/pre-update-20250104-153045-plugin-slug.sql
   ```

3. **Reinstall the previous plugin version** (if you have the ZIP):
   ```bash
   wp plugin install /path/to/old-plugin.zip --force
   wp plugin activate plugin-slug  # if it was active before
   ```

4. **Verify site health**:
   ```bash
   wp plugin list
   curl -I https://www.example.com
   ```

## Security Considerations

### SSH Keys Only

The tool uses SSH key-based authentication. Never commit private keys or passwords to the repository.

### URL Redaction

URLs with query strings (e.g., signed S3 URLs) are redacted in logs:

```
https://example.com/plugin.zip?token=SECRET
  becomes
https://example.com/plugin.zip?[REDACTED]
```

### Environment Variables

Store sensitive tokens in `.env` (gitignored):

```bash
# .env
SLACK_WEBHOOK=https://hooks.slack.com/services/YOUR/SECRET/TOKEN
```

## Troubleshooting

### SSH Connection Fails

```
Error: SSH_CONNECT_FAIL
```

**Solution**: Verify SSH key access:
```bash
ssh -T user@host
```

### WP-CLI Not Found

```
Error: WP_NOT_INSTALLED
```

**Solution**: Check `wp_cli` path in [inventory/sites.yaml](inventory/sites.yaml). Some hosts use `/usr/local/bin/wp` or custom paths.

### Timeout Errors

```
Error: Task exceeded timeout (900s)
```

**Solution**: Increase timeout for large sites:
```bash
python orchestrator.py ... --timeout-sec 1800
```

### Maintenance Mode Stuck

The script automatically clears maintenance mode. If it's still stuck:

```bash
ssh user@host
cd /home/app/public_html
wp maintenance-mode deactivate
rm -f .maintenance  # force removal if needed
```

### Cloudways SCP Issues

**Known Issue:** Direct SCP to `/tmp/plugin.zip` fails on Cloudways servers.

**Temporary Workaround:**
Use manual file upload or wait for fix in next release.

**Permanent Fix (In Progress):**
- Orchestrator will upload to `~/plugin.zip` instead
- See [SESSION-NOTES.md](SESSION-NOTES.md) for details

### Cloudways Chmod Warnings

**Expected Behavior:** WP-CLI shows ~100 chmod warnings during plugin install on Cloudways.

**Impact:** Cosmetic only - plugin installs successfully.

**Why:** Cloudways file ownership model (SSH user ≠ file owner).

**Fix:** Warnings will be suppressed in next release.

## Project Structure

```
wp-multi-updater/
├── orchestrator.py              # Main CLI tool
├── scripts/
│   └── remote-update.sh         # Remote execution script
├── inventory/
│   └── sites.yaml               # Site definitions
├── jobs/
│   ├── plugins.csv              # Plugin update jobs
│   └── example.csv              # Sample job file
├── reports/                     # Generated reports (CSV + MD)
├── state/
│   └── results.sqlite           # Task history database
├── requirements.txt             # Python dependencies
├── .env.sample                  # Environment template
└── README.md                    # This file
```

## Development

### Running Tests

```bash
# Unit tests (when available)
python -m pytest tests/

# Test on staging sites first
python orchestrator.py --sites inventory/sites-staging.yaml --plugins jobs/test.csv
```

### Adding a New Site

Edit [inventory/sites.yaml](inventory/sites.yaml):

```yaml
- name: newsite-prod
  host: ssh.newsite.com
  user: appuser
  path: /var/www/wordpress
  url: https://www.newsite.com
  wp_cli: /usr/local/bin/wp  # custom path if needed
```

### Extending the Remote Script

The [scripts/remote-update.sh](scripts/remote-update.sh) script can be customized:

- Add pre-flight checks
- Modify backup retention
- Add custom health checks
- Emit additional MARKER data

The orchestrator parses lines starting with `MARKER ` for structured data extraction.

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Update Plugins
on:
  workflow_dispatch:

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: |
          python orchestrator.py \
            --sites inventory/sites.yaml \
            --plugins jobs/monthly-updates.csv
      - uses: actions/upload-artifact@v3
        if: always()
        with:
          name: reports
          path: reports/
```

## License

Internal tool for ProjectA. All rights reserved.

## Support

For issues or questions, contact the DevOps team or open an issue in the internal repository.
