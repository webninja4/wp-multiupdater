"""
Site Manager - CRUD operations for site inventory.

Handles loading, saving, adding, updating, and deleting sites from the
inventory/sites.yaml file.
"""

import yaml
import subprocess
from pathlib import Path
from typing import List, Dict, Optional


class SiteManager:
    """Manages WordPress site inventory operations."""

    def __init__(self, yaml_path: str = 'inventory/sites.yaml'):
        """
        Initialize the site manager.

        Args:
            yaml_path: Path to the sites YAML inventory file
        """
        self.yaml_path = Path(yaml_path)

    def load_sites(self) -> List[Dict]:
        """
        Load all sites from the YAML inventory.

        Returns:
            List of site dictionaries
        """
        if not self.yaml_path.exists():
            return []

        with open(self.yaml_path, 'r') as f:
            sites = yaml.safe_load(f) or []

        return sites if isinstance(sites, list) else []

    def save_sites(self, sites: List[Dict]) -> bool:
        """
        Save sites list to YAML inventory.

        Args:
            sites: List of site dictionaries to save

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create backup
            if self.yaml_path.exists():
                backup_path = self.yaml_path.with_suffix('.yaml.backup')
                self.yaml_path.replace(backup_path)

            # Write new file
            with open(self.yaml_path, 'w') as f:
                # Preserve formatting with comments
                yaml.dump(sites, f, default_flow_style=False, sort_keys=False)

            return True
        except Exception as e:
            print(f"Error saving sites: {e}")
            return False

    def get_site_by_name(self, name: str) -> Optional[Dict]:
        """
        Get a single site by name.

        Args:
            name: Site name to look up

        Returns:
            Site dictionary or None if not found
        """
        sites = self.load_sites()
        for site in sites:
            if site.get('name') == name:
                return site
        return None

    def add_site(self, site_data: Dict) -> tuple[bool, str]:
        """
        Add a new site to the inventory.

        Args:
            site_data: Dictionary with site configuration

        Returns:
            Tuple of (success: bool, message: str)
        """
        # Validate required fields
        required_fields = ['name', 'host', 'user', 'path', 'url', 'wp_cli']
        for field in required_fields:
            if field not in site_data or not site_data[field]:
                return False, f"Missing required field: {field}"

        # Check for duplicate name
        sites = self.load_sites()
        if any(s.get('name') == site_data['name'] for s in sites):
            return False, f"Site with name '{site_data['name']}' already exists"

        # Add site
        sites.append(site_data)

        # Save
        if self.save_sites(sites):
            return True, f"Site '{site_data['name']}' added successfully"
        else:
            return False, "Failed to save site to inventory"

    def update_site(self, site_name: str, site_data: Dict) -> tuple[bool, str]:
        """
        Update an existing site in the inventory.

        Args:
            site_name: Name of site to update
            site_data: New site configuration

        Returns:
            Tuple of (success: bool, message: str)
        """
        sites = self.load_sites()

        # Find and update site
        updated = False
        for i, site in enumerate(sites):
            if site.get('name') == site_name:
                sites[i] = site_data
                updated = True
                break

        if not updated:
            return False, f"Site '{site_name}' not found"

        # Save
        if self.save_sites(sites):
            return True, f"Site '{site_name}' updated successfully"
        else:
            return False, "Failed to save changes"

    def delete_site(self, site_name: str) -> tuple[bool, str]:
        """
        Delete a site from the inventory.

        Args:
            site_name: Name of site to delete

        Returns:
            Tuple of (success: bool, message: str)
        """
        sites = self.load_sites()

        # Filter out the site
        new_sites = [s for s in sites if s.get('name') != site_name]

        if len(new_sites) == len(sites):
            return False, f"Site '{site_name}' not found"

        # Save
        if self.save_sites(new_sites):
            return True, f"Site '{site_name}' deleted successfully"
        else:
            return False, "Failed to save changes"

    def get_sites_by_server(self) -> Dict[str, List[Dict]]:
        """
        Group sites by server (IP address).

        Returns:
            Dictionary mapping IP addresses to lists of sites
        """
        sites = self.load_sites()
        grouped = {}

        for site in sites:
            host = site.get('host', 'unknown')
            if host not in grouped:
                grouped[host] = []
            grouped[host].append(site)

        return grouped

    def test_ssh_connection(self, site: Dict, ssh_key: Optional[str] = None) -> tuple[bool, str]:
        """
        Test SSH connectivity to a site.

        Args:
            site: Site configuration dictionary
            ssh_key: Optional path to SSH key (defaults to config default)

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Build SSH command
            cmd = ['ssh']

            if ssh_key:
                cmd.extend(['-i', ssh_key])

            cmd.extend([
                '-o', 'ConnectTimeout=10',
                '-o', 'StrictHostKeyChecking=accept-new',
                f"{site['user']}@{site['host']}",
                f"cd {site['path']} && {site['wp_cli']} core version"
            ])

            # Run test
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.returncode == 0:
                version = result.stdout.strip()
                return True, f"✓ Connected successfully. WordPress version: {version}"
            else:
                return False, f"✗ Connection failed: {result.stderr.strip()}"

        except subprocess.TimeoutExpired:
            return False, "✗ Connection timed out after 15 seconds"
        except Exception as e:
            return False, f"✗ Error: {str(e)}"
