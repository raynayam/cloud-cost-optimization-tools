#!/usr/bin/env python
"""
Diagnostic script for Azure SDK issues.
"""

import os
import sys
import pkg_resources
import subprocess
import importlib.util
from pprint import pprint

def print_section(title):
    """Print a section title."""
    print("\n" + "=" * 60)
    print(f" {title} ".center(60, "="))
    print("=" * 60 + "\n")

def check_package_installed(package_name):
    """Check if a package is installed and return its version."""
    try:
        return pkg_resources.get_distribution(package_name).version
    except pkg_resources.DistributionNotFound:
        return False

def check_module_importable(module_name):
    """Check if a module can be imported."""
    try:
        importlib.import_module(module_name)
        return True
    except ImportError as e:
        return str(e)

def try_to_fix():
    """Attempt to fix common Azure SDK issues."""
    print_section("FIX ATTEMPT")
    
    print("Attempting to reinstall key Azure packages...")
    packages = [
        "azure-identity",
        "azure-mgmt-compute",
        "azure-mgmt-monitor",
        "azure-core"
    ]
    
    for package in packages:
        print(f"\nReinstalling {package}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--force-reinstall", package])
            print(f"✓ Successfully reinstalled {package}")
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to reinstall {package}: {e}")

def main():
    """Main diagnostic function."""
    print_section("AZURE SDK DIAGNOSTIC TOOL")
    print("This script will help diagnose issues with the Azure SDK installation.\n")
    
    # Check Python environment
    print_section("PYTHON ENVIRONMENT")
    print(f"Python version: {sys.version}")
    print(f"Python executable: {sys.executable}")
    print(f"In virtual environment: {hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)}")
    
    # Check Azure packages
    print_section("AZURE PACKAGES")
    azure_packages = [
        "azure-identity",
        "azure-mgmt-compute",
        "azure-mgmt-monitor",
        "azure-mgmt-costmanagement",
        "azure-mgmt-resource",
        "azure-core",
        "azure-cli-core",
        "msrestazure"
    ]
    
    for package in azure_packages:
        version = check_package_installed(package)
        status = f"✓ {version}" if version else "✗ Not installed"
        print(f"{package.ljust(30)} {status}")
    
    # Check module imports
    print_section("MODULE IMPORTS")
    azure_modules = [
        "azure.identity",
        "azure.mgmt.compute",
        "azure.mgmt.monitor",
        "azure.core.exceptions",
        "azure.mgmt.costmanagement"
    ]
    
    for module in azure_modules:
        status = check_module_importable(module)
        if status is True:
            print(f"{module.ljust(30)} ✓ Importable")
        else:
            print(f"{module.ljust(30)} ✗ Import failed: {status}")
    
    # Check sys.path
    print_section("SYSTEM PATH")
    for i, path in enumerate(sys.path):
        print(f"{i}: {path}")
    
    # Check for conflicting packages
    print_section("POTENTIAL CONFLICTS")
    try:
        site_packages = [p for p in sys.path if "site-packages" in p]
        if site_packages:
            python_path = site_packages[0]
            azure_dirs = []
            
            print(f"Checking for conflicts in: {python_path}")
            
            if os.path.exists(python_path):
                azure_dirs = [d for d in os.listdir(python_path) if d.startswith("azure") or "azure" in d]
                
            print("\nAzure-related directories and packages:")
            for d in sorted(azure_dirs):
                print(f" - {d}")
        
    except Exception as e:
        print(f"Error checking for conflicts: {e}")
    
    # Offer to fix
    print_section("RECOMMENDATION")
    answer = input("Would you like to attempt to fix the Azure SDK installation? (y/n): ")
    if answer.lower() == "y":
        try_to_fix()
    
    print("\nDiagnostic complete. If issues persist, consider recreating your virtual environment and reinstalling packages.")

if __name__ == "__main__":
    main() 