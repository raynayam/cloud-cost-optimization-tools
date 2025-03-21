#!/usr/bin/env python
"""
Script to diagnose and fix import issues with Azure SDK packages.
"""

import os
import sys
import subprocess
import importlib.util

def check_module_installed(module_name):
    """Check if a Python module is installed and can be imported."""
    try:
        spec = importlib.util.find_spec(module_name)
        return spec is not None
    except ModuleNotFoundError:
        return False

def install_package(package_name):
    """Install a Python package using pip."""
    print(f"Installing {package_name}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to install {package_name}: {e}")
        return False

def main():
    """Main function to check and fix Azure SDK packages."""
    print("Cloud Cost Optimization Tools - Import Diagnostic Tool")
    print("=====================================================")
    
    # Check if running in virtual environment
    in_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )
    
    if not in_venv:
        print("Warning: Not running in a virtual environment. It's recommended to use a virtual environment.")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Exiting...")
            sys.exit(1)
    
    # Check for Azure Identity
    print("\nChecking for Azure Identity package...")
    if check_module_installed("azure.identity"):
        print("✓ azure.identity is installed")
    else:
        print("✗ azure.identity is not installed")
        print("Attempting to install azure-identity...")
        if install_package("azure-identity>=1.12.0"):
            print("✓ azure-identity installed successfully")
        else:
            print("✗ Failed to install azure-identity")
    
    # Check for Azure Management packages
    required_packages = [
        ("azure.mgmt.compute", "azure-mgmt-compute>=29.1.0"),
        ("azure.mgmt.monitor", "azure-mgmt-monitor>=5.0.0"),
        ("azure.mgmt.costmanagement", "azure-mgmt-costmanagement>=3.0.0"),
        ("azure.mgmt.resource", "azure-mgmt-resource>=21.1.0"),
        ("azure.mgmt.storage", "azure-mgmt-storage>=20.1.0"),
        ("azure.mgmt.billing", "azure-mgmt-billing>=6.0.0"),
        ("azure.core", "azure-core>=1.26.0")
    ]
    
    print("\nChecking for Azure Management packages...")
    for module_name, package_name in required_packages:
        if check_module_installed(module_name):
            print(f"✓ {module_name} is installed")
        else:
            print(f"✗ {module_name} is not installed")
            print(f"Attempting to install {package_name}...")
            if install_package(package_name):
                print(f"✓ {package_name} installed successfully")
            else:
                print(f"✗ Failed to install {package_name}")
    
    # Print Python path for diagnostics
    print("\nPython Path:")
    for path in sys.path:
        print(f"  - {path}")
    
    # Try importing again to verify
    print("\nVerifying imports after installation...")
    try:
        import azure.identity
        print("✓ azure.identity imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import azure.identity: {e}")
    
    print("\nDiagnostic complete. Try running your script again.")

if __name__ == "__main__":
    main() 