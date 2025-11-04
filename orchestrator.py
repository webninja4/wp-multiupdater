#!/usr/bin/env python3
"""
orchestrator.py - WordPress Multi-Site Plugin Updater

A production-grade CLI tool for updating premium WordPress plugins across
multiple sites via SSH and WP-CLI with safety features, verification, and
comprehensive reporting.
"""

import argparse
import csv
import logging
import os
import re
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs

import yaml


# ============================================================================
# Configuration & Constants
# ============================================================================

DEFAULT_CONCURRENCY = 10
DEFAULT_TIMEOUT = 900  # 15 minutes
DEFAULT_REPORT_DIR = "reports"
DEFAULT_STATE_DIR = "state"
DB_FILE = "results.sqlite"

# Error types matching PRD
ERROR_SSH_CONNECT_FAIL = "SSH_CONNECT_FAIL"
ERROR_SCP_FAIL = "SCP_FAIL"
ERROR_WP_NOT_INSTALLED = "WP_NOT_INSTALLED"
ERROR_ZIP_FETCH_FAIL = "ZIP_FETCH_FAIL"
ERROR_PLUGIN_INSTALL_FAIL = "PLUGIN_INSTALL_FAIL"
ERROR_MAINTENANCE_STUCK = "MAINTENANCE_STUCK"
ERROR_HTTP_UNHEALTHY = "HTTP_UNHEALTHY"
ERROR_TIMEOUT = "TIMEOUT"
ERROR_UNKNOWN = "UNKNOWN_EXCEPTION"

# Status values
STATUS_OK = "ok"
STATUS_NEEDS_ATTENTION = "needs_attention"
STATUS_FAILED = "failed"


# ============================================================================
# Logging Setup
# ============================================================================

def setup_logging(level=logging.INFO):
    """Configure structured logging with timestamp and level."""
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class Site:
    """WordPress site configuration."""
    name: str
    host: str
    user: str
    path: str
    url: str
    wp_cli: str = "wp"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Site':
        """Create Site from YAML dict."""
        return cls(
            name=data['name'],
            host=data['host'],
            user=data['user'],
            path=data['path'],
            url=data['url'],
            wp_cli=data.get('wp_cli', 'wp')
        )


@dataclass
class Plugin:
    """Plugin update configuration."""
    slug: str
    zip_source: str
    type: str  # "url" or "file"
    activate: bool

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Plugin':
        """Create Plugin from CSV dict."""
        activate = str(data.get('activate', 'false')).lower() == 'true'
        return cls(
            slug=data['plugin_slug'],
            zip_source=data['zip_source'],
            type=data['type'],
            activate=activate
        )


@dataclass
class Task:
    """A single plugin update task (site x plugin)."""
    site: Site
    plugin: Plugin
    run_id: Optional[int] = None
    task_id: Optional[int] = None


@dataclass
class TaskResult:
    """Result of executing a task."""
    task: Task
    status: str
    from_version: str = "none"
    to_version: str = "none"
    backup_path: str = "none"
    http_code: str = "0"
    maintenance_cleared: str = "false"
    error_message: str = ""
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


# ============================================================================
# Database Layer
# ============================================================================

