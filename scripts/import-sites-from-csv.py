#!/usr/bin/env python3
"""
import-sites-from-csv.py - Bulk import sites from CSV

Usage:
  python scripts/import-sites-from-csv.py sites-export.csv

CSV Format:
  name,host,user,path,url,wp_cli
  craterian-staging,104.207.159.106,master_beesbmscpg,/home/master/applications/xgeqcsqzqc/public_html,https://staging.craterian.org,wp
"""

import csv
import sys
import yaml
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/import-sites-from-csv.py sites.csv")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    if not csv_path.exists():
        print(f"Error: File not found: {csv_path}")
        sys.exit(1)

    # Read CSV
    sites = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            site = {
                'name': row['name'],
                'host': row['host'],
                'user': row['user'],
                'path': row['path'],
                'url': row['url'],
                'wp_cli': row.get('wp_cli', 'wp')
            }
            sites.append(site)

    print(f"Loaded {len(sites)} site(s) from {csv_path}")
    print("")

    # Show preview
    print("Sites to import:")
    for site in sites:
        print(f"  - {site['name']} ({site['url']})")

    print("")
    confirm = input("Append these sites to inventory/sites.yaml? (y/n): ")

    if confirm.lower() != 'y':
        print("Cancelled.")
        sys.exit(0)

    # Append to inventory
    inventory_path = Path(__file__).parent.parent / 'inventory' / 'sites.yaml'

    with open(inventory_path, 'a') as f:
        f.write("\n# Imported from CSV\n")
        for site in sites:
            f.write(f"\n- name: {site['name']}\n")
            f.write(f"  host: {site['host']}\n")
            f.write(f"  user: {site['user']}\n")
            f.write(f"  path: {site['path']}\n")
            f.write(f"  url: {site['url']}\n")
            f.write(f"  wp_cli: {site['wp_cli']}\n")

    print(f"✅ {len(sites)} site(s) appended to {inventory_path}")
    print("")
    print("Next step:")
    print(f"  python orchestrator.py --sites {inventory_path} --plugins jobs/example.csv --dry-run")


if __name__ == '__main__':
    main()
