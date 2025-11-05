#!/usr/bin/env python3
"""
Generate inventory/sites.yaml from Cloudways API

This script fetches all your servers and applications from Cloudways
and automatically generates a properly formatted sites.yaml inventory file.

Requirements:
  pip install requests

Usage:
  1. Set CLOUDWAYS_API_KEY and CLOUDWAYS_EMAIL environment variables (or in .env)
  2. Run: python scripts/generate_inventory_from_cloudways.py
  3. Review: inventory/sites-cloudways-auto.yaml
  4. Move to: inventory/sites.yaml (or merge with existing)
"""

import os
import sys
import time
import requests
import yaml
from pathlib import Path
from typing import Dict, List


# Load .env file if it exists
def load_env():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env()

# Cloudways API Configuration
API_BASE_URL = "https://api.cloudways.com/api/v1"
API_KEY = os.getenv("CLOUDWAYS_API_KEY")
API_EMAIL = os.getenv("CLOUDWAYS_EMAIL")


def get_access_token(email: str, api_key: str) -> str:
    """Authenticate with Cloudways API and get access token."""
    url = f"{API_BASE_URL}/oauth/access_token"
    payload = {
        "email": email,
        "api_key": api_key
    }

    print(f"Authenticating with Cloudways API...")
    response = requests.post(url, data=payload)

    if response.status_code != 200:
        print(f"Error: Failed to authenticate with Cloudways API")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        sys.exit(1)

    data = response.json()
    access_token = data.get("access_token")

    if not access_token:
        print("Error: No access token in response")
        sys.exit(1)

    print("✅ Authentication successful")
    return access_token


def get_servers(access_token: str) -> List[Dict]:
    """Fetch all servers from Cloudways."""
    url = f"{API_BASE_URL}/server"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    print(f"Fetching servers...")
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Error: Failed to fetch servers")
        print(f"Status: {response.status_code}")
        sys.exit(1)

    data = response.json()
    servers = data.get("servers", [])
    print(f"✅ Found {len(servers)} server(s)")

    return servers


def get_apps_for_server(access_token: str, server_id: str) -> List[Dict]:
    """Fetch all applications for a specific server."""
    url = f"{API_BASE_URL}/app"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    params = {
        "server_id": server_id
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code != 200:
        print(f"Warning: Failed to fetch apps for server {server_id} (HTTP {response.status_code})")
        return []

    try:
        data = response.json()
    except Exception as e:
        print(f"Warning: Failed to parse JSON for server {server_id}: {e}")
        return []

    apps = data.get("apps", [])

    return apps


def normalize_site_name(app_label: str, server_label: str) -> str:
    """Generate a clean site name for inventory."""
    # Remove special characters and make lowercase
    name = app_label.lower().replace(" ", "-").replace("_", "-")
    # Remove any non-alphanumeric except dash
    name = "".join(c for c in name if c.isalnum() or c == "-")
    return name


def generate_inventory(access_token: str) -> List[Dict]:
    """Generate complete inventory from Cloudways API."""
    servers = get_servers(access_token)
    inventory = []

    for server in servers:
        server_id = server.get("id")
        server_label = server.get("label", f"server-{server_id}")
        server_ip = server.get("public_ip")
        server_hostname = f"server-{server_id}.cloudways.com"

        print(f"\nProcessing server: {server_label} (ID: {server_id})")

        # Add delay to avoid rate limiting (Cloudways API limit)
        time.sleep(2)

        apps = get_apps_for_server(access_token, server_id)
        print(f"  Found {len(apps)} application(s)")

        for app in apps:
            app_label = app.get("label", "unknown")
            app_cname = app.get("cname", "")
            app_user = app.get("sys_user", "")
            app_path = app.get("webroot", "")

            # Determine the URL (prefer cname, fallback to app URL)
            app_url = app.get("app_url", "")
            if app_cname and app_cname != "false":
                site_url = f"https://{app_cname}"
            elif app_url:
                site_url = app_url
            else:
                site_url = f"http://{server_ip}"

            # Generate site name
            site_name = normalize_site_name(app_label, server_label)

            # Use server hostname or IP
            host = server_hostname if server_hostname else server_ip

            site_config = {
                "name": site_name,
                "host": host,
                "user": app_user,
                "path": app_path,
                "url": site_url,
                "wp_cli": "wp"
            }

            inventory.append(site_config)
            print(f"    ✅ {site_name}: {site_url}")

    return inventory


def save_inventory(inventory: List[Dict], output_path: Path):
    """Save inventory to YAML file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Add header comment
    yaml_content = "# WordPress Sites Inventory - Auto-generated from Cloudways API\n"
    yaml_content += f"# Generated: {os.popen('date').read().strip()}\n"
    yaml_content += "# \n"
    yaml_content += "# This file was automatically generated. To regenerate:\n"
    yaml_content += "#   python scripts/generate_inventory_from_cloudways.py\n"
    yaml_content += "\n"

    # Convert inventory to YAML
    yaml_content += yaml.dump(inventory, default_flow_style=False, sort_keys=False)

    with open(output_path, "w") as f:
        f.write(yaml_content)

    print(f"\n✅ Inventory written to: {output_path}")
    print(f"   Total sites: {len(inventory)}")


def main():
    """Main execution."""
    print("=" * 70)
    print("Cloudways Inventory Generator")
    print("=" * 70)

    # Check for API credentials
    if not API_KEY or not API_EMAIL:
        print("\nError: Missing Cloudways API credentials")
        print("\nPlease set environment variables:")
        print("  export CLOUDWAYS_API_KEY='your-api-key'")
        print("  export CLOUDWAYS_EMAIL='your-email@example.com'")
        print("\nOr add to .env file:")
        print("  CLOUDWAYS_API_KEY=your-api-key")
        print("  CLOUDWAYS_EMAIL=your-email@example.com")
        sys.exit(1)

    # Authenticate
    access_token = get_access_token(API_EMAIL, API_KEY)

    # Generate inventory
    inventory = generate_inventory(access_token)

    if not inventory:
        print("\n⚠️  No applications found. Check your API credentials or server setup.")
        sys.exit(1)

    # Save to file
    output_path = Path(__file__).parent.parent / "inventory" / "sites-cloudways-auto.yaml"
    save_inventory(inventory, output_path)

    print("\n" + "=" * 70)
    print("Next steps:")
    print("=" * 70)
    print("1. Review the generated inventory:")
    print(f"   cat {output_path}")
    print("\n2. If it looks good, replace your main inventory:")
    print(f"   mv {output_path} inventory/sites.yaml")
    print("\n3. Or merge with existing inventory:")
    print(f"   cat {output_path} >> inventory/sites.yaml")
    print("\n4. Run a dry-run to verify:")
    print("   python orchestrator.py --sites inventory/sites.yaml --plugins jobs/plugins.csv --dry-run")
    print("=" * 70)


if __name__ == "__main__":
    main()
