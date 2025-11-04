# Cloudways Setup Guide

Complete guide for managing multiple Cloudways servers and WordPress sites.

---

## Part 1: Upload SSH Key to Cloudways Servers (One-Time Setup)

### Your SSH Public Key

Copy this entire line:

```
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDR86pGASpFyKXl1Tf3ZWiIvh3zlXvBXX2tdJKsZEzPgEkZf8fUajRJcShR/RAFUYgrrT5Ydw0LA3T0S+MkhMS+5MTA07BI3j368mtByDLo+4uYWAc+jZVM/Myk0ucmKQ9k9kx4i/wG4e1KLHIvW0VIZEBqSBga6rjVj2yhfkx6/floneGrWHI70fu6+yw8nG9+EnTx/MjpeHB3N9klo+hwVl8L4aK4vI88gdMf7fvhzaeLON6XWdmv59p1e3YE9km2HnH5lmHnyp0r03CJhG7HB3iRgz8FcxSLpfrMF9OTBvwTASZl3oOLacU36dlyNMb/J5KEjTVPgQrW1tk4Mk/QJvuzZauoby+5XNe5KNxIvzfX/DwdMlfvSNx4yN6T2HiMZirJEp8PhwyNqOdKhJH5hPsrh4ftIBJejWN0IA5hfn8DMnQyBBtiiWCIV/5iw0gXgyMLscr+ilzS7EMFLoy6busyhGVBhpPbLK9ujtPfd/h7fd3U134KEPCZomDQZ1l4xOWHx8ym/fiCQbAXCLHTGx6QBLdM+pLkD6DjVMMgsZligLTG78qKr6U9zxUyKJZ7dTveTUlR+CfMQ836kscalikoF5p9+J4sKmcMe90A+USWmaNpEibjDGyFP2OyqWUsl4jmHvS4MeNaAZ8N1ZD4U+W5G+lDw4mFZXVr6Fwtzw== cloudways-wp-updater
```

### Upload to Each Server

**For each of your 10-20 Cloudways servers:**

1. **Log in** → https://platform.cloudways.com

2. **Navigate:** Sidebar → `Servers`

3. **Select a server** from your list

4. **Go to:** `Master Credentials` tab (top of page)

5. **Scroll to:** "SSH Public Key" section

6. **Paste the key** (the entire line above)

7. **Click:** `Save`

8. **Wait 30 seconds** for propagation

9. **Repeat** for all other servers

### Why This Works

- ✅ One key upload per **server** (not per application)
- ✅ All WordPress sites on that server automatically get access
- ✅ If you have 5 sites on 1 server = 1 upload gives access to all 5
- ✅ Total uploads needed = number of servers (10-20), not number of sites

---

## Part 2: Get Cloudways API Credentials

### Step 1: Access API Settings

1. **Cloudways Dashboard** → Click your **profile icon** (top right)
2. Click **`API`**
3. You'll see:
   - **Email:** Your Cloudways email (already shown)
   - **API Key:** Click **`Generate`** if you don't have one

### Step 2: Save to Environment

Create a `.env` file:

```bash
cd /Users/paulsteele/projects/plugin-updater
cp .env.sample .env
```

Edit `.env` and add:

```bash
CLOUDWAYS_EMAIL=your-email@example.com
CLOUDWAYS_API_KEY=your-actual-api-key-here
```

**Security:** The `.env` file is gitignored - your credentials stay local.

---

## Part 3: Auto-Generate Inventory from Cloudways API

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `PyYAML` (YAML parsing)
- `requests` (API calls)

### Step 2: Run the Inventory Generator

```bash
python scripts/generate_inventory_from_cloudways.py
```

**What it does:**
1. Authenticates with Cloudways API
2. Fetches all your servers
3. Fetches all applications per server
4. Generates `inventory/sites-cloudways-auto.yaml` with:
   - Site names (normalized from app labels)
   - SSH hostnames
   - SSH usernames per app
   - Application paths
   - URLs (from CNAME or app URL)

### Step 3: Review the Generated File

```bash
cat inventory/sites-cloudways-auto.yaml
```

Example output:
```yaml
# WordPress Sites Inventory - Auto-generated from Cloudways API
# Generated: Mon Jan 4 14:30:00 PST 2025

- name: craterian-staging
  host: server-123456.cloudways.com
  user: abcdef123456
  path: /home/123456.cloudways.com/craterian_stag/public_html
  url: https://staging.craterian.org
  wp_cli: wp

- name: craterian-prod
  host: server-789012.cloudways.com
  user: ghijkl789012
  path: /home/789012.cloudways.com/craterian_prod/public_html
  url: https://www.craterian.org
  wp_cli: wp

# ... all your other sites ...
```

### Step 4: Use the Generated Inventory

**Option A: Replace existing inventory**
```bash
mv inventory/sites-cloudways-auto.yaml inventory/sites.yaml
```

**Option B: Merge with existing sites**
```bash
cat inventory/sites-cloudways-auto.yaml >> inventory/sites.yaml
```

**Option C: Keep separate and use as needed**
```bash
python orchestrator.py --sites inventory/sites-cloudways-auto.yaml --plugins jobs/plugins.csv
```

---

## Part 4: Test Connection to One Site

Let's verify everything works with a single site first:

### Step 1: Pick One Site to Test

