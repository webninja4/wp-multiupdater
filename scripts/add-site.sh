#!/bin/bash
#
# add-site.sh - Interactive helper to add a new site to inventory
#
# Usage: ./scripts/add-site.sh

set -e

echo "=========================================="
echo "Add New Site to Inventory"
echo "=========================================="
echo ""

# Prompt for site details
read -p "Site name (lowercase-with-dashes, e.g., craterian-staging): " SITE_NAME
read -p "Server IP or hostname: " HOST
read -p "SSH username (from Cloudways Access Details): " USER
read -p "Application path (from Cloudways Access Details): " PATH
read -p "Site URL (e.g., https://staging.craterian.org): " URL
read -p "WP-CLI path [wp]: " WP_CLI
WP_CLI=${WP_CLI:-wp}

echo ""
echo "=========================================="
echo "Testing SSH Connection..."
echo "=========================================="

# Test SSH connection
if ssh -i ~/.ssh/id_rsa_cloudways -o BatchMode=yes -o ConnectTimeout=10 "$USER@$HOST" "cd $PATH && $WP_CLI core version" 2>&1; then
    echo "✅ SSH connection successful!"
    WP_VERSION=$(ssh -i ~/.ssh/id_rsa_cloudways "$USER@$HOST" "cd $PATH && $WP_CLI core version" 2>/dev/null)
    echo "   WordPress version: $WP_VERSION"
else
    echo "❌ SSH connection failed!"
    echo ""
    echo "Troubleshooting:"
    echo "1. Verify SSH key is uploaded to Cloudways server"
    echo "2. Check username: $USER"
    echo "3. Check host: $HOST"
    echo "4. Check path exists: $PATH"
    exit 1
fi

echo ""
echo "=========================================="
echo "Site Configuration"
echo "=========================================="
echo "name: $SITE_NAME"
echo "host: $HOST"
echo "user: $USER"
echo "path: $PATH"
echo "url: $URL"
echo "wp_cli: $WP_CLI"
echo ""

read -p "Add this site to inventory/sites.yaml? (y/n): " CONFIRM

if [[ "$CONFIRM" != "y" ]]; then
    echo "Cancelled."
    exit 0
fi

# Append to inventory
cat >> inventory/sites.yaml <<EOF

- name: $SITE_NAME
  host: $HOST
  user: $USER
  path: $PATH
  url: $URL
  wp_cli: $WP_CLI
EOF

echo ""
echo "✅ Site added to inventory/sites.yaml"
echo ""
echo "Next steps:"
echo "1. Verify: cat inventory/sites.yaml"
echo "2. Test: python orchestrator.py --sites inventory/sites.yaml --plugins jobs/example.csv --only-sites $SITE_NAME --dry-run"
echo ""
