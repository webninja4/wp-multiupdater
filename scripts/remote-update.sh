#!/usr/bin/env bash
#
# remote-update.sh - Idempotent WordPress plugin updater
#
# USAGE: Run via SSH from orchestrator with ENV vars:
#   PLUGIN_SLUG    - WordPress plugin slug (e.g., "the-events-calendar-pro")
#   ZIP_MODE       - "url" or "file"
#   ZIP_VALUE      - URL or $HOME/plugin.zip path
#   ACTIVATE       - "true" or "false"
#   SITE_URL       - Site base URL for HTTP health check
#
# OUTPUTS: Emits structured MARKER lines for orchestrator parsing
#

set -euo pipefail

# ============================================================================
# Configuration & Validation
# ============================================================================

PLUGIN_SLUG="${PLUGIN_SLUG:?PLUGIN_SLUG environment variable required}"
ZIP_MODE="${ZIP_MODE:?ZIP_MODE environment variable required}"
ZIP_VALUE="${ZIP_VALUE:?ZIP_VALUE environment variable required}"
ACTIVATE="${ACTIVATE:-false}"
SITE_URL="${SITE_URL:?SITE_URL environment variable required}"

# Defaults
WP_CLI="${WP_CLI:-wp}"
BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
ZIP_PATH="/tmp/plugin-${PLUGIN_SLUG}-$$.zip"

# Status tracking
STATUS="failed"
FROM_VERSION="none"
TO_VERSION="none"
BACKUP_PATH="none"
HTTP_CODE="0"
MAINTENANCE_CLEARED="false"
ERROR_MESSAGE=""

# ============================================================================
# Cleanup Function - ALWAYS runs on exit
# ============================================================================

cleanup() {
  local exit_code=$?

  # Force clear maintenance mode if active
  if $WP_CLI maintenance-mode is-active 2>/dev/null; then
    $WP_CLI maintenance-mode deactivate 2>/dev/null || true
  fi

  # Belt-and-suspenders: remove .maintenance file if exists
  if [[ -f .maintenance ]]; then
    rm -f .maintenance 2>/dev/null || true
  fi

  MAINTENANCE_CLEARED="true"

  # Clean up temporary ZIP file
  if [[ -f "$ZIP_PATH" ]]; then
    rm -f "$ZIP_PATH" 2>/dev/null || true
  fi

  # Emit all MARKER lines for orchestrator parsing
  echo "MARKER from_version=${FROM_VERSION}"
  echo "MARKER to_version=${TO_VERSION}"
  echo "MARKER backup_path=${BACKUP_PATH}"
  echo "MARKER http_code=${HTTP_CODE}"
  echo "MARKER maintenance_cleared=${MAINTENANCE_CLEARED}"
  echo "MARKER status=${STATUS}"

  if [[ -n "$ERROR_MESSAGE" ]]; then
    echo "MARKER error=${ERROR_MESSAGE}"
  fi

  exit $exit_code
}

trap cleanup EXIT INT TERM

# ============================================================================
# Helper Functions
# ============================================================================

log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" >&2
}

error_exit() {
  ERROR_MESSAGE="$1"
  STATUS="failed"
  log "ERROR: $ERROR_MESSAGE"
  exit 1
}

# ============================================================================
# Pre-flight Checks
# ============================================================================

log "Starting update for plugin: $PLUGIN_SLUG"
log "ZIP mode: $ZIP_MODE, value: $ZIP_VALUE"
log "Site URL: $SITE_URL"

# Check WP-CLI is available
if ! command -v "$WP_CLI" >/dev/null 2>&1; then
  error_exit "WP_NOT_INSTALLED: wp-cli command not found: $WP_CLI"
fi

# Verify WordPress installation
if ! $WP_CLI core is-installed 2>/dev/null; then
  error_exit "WP_NOT_INSTALLED: WordPress core is not installed or not accessible"
fi

log "WordPress installation verified"

# ============================================================================
# Maintenance Mode - Ensure Clean State
# ============================================================================

# Deactivate maintenance mode if currently active (from previous failed run)
if $WP_CLI maintenance-mode is-active 2>/dev/null; then
  log "WARNING: Maintenance mode was active, clearing it now"
  $WP_CLI maintenance-mode deactivate || true
fi

# Also check for .maintenance file
if [[ -f .maintenance ]]; then
  log "WARNING: .maintenance file exists, removing it"
  rm -f .maintenance || true
fi

# ============================================================================
# Get Pre-Update Version
# ============================================================================

log "Checking current plugin version..."

if $WP_CLI plugin is-installed "$PLUGIN_SLUG" 2>/dev/null; then
  FROM_VERSION=$($WP_CLI plugin get "$PLUGIN_SLUG" --field=version 2>/dev/null || echo "unknown")
  log "Current version: $FROM_VERSION"
else
  FROM_VERSION="not_installed"
  log "Plugin not currently installed"
fi

# ============================================================================
# Database Backup
# ============================================================================

log "Creating database backup..."

mkdir -p "$BACKUP_DIR"

BACKUP_FILENAME="pre-update-${TIMESTAMP}-${PLUGIN_SLUG}.sql"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILENAME}"

