# Testing Guide

Comprehensive testing procedures for the WP Multi-Updater tool.

## Pre-Testing Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Verify SSH Access

Test SSH connectivity to your staging sites:

```bash
ssh -T user@staging-host.com
```

### 3. Verify WP-CLI

Check WP-CLI is accessible on remote sites:

```bash
ssh user@staging-host.com "wp --version"
ssh user@staging-host.com "cd /path/to/wordpress && wp core is-installed && echo OK"
```

## Unit Testing

### Test MARKER Line Parsing

Create a test script to verify the parser:

```python
from orchestrator import parse_marker_lines

output = """
Some regular output
MARKER from_version=1.2.3
MARKER to_version=1.2.4
MARKER status=ok
More output here
"""

markers = parse_marker_lines(output)
assert markers['from_version'] == '1.2.3'
assert markers['to_version'] == '1.2.4'
assert markers['status'] == 'ok'
print("✅ MARKER parsing works")
```

### Test URL Redaction

```python
from orchestrator import redact_url

url1 = "https://example.com/plugin.zip?key=SECRET123"
url2 = "https://example.com/plugin.zip"

assert redact_url(url1) == "https://example.com/plugin.zip?[REDACTED]"
assert redact_url(url2) == "https://example.com/plugin.zip"
print("✅ URL redaction works")
```

### Test Database Schema

```bash
# Run orchestrator with --dry-run to create DB
python orchestrator.py --sites inventory/sites.yaml --plugins jobs/example.csv --dry-run

# Inspect schema
sqlite3 state/results.sqlite ".schema"
```

Expected output:
```sql
CREATE TABLE runs (...);
CREATE TABLE tasks (...);
CREATE INDEX idx_tasks_run_id ON tasks(run_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_site_plugin ON tasks(site_name, plugin_slug);
```

## Integration Testing

### Test 1: Dry Run Mode

**Purpose:** Verify task expansion and filtering without executing.

```bash
python orchestrator.py \
  --sites inventory/sites.yaml \
  --plugins jobs/example.csv \
  --dry-run
```

**Expected:**
- ✅ Lists all tasks (sites × plugins)
- ✅ Shows redacted URLs for query strings
- ✅ Exits with code 0
- ✅ No SSH connections made

### Test 2: Single Site, Single Plugin (Success Path)

**Purpose:** Basic end-to-end test.

**Setup:**
1. Create minimal inventory with 1 staging site
2. Create job CSV with 1 plugin (use a small, safe plugin)

```yaml
# inventory/test-staging.yaml
- name: test-staging
  host: staging.example.com
  user: wpuser
  path: /var/www/wordpress
  url: https://staging.example.com
  wp_cli: wp
```

```csv
# jobs/test-single.csv
plugin_slug,zip_source,type,activate
hello-dolly,https://downloads.wordpress.org/plugin/hello-dolly.1.7.2.zip,url,false
```

**Execute:**
```bash
python orchestrator.py \
  --sites inventory/test-staging.yaml \
  --plugins jobs/test-single.csv \
  --debug
```

**Verify:**
- ✅ Task completes (check exit code: `echo $?`)
- ✅ CSV report in `reports/run-*.csv`
- ✅ Markdown report in `reports/run-*.md`
- ✅ SQLite record: `sqlite3 state/results.sqlite "SELECT * FROM tasks ORDER BY task_id DESC LIMIT 1;"`
- ✅ Remote backup exists: `ssh user@host "ls -lh /var/www/wordpress/backups/"`
- ✅ Plugin version changed

### Test 3: Concurrency (3 Sites × 2 Plugins)

**Purpose:** Verify parallel execution.

**Setup:**
- 3 staging sites in inventory
- 2 small plugins in job CSV
- Total: 6 tasks

**Execute:**
```bash
time python orchestrator.py \
  --sites inventory/test-multi.yaml \
  --plugins jobs/test-multi.csv \
  --concurrency 3
```

**Verify:**
- ✅ All 6 tasks complete
- ✅ Execution time < (6 × single task time) - proves concurrency
- ✅ All tasks in database: `sqlite3 state/results.sqlite "SELECT COUNT(*) FROM tasks WHERE run_id = (SELECT MAX(run_id) FROM runs);"`
- ✅ No SSH connection errors
- ✅ Reports show all 6 tasks

### Test 4: Retry Failed Mechanism