class Database:
    """SQLite database for storing run and task results."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        """Initialize database schema with runs and tasks tables."""
        conn = self._get_connection()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    total_tasks INTEGER DEFAULT 0,
                    tasks_ok INTEGER DEFAULT 0,
                    tasks_needs_attention INTEGER DEFAULT 0,
                    tasks_failed INTEGER DEFAULT 0,
                    command_args TEXT
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    site_name TEXT NOT NULL,
                    plugin_slug TEXT NOT NULL,
                    status TEXT NOT NULL,
                    from_version TEXT,
                    to_version TEXT,
                    backup_path TEXT,
                    http_code TEXT,
                    maintenance_cleared TEXT,
                    error_message TEXT,
                    stdout TEXT,
                    stderr TEXT,
                    duration_ms INTEGER,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );

                CREATE INDEX IF NOT EXISTS idx_tasks_run_id ON tasks(run_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
                CREATE INDEX IF NOT EXISTS idx_tasks_site_plugin ON tasks(site_name, plugin_slug);
            """)
            conn.commit()
        finally:
            conn.close()

    def create_run(self, command_args: str) -> int:
        """Create a new run record and return run_id."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "INSERT INTO runs (started_at, command_args) VALUES (?, ?)",
                (datetime.utcnow().isoformat(), command_args)
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def update_run(self, run_id: int, stats: Dict[str, int]):
        """Update run with final statistics."""
        conn = self._get_connection()
        try:
            conn.execute("""
                UPDATE runs
                SET ended_at = ?,
                    total_tasks = ?,
                    tasks_ok = ?,
                    tasks_needs_attention = ?,
                    tasks_failed = ?
                WHERE run_id = ?
            """, (
                datetime.utcnow().isoformat(),
                stats['total'],
                stats['ok'],
                stats['needs_attention'],
                stats['failed'],
                run_id
            ))
            conn.commit()
        finally:
            conn.close()

    def insert_task(self, run_id: int, result: TaskResult) -> int:
        """Insert a task result and return task_id."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                INSERT INTO tasks (
                    run_id, site_name, plugin_slug, status,
                    from_version, to_version, backup_path,
                    http_code, maintenance_cleared, error_message,
                    stdout, stderr, duration_ms, started_at, ended_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id,
                result.task.site.name,
                result.task.plugin.slug,
                result.status,
                result.from_version,
                result.to_version,
                result.backup_path,
                result.http_code,
                result.maintenance_cleared,
                result.error_message,
                result.stdout,
                result.stderr,
                result.duration_ms,
                result.started_at.isoformat() if result.started_at else None,
                result.ended_at.isoformat() if result.ended_at else None
            ))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_last_run_id(self) -> Optional[int]:
        """Get the most recent run_id."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT MAX(run_id) as max_id FROM runs")
            row = cursor.fetchone()
            return row['max_id'] if row['max_id'] else None
        finally:
            conn.close()

    def get_failed_tasks(self, run_id: int) -> List[Tuple[str, str]]:
        """Get list of (site_name, plugin_slug) for failed/needs_attention tasks."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                SELECT site_name, plugin_slug
                FROM tasks
                WHERE run_id = ? AND status IN (?, ?)
            """, (run_id, STATUS_FAILED, STATUS_NEEDS_ATTENTION))
            return [(row['site_name'], row['plugin_slug']) for row in cursor.fetchall()]
        finally:
            conn.close()


# ============================================================================
# Utility Functions
# ============================================================================

def redact_url(url: str) -> str:
    """Redact query strings from URLs to hide secrets in logs."""
    parsed = urlparse(url)
    if parsed.query:
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?[REDACTED]"
    return url


def parse_marker_lines(output: str) -> Dict[str, str]:
    """
    Parse MARKER lines from remote script output.

    Example:
        MARKER from_version=1.2.3
        MARKER status=ok

    Returns dict: {"from_version": "1.2.3", "status": "ok"}
    """
    markers = {}
    for line in output.split('\n'):
        if line.startswith('MARKER '):
            # Remove 'MARKER ' prefix and parse key=value
            content = line[7:].strip()
            if '=' in content:
                key, value = content.split('=', 1)
                markers[key.strip()] = value.strip()
    return markers


def load_sites(yaml_path: Path) -> List[Site]:
    """Load sites from YAML inventory file."""
    if not yaml_path.exists():
        raise FileNotFoundError(f"Sites file not found: {yaml_path}")

    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)

    if not isinstance(data, list):
        raise ValueError("Sites YAML must contain a list of site definitions")

    return [Site.from_dict(item) for item in data]


def load_plugins(csv_path: Path) -> List[Plugin]:
    """Load plugins from CSV job file."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Plugins file not found: {csv_path}")

    plugins = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            plugins.append(Plugin.from_dict(row))

    return plugins


# ============================================================================
# SSH/SCP Operations
# ============================================================================

def build_ssh_command(site: Site, ssh_opts: str = "") -> List[str]:
    """Build SSH command with standard options."""
    cmd = ['ssh']

    if ssh_opts:
        # Split ssh_opts carefully (handle quoted args)
        cmd.extend(ssh_opts.split())

    cmd.extend([
        '-o', 'BatchMode=yes',
        '-o', 'StrictHostKeyChecking=no',
        f'{site.user}@{site.host}'
    ])

    return cmd


