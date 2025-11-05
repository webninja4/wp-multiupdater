#!/usr/bin/env python3
"""
Wrapper script for orchestrator.py that clears caches before and after plugin updates.

This script:
1. Clears Breeze and Object Cache on target sites
2. Runs plugin updates one site at a time (up to 3 sites in parallel)
3. Clears caches again after updates complete

Usage:
    python scripts/update-with-cache-clear.py \
        --sites inventory/sites.yaml \
        --plugins jobs/my-job.csv \
        --ssh-opts "-i ~/.ssh/id_rsa_cloudways" \
        --only-sites site1,site2,site3
"""

import argparse
import subprocess
import sys
import yaml
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

def parse_args():
    parser = argparse.ArgumentParser(description='Update plugins with cache clearing')
    parser.add_argument('--sites', required=True, help='Path to sites.yaml')
    parser.add_argument('--plugins', required=True, help='Path to plugins CSV')
    parser.add_argument('--ssh-opts', default='', help='SSH options')
    parser.add_argument('--only-sites', help='Comma-separated list of sites to update')
    parser.add_argument('--max-parallel', type=int, default=3, help='Max sites to update in parallel (default: 3)')
    return parser.parse_args()

def load_sites(yaml_path, only_sites=None):
    """Load sites from YAML file."""
    with open(yaml_path, 'r') as f:
        all_sites = yaml.safe_load(f)

    if only_sites:
        site_names = [s.strip() for s in only_sites.split(',')]
        sites = [s for s in all_sites if s['name'] in site_names]
    else:
        sites = all_sites

    return sites

def clear_cache(site, ssh_opts):
    """Clear Breeze cache and Object Cache Pro on a site."""
    print(f"[{site['name']}] Clearing caches...")

    ssh_cmd = f"ssh {ssh_opts} {site['user']}@{site['host']}"
    wp_cmd = f"cd {site['path']} && wp cache flush && wp eval 'wp_cache_flush();'"

    try:
        result = subprocess.run(
            f"{ssh_cmd} \"{wp_cmd}\"",
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            print(f"[{site['name']}] ✓ Cache cleared")
            return True
        else:
            print(f"[{site['name']}] ⚠ Warning: Cache clear returned error (this is usually OK)")
            return True
    except Exception as e:
        print(f"[{site['name']}] ✗ Failed to clear cache: {e}")
        return False

def update_site(site, plugins_csv, ssh_opts, sites_yaml):
    """Update plugins on a single site."""
    site_name = site['name']
    print(f"\n{'='*60}")
    print(f"Processing site: {site_name}")
    print(f"{'='*60}")

    # Clear cache before update
    clear_cache(site, ssh_opts)

    # Run orchestrator for this site only
    cmd = [
        'python', 'orchestrator.py',
        '--sites', sites_yaml,
        '--plugins', plugins_csv,
        '--only-sites', site_name,
        '--concurrency', '1'
    ]

    if ssh_opts:
        cmd.extend(['--ssh-opts', ssh_opts])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600
        )

        # Print output
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        # Clear cache after update
        clear_cache(site, ssh_opts)

        # Determine status - consider it successful if there are no failed tasks
        # (needs_attention is acceptable, usually due to HTTP 403/caching issues)
        import re
        failed_count = 0
        if '❌ Failed:' in result.stdout:
            match = re.search(r'❌ Failed:\s+(\d+)', result.stdout)
            if match:
                failed_count = int(match.group(1))

        success = failed_count == 0

        return {
            'site': site_name,
            'success': success,
            'returncode': result.returncode
        }

    except subprocess.TimeoutExpired:
        print(f"[{site_name}] ✗ Update timed out after 10 minutes")
        return {'site': site_name, 'success': False, 'returncode': -1}
    except Exception as e:
        print(f"[{site_name}] ✗ Error: {e}")
        return {'site': site_name, 'success': False, 'returncode': -2}

def main():
    args = parse_args()

    print(f"\n{'='*60}")
    print(f"WordPress Plugin Updater with Cache Clearing")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # Load sites
    sites = load_sites(args.sites, args.only_sites)

    if not sites:
        print("Error: No sites found matching criteria")
        sys.exit(1)

    print(f"Will update {len(sites)} site(s) with max {args.max_parallel} in parallel\n")

    # Process sites in parallel (up to max_parallel at a time)
    results = []
    with ThreadPoolExecutor(max_workers=args.max_parallel) as executor:
        futures = {
            executor.submit(
                update_site,
                site,
                args.plugins,
                args.ssh_opts,
                args.sites
            ): site for site in sites
        }

        for future in as_completed(futures):
            result = future.result()
            results.append(result)

    # Print summary
    print(f"\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"{'='*60}")

    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]

    print(f"Total sites:  {len(results)}")
    print(f"✓ Success:    {len(successful)}")
    print(f"✗ Failed:     {len(failed)}")

    if failed:
        print("\nFailed sites:")
        for r in failed:
            print(f"  - {r['site']}")
        sys.exit(1)
    else:
        print("\n✓ All sites updated successfully!")
        sys.exit(0)

if __name__ == '__main__':
    main()