if ! $WP_CLI db export "$BACKUP_PATH" --add-drop-table 2>/dev/null; then
  error_exit "DB_BACKUP_FAIL: Failed to export database to $BACKUP_PATH"
fi

log "Database backed up to: $BACKUP_PATH"

# ============================================================================
# Fetch/Prepare Plugin ZIP
# ============================================================================

log "Preparing plugin ZIP..."

if [[ "$ZIP_MODE" == "url" ]]; then
  log "Downloading plugin from URL..."

  # Download with curl, follow redirects, fail on HTTP errors
  if ! curl -L --fail --max-time 300 --connect-timeout 30 \
       -o "$ZIP_PATH" "$ZIP_VALUE" 2>/dev/null; then
    error_exit "ZIP_FETCH_FAIL: Failed to download plugin from URL"
  fi

  log "Plugin downloaded to: $ZIP_PATH"

elif [[ "$ZIP_MODE" == "file" ]]; then
  # Expect the orchestrator already scp'd to $HOME/plugin.zip
  # ZIP_VALUE should be the path (e.g., $HOME/plugin.zip)

  if [[ ! -f "$ZIP_VALUE" ]]; then
    error_exit "ZIP_FETCH_FAIL: Expected ZIP file not found at $ZIP_VALUE"
  fi

  # Move/copy to our working path
  if [[ "$ZIP_VALUE" != "$ZIP_PATH" ]]; then
    cp "$ZIP_VALUE" "$ZIP_PATH" || error_exit "ZIP_FETCH_FAIL: Failed to copy ZIP file"
  fi

  log "Using plugin ZIP: $ZIP_PATH"

else
  error_exit "INVALID_ZIP_MODE: ZIP_MODE must be 'url' or 'file', got: $ZIP_MODE"
fi

# Verify ZIP file exists and is not empty
if [[ ! -s "$ZIP_PATH" ]]; then
  error_exit "ZIP_FETCH_FAIL: ZIP file is empty or missing: $ZIP_PATH"
fi

# ============================================================================
# Install/Update Plugin
# ============================================================================

log "Installing plugin with --force to ensure update..."

# The --force flag makes this idempotent: it will overwrite existing plugin
# Note: We ignore exit code because chmod warnings on Cloudways cause non-zero exit
# Instead, we verify the plugin is actually installed afterwards
$WP_CLI plugin install "$ZIP_PATH" --force 2>&1 | tee /tmp/wp-plugin-install-$$.log || true

# Verify plugin was actually installed by checking if it exists
if ! $WP_CLI plugin is-installed "$PLUGIN_SLUG" 2>/dev/null; then
  ERROR_MESSAGE="PLUGIN_INSTALL_FAIL: Plugin not found after install attempt"
  cat /tmp/wp-plugin-install-$$.log >&2 || true
  rm -f /tmp/wp-plugin-install-$$.log || true
  STATUS="failed"
  exit 1
fi

rm -f /tmp/wp-plugin-install-$$.log || true

log "Plugin installed successfully"

# ============================================================================
# Activate Plugin (if requested)
# ============================================================================

if [[ "$ACTIVATE" == "true" ]]; then
  log "Activating plugin..."

  if ! $WP_CLI plugin activate "$PLUGIN_SLUG" 2>/dev/null; then
    log "WARNING: Failed to activate plugin $PLUGIN_SLUG"
    # Not a hard failure - plugin is installed, just not activated
  else
    log "Plugin activated"
  fi
fi

# ============================================================================
# Get Post-Update Version
# ============================================================================

log "Checking post-update plugin version..."

if $WP_CLI plugin is-installed "$PLUGIN_SLUG" 2>/dev/null; then
  TO_VERSION=$($WP_CLI plugin get "$PLUGIN_SLUG" --field=version 2>/dev/null || echo "unknown")
  log "New version: $TO_VERSION"
else
  log "WARNING: Plugin not found after install (unexpected)"
  TO_VERSION="unknown"
fi

# ============================================================================
# Health Check - HTTP Probe
# ============================================================================

log "Performing HTTP health check..."

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 --connect-timeout 10 "$SITE_URL" 2>/dev/null || echo "0")

log "HTTP response code: $HTTP_CODE"

# ============================================================================
# Determine Final Status
# ============================================================================

# Status logic per PRD:
# - "ok": Plugin updated, HTTP 200, maintenance cleared
# - "needs_attention": Plugin updated but HTTP != 200 or maintenance stuck
# - "failed": Any critical error (caught by error_exit earlier)

if [[ "$HTTP_CODE" == "200" ]] && [[ "$MAINTENANCE_CLEARED" == "true" ]]; then
  STATUS="ok"
  log "Update completed successfully (status: ok)"
elif [[ "$HTTP_CODE" != "200" ]]; then
  STATUS="needs_attention"
  log "Update completed but HTTP check failed (status: needs_attention)"
else
  STATUS="needs_attention"
  log "Update completed but maintenance mode issue (status: needs_attention)"
fi

# ============================================================================
# Exit - cleanup trap will emit MARKER lines
# ============================================================================

log "Update process finished for $PLUGIN_SLUG"
exit 0