def scp_file(site: Site, local_path: str, remote_path: str, timeout: int, ssh_opts: str = "") -> Tuple[bool, str]:
    """
    Copy file to remote site via SCP.

    Returns: (success: bool, error_message: str)
    """
    cmd = ['scp']

    if ssh_opts:
        for opt in ssh_opts.split():
            if opt.startswith('-o'):
                # Add -o options for scp
                pass
            cmd.append(opt)

    cmd.extend([
        '-o', 'BatchMode=yes',
        '-o', 'StrictHostKeyChecking=no',
        local_path,
        f'{site.user}@{site.host}:{remote_path}'
    ])

    logger.debug(f"Running SCP: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        if result.returncode != 0:
            return False, f"SCP failed: {result.stderr}"

        return True, ""

    except subprocess.TimeoutExpired:
        return False, f"SCP timeout after {timeout}s"
    except Exception as e:
        return False, f"SCP exception: {str(e)}"


def run_remote_script(
    site: Site,
    plugin: Plugin,
    timeout: int,
    ssh_opts: str = ""
) -> TaskResult:
    """
    Execute remote-update.sh on target site via SSH.

    Returns TaskResult with parsed output and status.
    """
    task = Task(site=site, plugin=plugin)
    result = TaskResult(task=task, status=STATUS_FAILED)

    started_at = datetime.utcnow()
    result.started_at = started_at

    # Build environment variables for remote script
    env_vars = {
        'PLUGIN_SLUG': plugin.slug,
        'ZIP_MODE': plugin.type,
        'ZIP_VALUE': plugin.zip_source if plugin.type == 'url' else '/tmp/plugin.zip',
        'ACTIVATE': 'true' if plugin.activate else 'false',
        'SITE_URL': site.url,
        'WP_CLI': site.wp_cli
    }

    # Read remote script
    script_path = Path(__file__).parent / 'scripts' / 'remote-update.sh'
    if not script_path.exists():
        result.error_message = "remote-update.sh script not found"
        result.status = STATUS_FAILED
        result.ended_at = datetime.utcnow()
        result.duration_ms = int((result.ended_at - started_at).total_seconds() * 1000)
        return result

    with open(script_path, 'r') as f:
        script_content = f.read()

    # Build SSH command with embedded script
    ssh_cmd = build_ssh_command(site, ssh_opts)

    # Build the full command: cd to path, export env vars, run script
    env_exports = ' '.join([f'export {k}="{v}";' for k, v in env_vars.items()])
    remote_command = f'cd {site.path} && {env_exports} bash -s'

    ssh_cmd.append(remote_command)

    logger.info(f"Executing update: {site.name} / {plugin.slug}")
    logger.debug(f"Remote command: cd {site.path} && export PLUGIN_SLUG=... bash -s")

    try:
        process = subprocess.run(
            ssh_cmd,
            input=script_content,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        ended_at = datetime.utcnow()
        result.ended_at = ended_at
        result.duration_ms = int((ended_at - started_at).total_seconds() * 1000)

        result.stdout = process.stdout
        result.stderr = process.stderr

        # Parse MARKER lines from output
        markers = parse_marker_lines(process.stdout)

        result.from_version = markers.get('from_version', 'none')
        result.to_version = markers.get('to_version', 'none')
        result.backup_path = markers.get('backup_path', 'none')
        result.http_code = markers.get('http_code', '0')
        result.maintenance_cleared = markers.get('maintenance_cleared', 'false')
        result.status = markers.get('status', STATUS_FAILED)

        if 'error' in markers:
            result.error_message = markers['error']

        # If SSH command failed but we didn't get status from markers
        if process.returncode != 0 and result.status == STATUS_FAILED:
            if not result.error_message:
                result.error_message = f"SSH command exited with code {process.returncode}"

            # Try to classify error from stderr
            stderr_lower = process.stderr.lower()
            if 'permission denied' in stderr_lower or 'connection refused' in stderr_lower:
                result.error_message = f"{ERROR_SSH_CONNECT_FAIL}: {result.error_message}"
            elif 'wp_not_installed' in process.stdout.lower():
                result.error_message = f"{ERROR_WP_NOT_INSTALLED}: {result.error_message}"

        logger.info(
            f"Task completed: {site.name}/{plugin.slug} - "
            f"Status: {result.status}, {result.from_version} -> {result.to_version}, "
            f"HTTP: {result.http_code}, Duration: {result.duration_ms}ms"
        )

        return result

    except subprocess.TimeoutExpired:
        ended_at = datetime.utcnow()
        result.ended_at = ended_at
        result.duration_ms = int((ended_at - started_at).total_seconds() * 1000)
        result.status = STATUS_FAILED
        result.error_message = f"{ERROR_TIMEOUT}: Task exceeded timeout ({timeout}s)"
        logger.error(f"Task timeout: {site.name}/{plugin.slug}")
        return result

    except Exception as e:
        ended_at = datetime.utcnow()
        result.ended_at = ended_at
        result.duration_ms = int((ended_at - started_at).total_seconds() * 1000)
        result.status = STATUS_FAILED
        result.error_message = f"{ERROR_UNKNOWN}: {str(e)}"
        logger.error(f"Task exception: {site.name}/{plugin.slug}: {e}")
        return result


def execute_task(
    task: Task,
    timeout: int,
    ssh_opts: str = ""
) -> TaskResult:
    """
    Execute a single task: SCP (if needed) + run remote script.
    """
    site = task.site
    plugin = task.plugin

    logger.info(f"Starting task: {site.name} / {plugin.slug}")

    # If plugin source is a local file, SCP it first
    if plugin.type == 'file':
        local_path = plugin.zip_source
        if not Path(local_path).exists():
            result = TaskResult(task=task, status=STATUS_FAILED)
            result.error_message = f"{ERROR_SCP_FAIL}: Local file not found: {local_path}"
            result.started_at = datetime.utcnow()
            result.ended_at = datetime.utcnow()
            result.duration_ms = 0
            logger.error(result.error_message)
            return result

        logger.info(f"Copying plugin ZIP to {site.name}:/tmp/plugin.zip")

        success, error_msg = scp_file(
            site=site,
            local_path=local_path,
            remote_path='/tmp/plugin.zip',
            timeout=timeout,
            ssh_opts=ssh_opts
        )

        if not success:
            result = TaskResult(task=task, status=STATUS_FAILED)
            result.error_message = f"{ERROR_SCP_FAIL}: {error_msg}"
            result.started_at = datetime.utcnow()
            result.ended_at = datetime.utcnow()
            result.duration_ms = 0
            logger.error(result.error_message)
            return result

    # Execute remote update script
    return run_remote_script(site, plugin, timeout, ssh_opts)


# ============================================================================
# Task Planning & Filtering
# ============================================================================

def expand_tasks(sites: List[Site], plugins: List[Plugin]) -> List[Task]:
    """Expand Cartesian product of sites x plugins."""
    tasks = []
    for site in sites:
        for plugin in plugins:
            tasks.append(Task(site=site, plugin=plugin))
    return tasks


def filter_tasks(
    tasks: List[Task],
    only_sites: Optional[List[str]] = None,
    only_plugins: Optional[List[str]] = None
) -> List[Task]:
    """Filter tasks by site names and/or plugin slugs."""
    filtered = tasks

    if only_sites:
        site_set = set(only_sites)
        filtered = [t for t in filtered if t.site.name in site_set]

    if only_plugins:
        plugin_set = set(only_plugins)
        filtered = [t for t in filtered if t.plugin.slug in plugin_set]

    return filtered


def filter_retry_tasks(
    tasks: List[Task],
    db: Database,
    last_run_id: int
) -> List[Task]:
    """Filter tasks to only those that failed in the last run."""
    failed_pairs = db.get_failed_tasks(last_run_id)
    failed_set = set(failed_pairs)

    return [
        t for t in tasks
        if (t.site.name, t.plugin.slug) in failed_set
    ]


# ============================================================================
# Reporting
# ============================================================================

def generate_reports(
    run_id: int,
    results: List[TaskResult],
    report_dir: Path
):
    """Generate CSV and Markdown reports for the run."""
    report_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    csv_path = report_dir / f"run-{timestamp}.csv"
    md_path = report_dir / f"run-{timestamp}.md"

    # Calculate statistics
    stats = {
        'total': len(results),
        'ok': sum(1 for r in results if r.status == STATUS_OK),
        'needs_attention': sum(1 for r in results if r.status == STATUS_NEEDS_ATTENTION),
        'failed': sum(1 for r in results if r.status == STATUS_FAILED)
    }

    # Generate CSV
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'site', 'plugin', 'status', 'from_version', 'to_version',
            'http_code', 'maintenance_cleared', 'duration_ms', 'error_message'
        ])

        for result in results:
            writer.writerow([
                result.task.site.name,
                result.task.plugin.slug,
                result.status,
                result.from_version,
                result.to_version,
                result.http_code,
                result.maintenance_cleared,
                result.duration_ms,
                result.error_message
            ])

    logger.info(f"CSV report written: {csv_path}")

    # Generate Markdown
    with open(md_path, 'w') as f:
        f.write(f"# WordPress Plugin Update Report\n\n")
        f.write(f"**Run ID:** {run_id}\n\n")
        f.write(f"**Timestamp:** {timestamp}\n\n")
        f.write(f"## Summary\n\n")
        f.write(f"| Status | Count |\n")
        f.write(f"|--------|-------|\n")
        f.write(f"| ✅ OK | {stats['ok']} |\n")
        f.write(f"| ⚠️  Needs Attention | {stats['needs_attention']} |\n")
        f.write(f"| ❌ Failed | {stats['failed']} |\n")
        f.write(f"| **Total** | **{stats['total']}** |\n\n")

        # Details section
        f.write(f"## Task Details\n\n")

        for status_filter, emoji in [
            (STATUS_FAILED, '❌'),
            (STATUS_NEEDS_ATTENTION, '⚠️'),
            (STATUS_OK, '✅')
        ]:
            filtered_results = [r for r in results if r.status == status_filter]
            if not filtered_results:
                continue

            f.write(f"### {emoji} {status_filter.upper().replace('_', ' ')}\n\n")

            for result in filtered_results:
                f.write(f"**{result.task.site.name}** / `{result.task.plugin.slug}`\n\n")
                f.write(f"- Version: {result.from_version} → {result.to_version}\n")
                f.write(f"- HTTP Code: {result.http_code}\n")
                f.write(f"- Maintenance Cleared: {result.maintenance_cleared}\n")
                f.write(f"- Duration: {result.duration_ms}ms\n")

                if result.error_message:
                    f.write(f"- Error: `{result.error_message}`\n")

                f.write(f"\n")

    logger.info(f"Markdown report written: {md_path}")

    return stats


