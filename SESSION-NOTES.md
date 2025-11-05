# Session Notes - WP Multi-Updater

**Date:** 2025-01-05 (Updated)
**Status:** ✅ Production Ready - Core functionality complete with cache-clearing wrapper

---

## Latest Updates (2025-01-05)

### ✅ All Critical Issues Resolved

1. **SCP Path Issue** - FIXED
   - Changed destination from `/tmp/plugin.zip` to `plugin.zip` (home directory)
   - Updated ZIP_VALUE to use `$HOME/plugin.zip` instead of `~/plugin.zip`
   - Files: orchestrator.py:576, orchestrator.py:448

2. **Chmod Warnings** - FIXED
   - Modified remote-update.sh to ignore WP-CLI exit codes
   - Now verifies plugin installation with `wp plugin is-installed`
   - Prevents false failures from Cloudways permission warnings
   - Files: scripts/remote-update.sh:212-228

3. **Cache-Clearing Wrapper** - COMPLETED
   - Created scripts/update-with-cache-clear.py
   - Clears Breeze cache and Object Cache Pro before/after updates
   - Processes sites sequentially (up to 3 in parallel)
   - Proper success detection (checks for failed count = 0)

### ✅ Production Testing Completed

**Multi-Site Test Results:**
- Sites tested: craterian-staging, travelashland-staging, 1000museums-staging
- Plugins tested: Events Calendar Pro, Community Events, Filter Bar
- All 9 plugin installations successful (3 plugins × 3 sites)
- Cache clearing working properly
- HTTP health checks passing (200 OK)

### Current Inventory
- **35 production and staging sites** in inventory/sites.yaml
- Grouped by 15 Cloudways servers
- Clients: Craterian, Travel Ashland, 1000Museums, McMenamins, Britt Festival, Phoenix Oregon, SOHS, more

---

## Quick Reference Commands

### Production Workflow (RECOMMENDED)
```bash
source venv/bin/activate

# Cache-clearing wrapper - best for production
python scripts/update-with-cache-clear.py \
  --sites inventory/sites.yaml \
  --plugins jobs/my-job.csv \
  --ssh-opts "-i ~/.ssh/id_rsa_cloudways" \
  --only-sites site1,site2 \
  --max-parallel 3
```

### Standard Orchestrator (no cache clearing)
```bash
python orchestrator.py \
  --sites inventory/sites.yaml \
  --plugins jobs/my-job.csv \
  --ssh-opts "-i ~/.ssh/id_rsa_cloudways" \
  --only-sites site1,site2 \
  --concurrency 2
```

### Testing
```bash
# Test SSH
ssh -i ~/.ssh/id_rsa_cloudways USER@HOST "wp core version"

# Dry run
python orchestrator.py --sites inventory/sites.yaml --plugins jobs/test.csv --dry-run

# Single site
python orchestrator.py --sites inventory/sites.yaml --plugins jobs/test.csv --only-sites site-name
```

---

## Files Created This Session

### Key Files Modified
- `orchestrator.py` - Fixed SCP path (line 576) and ZIP_VALUE (line 448)
- `scripts/remote-update.sh` - Fixed chmod warning handling (lines 212-228)
- `scripts/update-with-cache-clear.py` - New wrapper for production use
- `inventory/sites.yaml` - Converted from CSV, 35 sites organized by server

### Job Files
- `jobs/craterian-staging-3plugins.csv` - 3 Events Calendar plugins
- `jobs/travelashland-1000museums-staging.csv` - Multi-site test job
- `jobs/craterian-events-calendar.csv` - Single plugin test

---

## Configuration

### Site Inventory Format (inventory/sites.yaml)
```yaml
- name: craterian-staging
  host: 104.207.159.106
  user: master_beesbmscpg
  path: /home/master/applications/xgeqcsqzqc/public_html
  url: https://staging.craterian.org
  wp_cli: wp
```

### Job File Format (jobs/*.csv)
```csv
plugin_slug,zip_source,type,activate
events-calendar-pro,https://owncloud.scarabmedia.com/s/ABC123/download,url,true
my-plugin,/path/to/plugin.zip,file,false
```

---

## Known Issues

### 1. Cloudways API Rate Limiting
- HTTP 429 when fetching apps for multiple servers
- Workaround: Manual inventory from CSV
- Not blocking: Manual approach works well

### 2. File Ownership
- Plugins installed via SSH owned by SSH user, not www-data
- Can't delete from WP dashboard (permission denied)
- Use WP-CLI to delete: `wp plugin delete plugin-slug`

### 3. HTTP Health Check Limitations
- Some sites return 403 due to firewalls (MalCare, Wordfence)
- Tasks marked "needs_attention" even when plugins install successfully
- Cache-clearing wrapper handles this correctly

---

## Next Steps

### Immediate Priority
1. **GUI Application**
   - Add sites to inventory easily
   - Select sites and plugins for updates
   - Real-time progress display
   - Success/failure indicators

### Future Enhancements
2. Dashboard with update history
3. Scheduled updates (cron)
4. Email notifications
5. Automated rollback

---

## Resources

- **Cloudways Dashboard:** https://platform.cloudways.com
- **WP-CLI Docs:** https://developer.wordpress.org/cli/
- **GitHub Repo:** https://github.com/webninja4/wp-multiupdater

**Status:** Production ready for CLI. Next: Building GUI.