Look at your generated inventory and pick a staging site:

```bash
head -20 inventory/sites-cloudways-auto.yaml
```

Note the `name` field (e.g., `craterian-staging`).

### Step 2: Test SSH Connection

```bash
# Replace 'craterian-staging' with your actual site name from inventory
python orchestrator.py \
  --sites inventory/sites-cloudways-auto.yaml \
  --plugins jobs/example.csv \
  --only-sites craterian-staging \
  --dry-run
```

This will:
- ✅ Load your inventory
- ✅ Filter to just that one site
- ✅ Show what would be updated (without doing it)
- ✅ Verify SSH config is working

### Step 3: Verify WP-CLI Access

If dry-run works, test actual WP-CLI:

```bash
# Get the site details from inventory
HOST="server-123456.cloudways.com"  # Replace with actual
USER="abcdef123456"                  # Replace with actual
PATH="/home/123456.cloudways.com/app/public_html"  # Replace with actual

# Test WP-CLI
ssh -i ~/.ssh/id_rsa_cloudways $USER@$HOST "cd $PATH && wp core version"
```

Should output WordPress version (e.g., `6.4.2`).

---

## Part 5: Run Your First Update

### Create a Job File

```bash
cat > jobs/craterian-events-calendar.csv <<'EOF'
plugin_slug,zip_source,type,activate
events-calendar-pro,/Users/paulsteele/ownCloud/Wordpress Plugins/events-calendar-pro7.7.9.zip,file,false
EOF
```

### Dry Run First (Recommended)

```bash
python orchestrator.py \
  --sites inventory/sites-cloudways-auto.yaml \
  --plugins jobs/craterian-events-calendar.csv \
  --only-sites craterian-staging \
  --dry-run
```

### Execute the Update

```bash
python orchestrator.py \
  --sites inventory/sites-cloudways-auto.yaml \
  --plugins jobs/craterian-events-calendar.csv \
  --only-sites craterian-staging
```

### Review Results

```bash
# Latest report
ls -lt reports/run-*.md | head -1 | xargs cat

# Or CSV format
ls -lt reports/run-*.csv | head -1 | xargs cat
```

---

## Part 6: Scale to All Sites

Once you've tested with one site:

### Update All Staging Sites

```bash
python orchestrator.py \
  --sites inventory/sites-cloudways-auto.yaml \
  --plugins jobs/craterian-events-calendar.csv \
  --only-sites site1-staging,site2-staging,site3-staging
```

### Update All Production Sites (Carefully!)

```bash
# Dry run first!
python orchestrator.py \
  --sites inventory/sites-cloudways-auto.yaml \
  --plugins jobs/monthly-updates.csv \
  --only-sites site1-prod,site2-prod \
  --dry-run

# Then execute
python orchestrator.py \
  --sites inventory/sites-cloudways-auto.yaml \
  --plugins jobs/monthly-updates.csv \
  --only-sites site1-prod,site2-prod
```

### Update Everything (Ultimate Scale)

```bash
# Update one plugin across ALL sites
python orchestrator.py \
  --sites inventory/sites-cloudways-auto.yaml \
  --plugins jobs/critical-security-update.csv \
  --concurrency 20  # Higher for faster completion
```

---

## Troubleshooting

### SSH Connection Fails

**Error:** `Permission denied (publickey)`

**Fix:**
1. Verify key is uploaded to Cloudways server
2. Wait 60 seconds after upload
3. Check SSH config: `cat ~/.ssh/config`
4. Test manually: `ssh -i ~/.ssh/id_rsa_cloudways USER@HOST`

### API Authentication Fails

**Error:** `Failed to authenticate with Cloudways API`

**Fix:**
1. Verify credentials: `cat .env | grep CLOUDWAYS`
2. Check API key is active: Cloudways Dashboard → Profile → API
3. Regenerate key if needed

### WP-CLI Not Found

**Error:** `WP_NOT_INSTALLED`

**Fix:**
1. Verify WP-CLI on remote: `ssh USER@HOST "which wp"`
2. Update inventory if path is different:
   ```yaml
   wp_cli: /usr/local/bin/wp  # Custom path
   ```

### Wrong Application Path

**Fix:** Re-run inventory generator, or manually check:
```bash
ssh USER@HOST "pwd"
# Should show: /home/xxxxx.cloudways.com/app_name
```

Then verify WordPress:
```bash
ssh USER@HOST "ls -la | grep wp-config.php"
```

---

## Maintenance

### Re-generate Inventory (As Sites Change)

Run monthly or when you add/remove sites:

```bash
python scripts/generate_inventory_from_cloudways.py
```

### Rotate SSH Keys

If compromised:
1. Generate new key: `ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa_cloudways_new`
2. Upload to all Cloudways servers
3. Update `~/.ssh/config` to use new key
4. Remove old key from Cloudways

---

## Next Steps

1. ✅ Upload SSH key to first Cloudways server
2. ✅ Get API credentials and add to `.env`
3. ✅ Run inventory generator
4. ✅ Test with one site (dry-run)
5. ✅ Execute first real update
6. ✅ Scale to all sites
7. ✅ Set up monthly update jobs
8. ✅ Automate with cron/CI-CD

**You now have automated WordPress plugin updates across unlimited Cloudways sites!** 🚀