**Purpose:** Verify selective retry of failures.

**Setup:**
1. Run an update that will partially fail (e.g., one site with bad SSH credentials)
2. Fix the issue
3. Run with `--retry-failed`

**Execute:**
```bash
# Initial run (will have failures)
python orchestrator.py \
  --sites inventory/test-mixed.yaml \
  --plugins jobs/test-single.csv

# Fix the issue (e.g., correct SSH key)

# Retry
python orchestrator.py \
  --sites inventory/test-mixed.yaml \
  --plugins jobs/test-single.csv \
  --retry-failed
```

**Verify:**
- ✅ Second run only processes previously failed tasks
- ✅ Successful tasks from first run are NOT retried
- ✅ New run_id created in database
- ✅ Exit code 0 if retry succeeds

### Test 5: Timeout Handling

**Purpose:** Verify timeout enforcement.

**Execute:**
```bash
python orchestrator.py \
  --sites inventory/test-staging.yaml \
  --plugins jobs/test-single.csv \
  --timeout-sec 5
```

**Verify:**
- ✅ Task times out after 5 seconds
- ✅ Status marked as `failed`
- ✅ Error message contains "TIMEOUT"
- ✅ Exit code 1

### Test 6: Maintenance Mode Guard

**Purpose:** Verify maintenance mode is always cleared.

**Setup:**
1. Manually enable maintenance mode on staging site
2. Run update

**Execute:**
```bash
# Enable maintenance manually
ssh user@host "cd /path/to/wp && wp maintenance-mode activate"

# Run update
python orchestrator.py \
  --sites inventory/test-staging.yaml \
  --plugins jobs/test-single.csv

# Check maintenance mode after
ssh user@host "cd /path/to/wp && wp maintenance-mode is-active || echo 'Cleared!'"
```

**Verify:**
- ✅ Maintenance mode cleared even if script ran
- ✅ MARKER output shows `maintenance_cleared=true`
- ✅ No .maintenance file exists

### Test 7: Filter Options

**Purpose:** Verify --only-sites and --only-plugins filters.

**Execute:**
```bash
# Filter to specific sites
python orchestrator.py \
  --sites inventory/sites.yaml \
  --plugins jobs/example.csv \
  --only-sites site1,site2 \
  --dry-run

# Filter to specific plugins
python orchestrator.py \
  --sites inventory/sites.yaml \
  --plugins jobs/example.csv \
  --only-plugins plugin-slug-1 \
  --dry-run
```

**Verify:**
- ✅ Only specified sites/plugins in task list
- ✅ Task count matches filters

### Test 8: SCP File Transfer

**Purpose:** Verify local file transfer.

**Setup:**
```csv
# jobs/test-local.csv
plugin_slug,zip_source,type,activate
test-plugin,/path/to/local/plugin.zip,file,false
```

**Execute:**
```bash
python orchestrator.py \
  --sites inventory/test-staging.yaml \
  --plugins jobs/test-local.csv
```

**Verify:**
- ✅ File copied to remote `/tmp/plugin.zip`
- ✅ Plugin installed from copied file
- ✅ No SCP errors in output

### Test 9: URL Download (Remote)

**Purpose:** Verify remote URL download.

**Setup:**
```csv
# jobs/test-url.csv
plugin_slug,zip_source,type,activate
hello-dolly,https://downloads.wordpress.org/plugin/hello-dolly.1.7.2.zip,url,false
```

**Execute:**
```bash
python orchestrator.py \
  --sites inventory/test-staging.yaml \
  --plugins jobs/test-url.csv
```

**Verify:**
- ✅ Remote script downloads file via curl
- ✅ Plugin installs successfully
- ✅ No ZIP_FETCH_FAIL errors

### Test 10: HTTP Health Check

**Purpose:** Verify HTTP probing works.

**Execute:**
```bash
python orchestrator.py \
  --sites inventory/test-staging.yaml \
  --plugins jobs/test-single.csv \
  --debug
```

**Verify:**
- ✅ MARKER line shows `http_code=200` (or actual code)
- ✅ Status is `ok` if HTTP 200
- ✅ Status is `needs_attention` if HTTP != 200

## Error Simulation Testing

### Test SSH Connection Failure

**Setup:** Use invalid hostname in inventory

```yaml
- name: bad-site
  host: nonexistent.example.com
  user: user
  path: /path
  url: https://example.com
  wp_cli: wp
```

