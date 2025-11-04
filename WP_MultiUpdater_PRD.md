# ProjectA WP Multi-Updater (Option A — WP-CLI over SSH) PRD

## 1) Overview
A local command-line tool to update premium (ZIP) WordPress plugins across ~50+ sites via SSH using WP-CLI, with safety (DB backup, maintenance cleanup), verification (pre/post version), robust logging, and retryable results. Supports both one-off and CSV batches. Produces a report and exit codes suitable for CI.

## 2) Personas
- **Operator (Paul / DevOps):** runs updates from macOS terminal/VS Code, monitors output, re-runs failures.
- **Developer:** extends tool, adds site(s), adds checks, tweaks concurrency.
- **Stakeholder (PM/CEO):** wants a simple report of success/failures.

## 3) Goals
- Update one or more plugins by pushing ZIPs to multiple sites over SSH.
- Safety: DB export pre-update; force-clear maintenance mode on exit.
- Verification: confirm plugin version change and basic HTTP reachability.
- Observability: per-task structured results (SQLite + CSV + Markdown summary).
- Reliability: mark failures for retry; idempotent re-runs.

### Non-Goals
- Building an agent plugin or REST endpoint (that’s Option B).
- Managing WP license keys.
- Full rollback automation (manual restore supported via generated backups).

## 4) Constraints & Assumptions
- SSH key access to each host; WP-CLI installed on each site.
- Operator can `scp` a ZIP or provide a signed/public URL to the ZIP.
- Sites may reside on Cloudways/Vultr/etc. with per-app paths.
- Python 3.10+ environment locally.

## 5) High-Level Architecture
- **orchestrator.py**: main CLI; reads inventory + job; coordinates SSH/SCP, runs remote script, records results, renders reports, supports retries and concurrency.
- **remote-update.sh**: idempotent bash script run on each host; executes WP-CLI flow; prints machine-parsable markers for version, status, and checks.
- **results.sqlite**: persistent run/task storage.
- **reports/**: human-readable CSV/Markdown per run.

(Local) orchestrator.py
   ├─ read sites.yaml & plugins.csv
   ├─ for each (site x plugin):
   │    ├─ scp ZIP (if local)
   │    └─ ssh: cd to app path → run remote-update.sh with env vars
   ├─ parse stdout/stderr → save to SQLite
   ├─ generate CSV/MD report
   └─ exit non-zero if any failures (for CI)

## 6) Data & Files

### Repo Layout
```
wp-multi-updater/
├─ orchestrator.py
├─ scripts/
│  └─ remote-update.sh
├─ inventory/
│  └─ sites.yaml
├─ jobs/
│  ├─ plugins.csv
│  └─ example.csv
├─ reports/
├─ state/
│  └─ results.sqlite
├─ .env.sample
├─ requirements.txt
└─ README.md
```

### inventory/sites.yaml
```yaml
- name: britt-prod
  host: ssh.brittfest.org
  user: appuser
  path: /home/xxx/htdocs/public_html
  url: https://www.brittfest.org
  wp_cli: wp
- name: laclinica-prod
  host: ssh.laclinica.org
  user: appuser
  path: /home/xxx/htdocs/public_html
  url: https://www.laclinica.org
  wp_cli: wp
```

### jobs/plugins.csv
```
plugin_slug,zip_source,type,activate
the-events-calendar-pro,https://signed-s3-url/tec-pro-6.5.4.zip,url,false
document-library-pro,/Users/paul/Downloads/dlp-3.5.1.zip,file,false
```

## 7) CLI Spec
```
usage: orchestrator.py --sites inventory/sites.yaml --plugins jobs/plugins.csv
                       [--concurrency 10] [--dry-run] [--retry-failed]
                       [--only-sites SITE1,SITE2] [--only-plugins SLUG]
                       [--timeout-sec 900] [--report-dir reports]
```

## 8) Remote Script Spec
**Inputs (ENV)**
- PLUGIN_SLUG
- ZIP_MODE
- ZIP_VALUE
- ACTIVATE
- SITE_URL

**Steps**
1. `set -euo pipefail`; trap maintenance cleanup.
2. `wp core is-installed` else exit 20.
3. Ensure maintenance off.
4. Get pre-version.
5. DB export backup.
6. Download/expect ZIP.
7. Install/update plugin.
8. Activate if requested.
9. Get post-version.
10. Health probe with curl.
11. Emit MARKER lines.

## 9) Transport & Concurrency
- System ssh/scp via subprocess.
- Concurrency default 10.

## 10) Error Taxonomy
SSH_CONNECT_FAIL, SCP_FAIL, WP_NOT_INSTALLED, ZIP_FETCH_FAIL, PLUGIN_INSTALL_FAIL, MAINTENANCE_STUCK, HTTP_UNHEALTHY, UNKNOWN_EXCEPTION

## 11) Security
- SSH keys only; no passwords.
- .env for optional tokens.
- Redact URLs in logs.

## 12) Observability
- Structured log lines.
- Raw stdout/stderr stored per task.
- Slack webhook future option.

## 13) Retry Semantics
- Retry failed/needs_retry tasks.

## 14) Acceptance Criteria
AC1–AC6 (see chat spec).

## 15) Test Plan
Unit mock ssh/scp, local E2E on staging, concurrency test, maintenance guard.

## 16) Rollout
Test on 3 sites, expand to 50+.

## 17) Future Enhancements
Web UI, Slack alerts, S3 backups, rollback tar.

---

## Initial Codex CLI Prompt
```
You are building a local Python tool called “ProjectA WP Multi-Updater” that updates premium WordPress plugins across many sites via SSH using WP-CLI. Follow this PRD and create production-quality code and docs.

Key requirements:
- Python 3.10+, shell out to system ssh/scp and wp.
- Concurrency with ThreadPoolExecutor or asyncio subprocess.
- Files: orchestrator.py, scripts/remote-update.sh, inventory/sites.yaml, jobs/example.csv, state/results.sqlite, reports/, requirements.txt, .env.sample, README.md.
- CLI flags: --sites, --plugins, --concurrency, --dry-run, --retry-failed, --only-sites, --only-plugins, --timeout-sec, --report-dir, --ssh-opts.
- SQLite schema: runs/tasks with fields per PRD.
- remote-update.sh: wp pre-flight, DB backup, plugin install, activation, verify, emit MARKER lines.
- Robust logging, error handling, redacted URLs.
- Reports: CSV + Markdown, exit 0 if all OK, else 1.

Start by scaffolding the repo structure and README.md with Quick Start, then build remote-update.sh, then orchestrator.py (single site), add concurrency and reports. Validate AC1–AC6 at end.
```
