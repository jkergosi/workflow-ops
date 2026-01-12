"""
Fix Corrupted Python Packages

This script identifies and removes corrupted package directories (those starting with ~)
from the Python site-packages directory, then reinstalls the required packages.

WARNING: Run this script with caution and make sure you have a backup of your environment.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path


def get_site_packages_path():
    """Get the site-packages directory path."""
    # Get the site-packages path from sys.path
    for path in sys.path:
        if 'site-packages' in path and os.path.exists(path):
            return Path(path)
    return None


def find_corrupted_packages(site_packages_path):
    """Find all corrupted package directories (starting with ~)."""
    corrupted = []

    if not site_packages_path or not site_packages_path.exists():
        print(f"Site-packages path not found or doesn't exist: {site_packages_path}")
        return corrupted

    print(f"\nScanning: {site_packages_path}")
    print("-" * 80)

    for item in site_packages_path.iterdir():
        if item.is_dir() and item.name.startswith('~'):
            corrupted.append(item)
            print(f"Found corrupted package: {item.name}")

    return corrupted


def remove_corrupted_packages(corrupted_packages, dry_run=True):
    """Remove corrupted package directories."""
    if not corrupted_packages:
        print("\nNo corrupted packages found!")
        return

    print(f"\n{'DRY RUN - ' if dry_run else ''}Removing {len(corrupted_packages)} corrupted package(s):")
    print("-" * 80)

    for package_path in corrupted_packages:
        try:
            print(f"{'[DRY RUN] Would remove' if dry_run else 'Removing'}: {package_path}")
            if not dry_run:
                if package_path.is_dir():
                    shutil.rmtree(package_path)
                else:
                    package_path.unlink()
                print(f"✓ Successfully removed: {package_path.name}")
        except Exception as e:
            print(f"✗ Error removing {package_path.name}: {e}")


def reinstall_packages(requirements_file=None):
    """Reinstall packages from requirements.txt."""
    if not requirements_file:
        requirements_file = Path(__file__).parent / "requirements.txt"

    if not requirements_file.exists():
        print(f"\nRequirements file not found: {requirements_file}")
        print("Skipping package reinstallation.")
        return

    print(f"\nReinstalling packages from: {requirements_file}")
    print("-" * 80)

    try:
        # First, upgrade pip
        print("Upgrading pip...")
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
                      check=True, capture_output=True, text=True)

        # Then reinstall packages
        print("Reinstalling packages...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
            check=True, capture_output=True, text=True
        )
        print("✓ Packages reinstalled successfully!")
        if result.stdout:
            print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"✗ Error reinstalling packages: {e}")
        if e.stderr:
            print(e.stderr)


def main():
    """Main function to fix corrupted packages."""
    print("=" * 80)
    print("Python Package Corruption Fix Utility")
    print("=" * 80)

    # Get site-packages path
    site_packages = get_site_packages_path()
    if not site_packages:
        print("Error: Could not find site-packages directory!")
        return 1

    # Find corrupted packages
    corrupted = find_corrupted_packages(site_packages)

    if not corrupted:
        print("\n✓ No corrupted packages found! Your environment is clean.")
        return 0

    # Show summary
    print(f"\n{'=' * 80}")
    print(f"Found {len(corrupted)} corrupted package(s)")
    print(f"{'=' * 80}")

    # Ask for confirmation
    print("\nOptions:")
    print("1. Dry run (show what would be deleted)")
    print("2. Remove corrupted packages only")
    print("3. Remove corrupted packages and reinstall from requirements.txt")
    print("4. Exit")

    choice = input("\nEnter your choice (1-4): ").strip()

    if choice == "1":
        print("\n--- DRY RUN MODE ---")
        remove_corrupted_packages(corrupted, dry_run=True)
    elif choice == "2":
        confirm = input("\nAre you sure you want to remove these packages? (yes/no): ")
        if confirm.lower() == "yes":
            remove_corrupted_packages(corrupted, dry_run=False)
            print("\n✓ Cleanup complete!")
        else:
            print("Operation cancelled.")
    elif choice == "3":
        confirm = input("\nAre you sure you want to remove and reinstall? (yes/no): ")
        if confirm.lower() == "yes":
            remove_corrupted_packages(corrupted, dry_run=False)
            reinstall_packages()
            print("\n✓ Cleanup and reinstallation complete!")
        else:
            print("Operation cancelled.")
    elif choice == "4":
        print("Exiting...")
        return 0
    else:
        print("Invalid choice. Exiting...")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
