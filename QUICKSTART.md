# Quick Start Guide

Get up and running with WP Multi-Updater in 5 minutes.

## 1. Install Dependencies

```bash
pip install -r requirements.txt
```

## 2. Configure Sites

Edit `inventory/sites.yaml`:

```yaml
- name: mysite-prod
  host: ssh.example.com
  user: wpuser
  path: /var/www/wordpress
  url: https://www.example.com
  wp_cli: wp
```

## 3. Create Plugin Job

Edit `jobs/plugins.csv`:

```csv
plugin_slug,zip_source,type,activate
advanced-custom-fields-pro,https://example.com/acf-pro.zip,url,false
```

## 4. Test SSH Access

Verify you can connect to your sites:

```bash
ssh wpuser@ssh.example.com "cd /var/www/wordpress && wp core version"
```

## 5. Dry Run

Preview what will be updated:

```bash
python orchestrator.py --sites inventory/sites.yaml --plugins jobs/plugins.csv --dry-run
```

## 6. Execute Updates

Run the updates:

```bash
python orchestrator.py --sites inventory/sites.yaml --plugins jobs/plugins.csv
```

## 7. Review Reports

Check the output in `reports/`:

- `run-TIMESTAMP.csv` - Spreadsheet of results
- `run-TIMESTAMP.md` - Human-readable summary

## Common Commands

```bash
# Update specific sites only
python orchestrator.py --sites inventory/sites.yaml --plugins jobs/plugins.csv \
  --only-sites site1,site2

# Lower concurrency for stability
python orchestrator.py --sites inventory/sites.yaml --plugins jobs/plugins.csv \
  --concurrency 3

# Retry failed tasks
python orchestrator.py --sites inventory/sites.yaml --plugins jobs/plugins.csv \
  --retry-failed

# Increase timeout for large sites
python orchestrator.py --sites inventory/sites.yaml --plugins jobs/plugins.csv \
  --timeout-sec 1800
```

## Troubleshooting

### SSH Connection Failed

```bash
# Test SSH manually
ssh -v wpuser@ssh.example.com

# Check SSH key is loaded
ssh-add -l
```

### WP-CLI Not Found

Update `wp_cli` path in `inventory/sites.yaml`:

```yaml
wp_cli: /usr/local/bin/wp  # or /opt/wp-cli/bin/wp
```

### Timeout Errors

Increase timeout:

```bash
python orchestrator.py ... --timeout-sec 1800  # 30 minutes
```

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Review the [PRD](WP_MultiUpdater_PRD.md) for architecture details
- Set up a CI/CD pipeline for automated updates

## Safety Reminders

- Always test on staging sites first
- Database backups are created automatically in `./backups/` on each site
- Maintenance mode is automatically cleared on exit
- Use `--dry-run` to preview changes before executing
