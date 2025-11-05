# Adding Sites to Inventory

Quick guide for adding WordPress sites to the updater tool.

## Option 1: Edit YAML Directly (Recommended for 1-3 sites)

### Step 1: Open the inventory file
```bash
vim inventory/sites.yaml
```

### Step 2: Add your site using the template

```yaml
- name: your-site-name           # Unique identifier (lowercase-with-dashes)
  host: 104.207.159.106          # Server IP (same for all apps on that server)
  user: master_abcdefg           # SSH username from Cloudways
  path: /home/master/applications/xxxxxxxxxx/public_html  # App path from Cloudways
  url: https://yoursite.com      # Public URL (for health checks)
  wp_cli: wp                     # WP-CLI command (usually just "wp")
```

### Step 3: Group by server for organization

**Recommended structure:**
```yaml
# ========================================
# Cloudways Server: WP-4 (104.207.159.106)
# ========================================

- name: site1-on-wp4
  host: 104.207.159.106
  user: user_site1
  path: /home/master/applications/aaaaaa/public_html
  url: https://site1.com
  wp_cli: wp

- name: site2-on-wp4
  host: 104.207.159.106      # Same IP as site1
  user: user_site2            # Different user
  path: /home/master/applications/bbbbbb/public_html  # Different path
  url: https://site2.com
  wp_cli: wp

# ========================================
# Cloudways Server: WP-5 (123.45.67.89)
# ========================================

- name: site-on-wp5
  host: 123.45.67.89           # Different server IP
  user: user_site3
  path: /home/master/applications/cccccc/public_html
  url: https://site3.com
  wp_cli: wp
```

### Key Points:
- **Same Server = Same IP:** All apps on WP-4 use `104.207.159.106`
- **Each App = Unique User:** Every site has its own SSH username
- **Each App = Unique Path:** Every site has its own application directory
- **Grouping is Optional:** Comments are just for your organization

---

## Option 2: Interactive Script (Easiest for 1 site)

Use the interactive helper to add one site with validation:

```bash
./scripts/add-site.sh
```

**Prompts:**
1. Site name
2. Server IP
3. SSH username
4. Application path
5. Site URL
6. WP-CLI path

**Benefits:**
- ✅ Tests SSH connection before adding
- ✅ Verifies WP-CLI works
- ✅ Shows WordPress version
- ✅ Auto-appends to inventory/sites.yaml

---

## Option 3: CSV Import (Best for 5+ sites)

For bulk imports, use a spreadsheet:

### Step 1: Create CSV file

Use the template: [inventory/sites-import-template.csv](inventory/sites-import-template.csv)

```csv
name,host,user,path,url,wp_cli
site1-prod,104.207.159.106,user1,/home/master/applications/app1/public_html,https://site1.com,wp
site2-staging,104.207.159.106,user2,/home/master/applications/app2/public_html,https://staging.site2.com,wp
site3-prod,123.45.67.89,user3,/home/master/applications/app3/public_html,https://site3.com,wp
```

### Step 2: Import

```bash
python scripts/import-sites-from-csv.py your-sites.csv
```

**Benefits:**
- ✅ Fast for many sites
- ✅ Can export from Cloudways API or spreadsheet
- ✅ Preview before importing
- ✅ Validates CSV format

---

## Getting Site Details from Cloudways

### Method 1: Manual (Reliable)

For each site:

1. **Cloudways Dashboard** → **Applications** → [Your App]
2. Click **Access Details** tab
3. Copy:
   - **SSH/SFTP Username** → `user` field
   - **Application Path** → `path` field
   - Note the site URL → `url` field

4. Go to **Servers** → [Server hosting this app]
5. Copy **Public IP** → `host` field

### Method 2: Cloudways API (When Fixed)

Once API rate limiting is resolved:

```bash
source venv/bin/activate
python scripts/generate_inventory_from_cloudways.py
# Generates: inventory/sites-cloudways-auto.yaml
```

Then review and merge into `sites.yaml`.

---

## Testing New Sites

After adding a site, always test before bulk operations:

