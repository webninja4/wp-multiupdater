# Session Notes - WP Multi-Updater

**Date:** 2025-01-04
**Status:** Proof of Concept Working, Production Refinements Needed

---

## What We Accomplished This Session

### 1. ✅ Created Complete Tool Structure
- **orchestrator.py** (797 lines) - Main CLI with concurrency, DB, reporting
- **scripts/remote-update.sh** (225 lines) - Idempotent bash script with MARKER output
- **SQLite schema** - runs + tasks tables with indexes
- **Sample configs** - inventory/sites.yaml, jobs/*.csv
- **Documentation** - README.md, QUICKSTART.md, TESTING.md, CLOUDWAYS_SETUP.md

### 2. ✅ SSH Key Setup Completed
- Generated 4096-bit RSA key: `~/.ssh/id_rsa_cloudways`
- Public key uploaded to **all 23 Cloudways servers**
- SSH config created at `~/.ssh/config` for automatic key selection
- Verified SSH connectivity to Craterian staging server

### 3. ✅ Cloudways API Integration
- API credentials configured in `.env`:
  - Email: `webmaster@projecta.com`
  - API Key: `97IHjEd19ZgjejUN8WlfA9OTUcXMBh`
- Created `scripts/generate_inventory_from_cloudways.py`
- Discovered 23 Cloudways servers via API
- **Issue:** API rate limiting (HTTP 429) prevents batch inventory generation

### 4. ✅ First Test Execution
- **Site:** staging.craterian.org (104.207.159.106)
- **Plugin:** Events Calendar Pro 7.7.9
- **Result:** Script executed successfully (manual mode)
  - Database backup created: `./backups/pre-update-20251105-000903-events-calendar-pro.sql`
  - Plugin reinstalled with `--force` (idempotent)
  - Remained active (preserved state)
  - Maintenance mode cleared automatically
  - MARKER lines emitted correctly

---

## Current Issues & Blockers

### 1. SCP Permission Issue (CRITICAL)
**Problem:** Cannot SCP directly to `/tmp/plugin.zip` on Cloudways servers.

**Error:**
```
scp: dest open "/tmp/plugin.zip": No such file or directory
```

**Root Cause:** Cloudways `/tmp` directory has restrictive permissions that prevent SCP file creation.

**Fix Needed:**
- Change orchestrator.py SCP destination from `/tmp/plugin.zip` to `~/plugin.zip`
- Update remote-update.sh to look for plugin at `~/plugin.zip` instead of `/tmp/plugin.zip`
- OR: Use application-specific temp directory like `$APP_PATH/tmp/plugin.zip`

**Code Location:**
- [orchestrator.py:338](orchestrator.py#L338) - `scp_file()` function
- [scripts/remote-update.sh:120-140](scripts/remote-update.sh#L120-L140) - ZIP_VALUE path handling

### 2. Cloudways API Rate Limiting
**Problem:** API returns HTTP 429 when fetching apps for multiple servers.

**Current Behavior:**
- Can authenticate successfully
- Can fetch server list (23 servers)
- Fails when fetching apps per server (rate limited after 4-5 requests)

**Attempted Fix:**
- Added 2-second delay between requests - still rate limited

**Next Steps to Try:**
- Increase delay to 5-10 seconds
- Implement exponential backoff on 429 errors
- Cache API responses (fetch once, use for days)
- OR: Use manual inventory creation for now

### 3. Chmod Warnings on Cloudways
**Problem:** WP-CLI plugin install shows ~100 chmod warnings.

**Impact:** Cosmetic only - plugin installs successfully.

**Cause:** Cloudways file ownership restrictions (files owned by `www-data`, SSH user is different).

**Fix Options:**
- Suppress stderr in WP-CLI call: `wp plugin install ... 2>/dev/null`
- Ignore warnings in MARKER parsing (don't fail on stderr)
- Document as expected behavior

---

## Files Created/Modified This Session

### New Files
```
inventory/craterian.yaml         - Craterian staging site config
jobs/craterian-events-calendar.csv - Events Calendar Pro job
.env                              - API credentials (gitignored)
~/.ssh/id_rsa_cloudways          - SSH key for Cloudways
~/.ssh/id_rsa_cloudways.pub      - Public key
~/.ssh/config                     - SSH config for auto key selection
CLOUDWAYS_SETUP.md                - Cloudways-specific documentation
SESSION-NOTES.md                  - This file
```

### Modified Files
```
scripts/generate_inventory_from_cloudways.py - Added .env loader, rate limit delay, error handling
requirements.txt                  - Added requests>=2.31.0
.env.sample                       - Added CLOUDWAYS_EMAIL, CLOUDWAYS_API_KEY
```

---

## Configuration Snapshot

### Craterian Staging Details
```yaml
name: craterian-staging
host: 104.207.159.106
user: master_beesbmscpg
path: /home/master/applications/xgeqcsqzqc/public_html
url: https://staging.craterian.org
wp_cli: wp
```

### SSH Connection Test
```bash
ssh -i ~/.ssh/id_rsa_cloudways master_beesbmscpg@104.207.159.106 "wp core version"
# Output: 6.8.3 ✅
```

### WP-CLI Test
```bash
wp plugin list | grep events-calendar-pro
# Output: events-calendar-pro	active	7.7.9 ✅
```

---

## Next Steps (Priority Order)

### HIGH PRIORITY

#### 1. Fix SCP Destination Path
**Goal:** Make file uploads work through the orchestrator.

**Tasks:**
- [ ] Update `orchestrator.py` - change SCP destination to `~/plugin.zip`
- [ ] Update `remote-update.sh` - accept `~/plugin.zip` or custom path
- [ ] Test end-to-end with orchestrator (not manual mode)
- [ ] Verify with file that has spaces in path

**Files to Edit:**
- `orchestrator.py:338-347` - scp_file() function
- `scripts/remote-update.sh:135-150` - ZIP file handling

**Test Command:**
```bash
python orchestrator.py \
  --sites inventory/craterian.yaml \
  --plugins jobs/craterian-events-calendar.csv \
  --ssh-opts "-i ~/.ssh/id_rsa_cloudways"
```

#### 2. Retry Cloudways API Inventory Generation
**Goal:** Get API working to auto-discover all 50+ sites.

**Approaches to Try:**

**Option A: Increase Delays**
```python
# Try 10-second delay instead of 2
time.sleep(10)
```

**Option B: Exponential Backoff**
```python
def get_apps_with_retry(access_token, server_id, max_retries=3):
    for attempt in range(max_retries):
        response = requests.get(...)
        if response.status_code == 429:
            wait = (2 ** attempt) * 5  # 5s, 10s, 20s
            time.sleep(wait)
            continue
        return response
```

**Option C: Batch Processing**
- Fetch 5 servers at a time
- Save intermediate results
- Resume from last successful server

**Test Command:**
```bash
python scripts/generate_inventory_from_cloudways.py 2>&1 | tee api-test.log
```

**Success Criteria:**
- Generate `inventory/sites-cloudways-auto.yaml` with 50+ sites
- No HTTP 429 errors
- Complete in <10 minutes

#### 3. Streamline Adding New Sites/Plugins
**Goal:** Make it easy to add sites and create update jobs.

**Option A: Interactive CLI Tool**
```bash
# Add a new site
python scripts/add-site.py

# Interactive prompts:
# Site name: mysite-prod
# SSH host: 123.45.67.89
# SSH user: abc123
# App path: /home/xxx/app/public_html
# URL: https://mysite.com
# WP-CLI path [wp]:

# Appends to inventory/sites.yaml
```

**Option B: CSV Import for Sites**
```bash
# Create sites from spreadsheet
python scripts/import-sites-csv.py sites-export.csv

# CSV format:
# name,host,user,path,url,wp_cli
# site1,1.2.3.4,user1,/path1,https://site1.com,wp
```

**Option C: Template-Based**
```bash
# Copy template and edit
cp inventory/site-template.yaml inventory/new-client.yaml
vim inventory/new-client.yaml

# Merge into main inventory
cat inventory/*.yaml > inventory/all-sites.yaml
```

**Plugin Job Templates:**
```bash
# Create job from template
cp jobs/templates/monthly-security-update.csv jobs/2025-01-security.csv

# Template has common plugins:
# - wordfence
# - updraftplus
# - wpforms
# - etc.
```

### MEDIUM PRIORITY

#### 4. Suppress Chmod Warnings
**Goal:** Clean up output, avoid false "failed" status.

**Fix in remote-update.sh:**
```bash
# Option 1: Redirect stderr
wp plugin install /tmp/plugin.zip --force 2>/dev/null

# Option 2: Filter out chmod warnings
wp plugin install /tmp/plugin.zip --force 2>&1 | grep -v "chmod()"

# Option 3: Set exit code based on plugin status, not wp-cli exit code
```

**Update status logic:**
```bash
# After install, check if plugin exists and has correct version
if wp plugin is-installed "$PLUGIN_SLUG"; then
    STATUS="ok"  # Ignore chmod warnings
fi
```

#### 5. Handle Files with Spaces in Paths
**Current Workaround:** Symlink to path without spaces.

**Better Fix:**
```python
# In orchestrator.py scp_file()
cmd = ['scp', '-i', ssh_key]
cmd.extend([local_path, f'{user}@{host}:{remote_path}'])
# subprocess will handle quoting automatically
```

#### 6. Update Documentation
- [ ] Update README.md with SCP fix instructions
- [ ] Update CLOUDWAYS_SETUP.md with API retry guidance
- [ ] Create TROUBLESHOOTING.md with common issues
- [ ] Add examples to QUICKSTART.md for multi-site scenarios

### LOW PRIORITY

#### 7. DateTime Deprecation Warnings
**Fix:**
```python
# Replace throughout orchestrator.py:
datetime.utcnow()  # Deprecated
# With:
datetime.now(timezone.utc)  # Recommended
```

#### 8. Virtual Environment in Docs
**Add to README.md:**
```bash
# Create venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 9. Add venv to .gitignore
```
# Add to .gitignore
venv/
```

---

## Quick Reference Commands

### SSH Test
```bash
ssh -i ~/.ssh/id_rsa_cloudways master_beesbmscpg@104.207.159.106 "wp core version"
```

### Run Orchestrator (Once SCP is Fixed)
```bash
source venv/bin/activate
python orchestrator.py \
  --sites inventory/craterian.yaml \
  --plugins jobs/craterian-events-calendar.csv \
  --ssh-opts "-i ~/.ssh/id_rsa_cloudways"
```

### Manual Script Execution (Current Workaround)
```bash
# 1. SCP file manually
scp -i ~/.ssh/id_rsa_cloudways "/path/to/plugin.zip" master_beesbmscpg@104.207.159.106:~/plugin.zip

# 2. Move to /tmp
ssh -i ~/.ssh/id_rsa_cloudways master_beesbmscpg@104.207.159.106 "mv ~/plugin.zip /tmp/plugin.zip"

# 3. Run script
ssh -i ~/.ssh/id_rsa_cloudways master_beesbmscpg@104.207.159.106 \
  "cd /home/master/applications/xgeqcsqzqc/public_html && \
   export PLUGIN_SLUG=events-calendar-pro && \
   export ZIP_MODE=file && \
   export ZIP_VALUE=/tmp/plugin.zip && \
   export ACTIVATE=false && \
   export SITE_URL=https://staging.craterian.org && \
   bash" < scripts/remote-update.sh
```

### Generate API Inventory
```bash
source venv/bin/activate
python scripts/generate_inventory_from_cloudways.py
```

### View Reports
```bash
# Latest Markdown report
ls -t reports/*.md | head -1 | xargs cat

# Latest CSV report
ls -t reports/*.csv | head -1 | xargs cat

# Database query
sqlite3 state/results.sqlite "SELECT * FROM tasks ORDER BY task_id DESC LIMIT 5;"
```

---

## Testing Checklist for Next Session

Before considering production-ready:

- [ ] **SCP Fix:** File upload works through orchestrator
- [ ] **End-to-End:** Single site, single plugin completes with status=ok
- [ ] **Multi-Site:** 3 sites × 1 plugin completes successfully
- [ ] **Multi-Plugin:** 1 site × 3 plugins completes successfully
- [ ] **Concurrency:** 10 tasks complete in parallel
- [ ] **Retry:** --retry-failed only retries failures
- [ ] **Filters:** --only-sites and --only-plugins work correctly
- [ ] **Reports:** CSV and Markdown generated correctly
- [ ] **Exit Codes:** 0 for all OK, 1 for any failures
- [ ] **API Inventory:** Generate YAML for all 23 servers

---

## Known Cloudways Specifics

### Server Count
- **23 Cloudways servers** in the account
- Mix of production, staging, and client sites
- Examples: "Britt Festival", "McMenamins", "Project A", "Sedona Film Festival"

### Permissions
- SSH user (e.g., `master_beesbmscpg`) ≠ file owner (`www-data`)
- Causes chmod warnings in WP-CLI (harmless)
- `/tmp` has restrictive SCP permissions

### WP-CLI Version
- Appears to be recent version (6.8.3 core detected)
- Standard `wp` command works

### Application Paths
- Format: `/home/MASTER/applications/APP_ID/public_html`
- Example: `/home/master/applications/xgeqcsqzqc/public_html`

---

## Environment State

### Python Environment
```bash
# Virtual environment created
venv/

# Installed packages:
PyYAML==6.0.3
requests==2.32.5
```

### SSH Configuration
```bash
# Key pair created
~/.ssh/id_rsa_cloudways
~/.ssh/id_rsa_cloudways.pub

# SSH config exists
~/.ssh/config
```

### Database
```bash
# SQLite database initialized
state/results.sqlite

# Schema created:
# - runs table
# - tasks table
# - indexes

# Sample data:
# - 3 test runs (all failed due to SCP issue)
```

---

## Questions for Next Session

1. **Inventory Management:**
   - Prefer API auto-discovery or manual YAML editing?
   - How often do sites change (weekly, monthly)?
   - Want to organize by client/project or all in one file?

2. **Plugin Organization:**
   - Standard update sets (security, monthly, quarterly)?
   - Per-client plugin lists?
   - Template-based or ad-hoc CSV creation?

3. **Workflow:**
   - Run updates manually or on schedule (cron)?
   - Want Slack/email notifications?
   - Need approval step before bulk updates?

4. **Rollback:**
   - Automate rollback or manual restore from backups?
   - Keep how many days of backups?

5. **Reporting:**
   - Current format (CSV + MD) sufficient?
   - Want dashboards or just files?
   - Need historical trending?

---

## Git Repository

**Remote:** https://github.com/webninja4/wp-multiupdater.git
**Branch:** main
**Last Commit:** 4fe23c7 - "Add Cloudways API integration..."

**Uncommitted Changes:**
- `.env` (gitignored - contains API key)
- `inventory/craterian.yaml` (new site)
- `jobs/craterian-events-calendar.csv` (new job)
- `venv/` (gitignored)
- `SESSION-NOTES.md` (this file)

---

## Resources & Links

- **Cloudways Dashboard:** https://platform.cloudways.com
- **Cloudways API Docs:** https://developers.cloudways.com/docs/
- **WP-CLI Handbook:** https://developer.wordpress.org/cli/commands/
- **GitHub Repo:** https://github.com/webninja4/wp-multiupdater

---

**End of Session Notes**

Resume next session with: Fix SCP path issue → Test end-to-end → Retry API inventory generation