**Verify:**
- ✅ Error type: `SSH_CONNECT_FAIL`
- ✅ Status: `failed`
- ✅ Exit code: 1

### Test WP Not Installed

**Setup:** Point path to non-WordPress directory

**Verify:**
- ✅ Error type: `WP_NOT_INSTALLED`
- ✅ Remote script exits early
- ✅ No database backup attempted

### Test Invalid Plugin ZIP

**Setup:** Use URL that returns 404

**Verify:**
- ✅ Error type: `ZIP_FETCH_FAIL`
- ✅ Database backup created (before ZIP fetch)
- ✅ Plugin not modified

## Performance Testing

### Large Scale Test (50 Sites)

**Purpose:** Verify tool scales to production.

**Execute:**
```bash
time python orchestrator.py \
  --sites inventory/sites-prod.yaml \
  --plugins jobs/monthly-update.csv \
  --concurrency 10
```

**Verify:**
- ✅ All 50+ sites process
- ✅ No memory leaks (monitor with `top`)
- ✅ Database performance acceptable
- ✅ Reports generate in reasonable time

### Stress Test (High Concurrency)

**Execute:**
```bash
python orchestrator.py \
  --sites inventory/sites.yaml \
  --plugins jobs/plugins.csv \
  --concurrency 50
```

**Verify:**
- ✅ System remains stable
- ✅ SSH connections don't exhaust limits
- ✅ All tasks complete

## Rollback Testing

### Manual Rollback Procedure

**Simulate a bad update:**

1. Run update
2. Identify backup: `ssh user@host "ls -lh backups/"`
3. Restore DB: `ssh user@host "cd /path/to/wp && wp db import backups/pre-update-*.sql"`
4. Verify: `ssh user@host "cd /path/to/wp && wp plugin list"`

**Verify:**
- ✅ Database restored to pre-update state
- ✅ Site functional

## CI/CD Testing

### Test Exit Codes in Pipeline

```bash
#!/bin/bash

# This should exit 0
python orchestrator.py --sites inventory/test-ok.yaml --plugins jobs/test.csv
if [ $? -ne 0 ]; then
  echo "FAIL: Expected exit 0 for successful run"
  exit 1
fi

# This should exit 1 (contains failures)
python orchestrator.py --sites inventory/test-fail.yaml --plugins jobs/test.csv
if [ $? -ne 1 ]; then
  echo "FAIL: Expected exit 1 for failed run"
  exit 1
fi

echo "✅ Exit codes work correctly"
```

## Final Checklist

Before deploying to production:

- [ ] All unit tests pass
- [ ] Dry run on prod inventory succeeds
- [ ] Single plugin update on staging succeeds
- [ ] Multi-site update on staging succeeds
- [ ] Retry mechanism tested
- [ ] Maintenance mode guard tested
- [ ] Timeout handling tested
- [ ] Reports generate correctly
- [ ] Database queries performant
- [ ] Rollback procedure documented and tested
- [ ] SSH keys configured for all prod sites
- [ ] Backups directory has sufficient space
- [ ] Monitoring/alerting configured (if applicable)

## Automated Test Script

Save as `run_tests.sh`:

```bash
#!/bin/bash
set -e

echo "Running WP Multi-Updater Test Suite..."

echo "✅ Test 1: Dry run"
python orchestrator.py --sites inventory/sites.yaml --plugins jobs/example.csv --dry-run

echo "✅ Test 2: URL redaction"
python -c "from orchestrator import redact_url; assert redact_url('http://ex.com/f?k=v') == 'http://ex.com/f?[REDACTED]'"

echo "✅ Test 3: MARKER parsing"
python -c "from orchestrator import parse_marker_lines; markers = parse_marker_lines('MARKER status=ok\nMARKER http_code=200'); assert markers['status'] == 'ok'"

echo "✅ Test 4: Database schema"
python orchestrator.py --sites inventory/sites.yaml --plugins jobs/example.csv --dry-run
sqlite3 state/results.sqlite "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name IN ('runs', 'tasks');" | grep -q 2

echo ""
echo "🎉 All automated tests passed!"
echo ""
echo "Next steps:"
echo "1. Run integration tests on staging sites"
echo "2. Review test output in reports/"
echo "3. Verify SSH access to all production sites"
```

Make executable: `chmod +x run_tests.sh`

Run: `./run_tests.sh`