# ============================================================================
# Main Orchestrator
# ============================================================================

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='WordPress Multi-Site Plugin Updater',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to preview tasks
  python orchestrator.py --sites inventory/sites.yaml --plugins jobs/plugins.csv --dry-run

  # Execute updates with 5 workers
  python orchestrator.py --sites inventory/sites.yaml --plugins jobs/plugins.csv --concurrency 5

  # Update specific sites only
  python orchestrator.py --sites inventory/sites.yaml --plugins jobs/plugins.csv --only-sites site1,site2

  # Retry failed tasks from last run
  python orchestrator.py --sites inventory/sites.yaml --plugins jobs/plugins.csv --retry-failed
        """
    )

    parser.add_argument('--sites', required=True, type=Path,
                        help='Path to sites YAML inventory file')
    parser.add_argument('--plugins', required=True, type=Path,
                        help='Path to plugins CSV job file')
    parser.add_argument('--concurrency', type=int, default=DEFAULT_CONCURRENCY,
                        help=f'Number of parallel workers (default: {DEFAULT_CONCURRENCY})')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print execution plan without running updates')
    parser.add_argument('--retry-failed', action='store_true',
                        help='Only retry failed/needs_attention tasks from last run')
    parser.add_argument('--only-sites', type=str,
                        help='Comma-separated list of site names to target')
    parser.add_argument('--only-plugins', type=str,
                        help='Comma-separated list of plugin slugs to update')
    parser.add_argument('--timeout-sec', type=int, default=DEFAULT_TIMEOUT,
                        help=f'Timeout per task in seconds (default: {DEFAULT_TIMEOUT})')
    parser.add_argument('--report-dir', type=Path, default=Path(DEFAULT_REPORT_DIR),
                        help=f'Directory for output reports (default: {DEFAULT_REPORT_DIR})')
    parser.add_argument('--ssh-opts', type=str, default="",
                        help='Additional SSH options (e.g., "-o ConnectTimeout=30")')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging')

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logging(log_level)

    logger.info("=" * 70)
    logger.info("WordPress Multi-Site Plugin Updater")
    logger.info("=" * 70)

    # Load configuration
    try:
        logger.info(f"Loading sites from: {args.sites}")
        sites = load_sites(args.sites)
        logger.info(f"Loaded {len(sites)} site(s)")

        logger.info(f"Loading plugins from: {args.plugins}")
        plugins = load_plugins(args.plugins)
        logger.info(f"Loaded {len(plugins)} plugin(s)")

    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return 1

    # Expand tasks
    tasks = expand_tasks(sites, plugins)
    logger.info(f"Expanded to {len(tasks)} total task(s)")

    # Apply filters
    only_sites_list = args.only_sites.split(',') if args.only_sites else None
    only_plugins_list = args.only_plugins.split(',') if args.only_plugins else None

    if only_sites_list or only_plugins_list:
        tasks = filter_tasks(tasks, only_sites_list, only_plugins_list)
        logger.info(f"Filtered to {len(tasks)} task(s)")

    # Handle retry mode
    db_path = Path(DEFAULT_STATE_DIR) / DB_FILE
    db = Database(db_path)

    if args.retry_failed:
        last_run_id = db.get_last_run_id()
        if last_run_id is None:
            logger.error("No previous run found for --retry-failed")
            return 1

        logger.info(f"Retrying failed tasks from run {last_run_id}")
        tasks = filter_retry_tasks(tasks, db, last_run_id)
        logger.info(f"Retrying {len(tasks)} task(s)")

    if not tasks:
        logger.warning("No tasks to execute")
        return 0

    # Dry run mode
    if args.dry_run:
        logger.info("=" * 70)
        logger.info("DRY RUN - Execution Plan")
        logger.info("=" * 70)

        for i, task in enumerate(tasks, 1):
            plugin_source = redact_url(task.plugin.zip_source)
            logger.info(
                f"{i:3d}. {task.site.name:20s} | {task.plugin.slug:30s} | "
                f"{task.plugin.type:5s} | {plugin_source}"
            )

        logger.info("=" * 70)
        logger.info(f"Total tasks: {len(tasks)}")
        logger.info(f"Concurrency: {args.concurrency}")
        logger.info(f"Timeout: {args.timeout_sec}s per task")
        logger.info("=" * 70)
        logger.info("Dry run complete. Use without --dry-run to execute.")
        return 0

    # Create run record
    command_args = ' '.join(sys.argv)
    run_id = db.create_run(command_args)
    logger.info(f"Created run {run_id}")

    # Execute tasks with concurrency
    logger.info("=" * 70)
    logger.info(f"Executing {len(tasks)} task(s) with concurrency {args.concurrency}")
    logger.info("=" * 70)

    results: List[TaskResult] = []

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        # Submit all tasks
        future_to_task = {
            executor.submit(
                execute_task,
                task,
                args.timeout_sec,
                args.ssh_opts
            ): task
            for task in tasks
        }

        # Collect results as they complete
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            try:
                result = future.result()
                results.append(result)

                # Save to database immediately
                task_id = db.insert_task(run_id, result)
                result.task.task_id = task_id

            except Exception as e:
                logger.error(f"Unexpected error processing task {task.site.name}/{task.plugin.slug}: {e}")
                # Create a failed result
                result = TaskResult(
                    task=task,
                    status=STATUS_FAILED,
                    error_message=f"{ERROR_UNKNOWN}: {str(e)}",
                    started_at=datetime.utcnow(),
                    ended_at=datetime.utcnow(),
                    duration_ms=0
                )
                results.append(result)
                db.insert_task(run_id, result)

    # Generate reports
    logger.info("=" * 70)
    logger.info("Generating reports...")
    logger.info("=" * 70)

    stats = generate_reports(run_id, results, args.report_dir)

    # Update run record with final stats
    db.update_run(run_id, stats)

    # Print summary
    logger.info("=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Total tasks:       {stats['total']}")
    logger.info(f"✅ OK:              {stats['ok']}")
    logger.info(f"⚠️  Needs Attention: {stats['needs_attention']}")
    logger.info(f"❌ Failed:          {stats['failed']}")
    logger.info("=" * 70)

    # Determine exit code
    if stats['needs_attention'] > 0 or stats['failed'] > 0:
        logger.warning("Some tasks did not complete successfully")
        return 1
    else:
        logger.info("All tasks completed successfully!")
        return 0


if __name__ == '__main__':
    sys.exit(main())