### 1. Test SSH Connection
```bash
ssh -i ~/.ssh/id_rsa_cloudways USER@HOST "cd PATH && wp core version"
```

**Expected:** WordPress version number (e.g., `6.8.3`)

### 2. Test Site in Orchestrator (Dry Run)
```bash
python orchestrator.py \
  --sites inventory/sites.yaml \
  --plugins jobs/example.csv \
  --only-sites your-new-site \
  --dry-run
```

**Expected:** Shows 1 task, no errors

### 3. Test with Real Update (Optional)
```bash
# Use a safe plugin that's already installed
python orchestrator.py \
  --sites inventory/sites.yaml \
  --plugins jobs/safe-test.csv \
  --only-sites your-new-site
```

---

## Common Patterns

### Multiple Sites on Same Server

```yaml
# All 5 sites on WP-4 server
- name: craterian-staging
  host: 104.207.159.106    # WP-4
  user: master_craterian
  path: /home/master/applications/craterian/public_html
  url: https://staging.craterian.org
  wp_cli: wp

- name: brittfest-staging
  host: 104.207.159.106    # Same WP-4 server
  user: master_brittfest   # Different user
  path: /home/master/applications/brittfest/public_html
  url: https://staging.brittfest.org
  wp_cli: wp

- name: client-site-staging
  host: 104.207.159.106    # Same WP-4 server
  user: master_client
  path: /home/master/applications/client/public_html
  url: https://staging.client.com
  wp_cli: wp
```

### Staging + Production Pairs

```yaml
# Staging environment
- name: mysite-staging
  host: 104.207.159.106    # WP-4 (staging server)
  user: master_mysite_stag
  path: /home/master/applications/mysite_stag/public_html
  url: https://staging.mysite.com
  wp_cli: wp

# Production environment
- name: mysite-prod
  host: 192.168.1.100      # WP-1 (production server)
  user: master_mysite_prod
  path: /home/master/applications/mysite_prod/public_html
  url: https://www.mysite.com
  wp_cli: wp
```

Then update selectively:
```bash
# Test on staging first
python orchestrator.py --sites inventory/sites.yaml --plugins jobs/update.csv --only-sites mysite-staging

# If successful, update production
python orchestrator.py --sites inventory/sites.yaml --plugins jobs/update.csv --only-sites mysite-prod
```

### Custom WP-CLI Paths

Some Cloudways servers may have custom WP-CLI locations:

```yaml
- name: special-site
  host: 123.45.67.89
  user: special_user
  path: /custom/path/to/wordpress
  url: https://special.com
  wp_cli: /usr/local/bin/wp    # Custom path
```

---

## Troubleshooting

### Site Not Found Error

**Error:** `FileNotFoundError: Sites file not found`

**Fix:** Check file path:
```bash
ls inventory/sites.yaml
# Should exist
```

### YAML Syntax Error

**Error:** `yaml.scanner.ScannerError`

**Fix:** Validate YAML syntax:
```bash
python -c "import yaml; yaml.safe_load(open('inventory/sites.yaml'))"
# Should print the structure with no errors
```

### SSH Connection Fails

**Error:** `SSH_CONNECT_FAIL`

**Checklist:**
- [ ] SSH key uploaded to Cloudways server?
- [ ] Correct username (check Cloudways Access Details)?
- [ ] Correct server IP (not site URL)?
- [ ] Test manually: `ssh -i ~/.ssh/id_rsa_cloudways USER@HOST`

### Wrong Application Path

**Error:** `WP_NOT_INSTALLED`

**Fix:** Verify path in Cloudways:
1. Applications → Your App → Access Details
2. Copy exact path (including `/public_html` at end)
3. Test: `ssh USER@HOST "ls -la /your/path/wp-config.php"`

---

## Summary

**For 1-3 sites:** Edit `inventory/sites.yaml` directly
**For 1 site with validation:** Use `./scripts/add-site.sh`
**For 5+ sites:** Use CSV import `scripts/import-sites-from-csv.py`

**Key principle:** One YAML file, organized by comments, all sites in a flat list.

**Next:** [ADDING-PLUGINS.md](ADDING-PLUGINS.md) - How to create plugin update jobs
