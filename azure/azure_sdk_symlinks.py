#!/usr/bin/env python
"""
Script to create symbolic links to Azure SDK modules within the project structure.
This helps resolve import issues when the regular Python path is not working correctly.
"""

import os
import sys
import shutil
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger('azure_sdk_symlinks')

def is_venv():
    """Check if running in a virtual environment."""
    return hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)

def main():
    """Set up symlinks to Azure SDK modules."""
    logger.info("Azure SDK Symlinks Setup Tool")
    logger.info("============================")

    # Check if we are in a virtual environment
    if not is_venv():
        logger.warning("Not running in a virtual environment.")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            logger.info("Exiting...")
            sys.exit(1)
    
    # Find the site-packages directory
    site_packages = None
    for path in sys.path:
        if 'site-packages' in path and os.path.exists(path):
            site_packages = path
            break
    
    if not site_packages:
        logger.error("Could not find site-packages directory. Exiting.")
        sys.exit(1)
    
    logger.info(f"Found site-packages directory: {site_packages}")
    
    # Check if Azure module exists in site-packages
    azure_source = os.path.join(site_packages, 'azure')
    if not os.path.exists(azure_source):
        logger.error(f"Azure module not found in {site_packages}")
        logger.error("Please install the Azure SDK packages first, then run this script.")
        sys.exit(1)
    
    logger.info("Found Azure SDK modules in site-packages.")
    
    # Create a local copy of the required modules
    project_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(project_dir)
    azure_local_dir = os.path.join(parent_dir, 'azure_sdk')
    
    # Create the local azure_sdk directory if it doesn't exist
    if not os.path.exists(azure_local_dir):
        os.makedirs(azure_local_dir, exist_ok=True)
        logger.info(f"Created directory: {azure_local_dir}")
    
    # Create an __init__.py file in the azure_sdk directory
    with open(os.path.join(azure_local_dir, '__init__.py'), 'w') as f:
        f.write('# Azure SDK local package\n')
    
    # Create symlinks to the necessary Azure modules
    modules_to_link = ['identity', 'mgmt', 'core']
    
    for module in modules_to_link:
        source = os.path.join(azure_source, module)
        target = os.path.join(azure_local_dir, module)
        
        if not os.path.exists(source):
            logger.warning(f"Source module not found: {source}")
            continue
        
        # Remove existing link/directory if it exists
        if os.path.exists(target):
            if os.path.islink(target):
                os.unlink(target)
            elif os.path.isdir(target):
                shutil.rmtree(target)
            else:
                os.remove(target)
        
        # Create the symlink
        try:
            os.symlink(source, target, target_is_directory=True)
            logger.info(f"Created symlink: {target} -> {source}")
        except OSError as e:
            logger.error(f"Failed to create symlink {target}: {e}")
            # Try copying instead
            try:
                shutil.copytree(source, target)
                logger.info(f"Copied directory: {source} -> {target}")
            except Exception as e:
                logger.error(f"Failed to copy directory {source}: {e}")
    
    # Create a patch for imports
    patch_file = os.path.join(parent_dir, 'azure_sdk_patch.py')
    with open(patch_file, 'w') as f:
        f.write('''"""
Azure SDK Import Patch

This module patches the sys.path to include the local Azure SDK modules.
"""

import os
import sys

# Add the azure_sdk directory to the path
azure_sdk_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'azure_sdk')
if azure_sdk_dir not in sys.path:
    sys.path.insert(0, azure_sdk_dir)

# Create aliases to make imports work
import azure_sdk.identity as identity
import azure_sdk.mgmt as mgmt
import azure_sdk.core as core

# Patch the azure namespace
import sys
if 'azure' not in sys.modules:
    import types
    azure = types.ModuleType('azure')
    azure.identity = identity
    azure.mgmt = mgmt
    azure.core = core
    sys.modules['azure'] = azure
    sys.modules['azure.identity'] = identity
    sys.modules['azure.mgmt'] = mgmt
    sys.modules['azure.core'] = core
''')
    logger.info(f"Created patch file: {patch_file}")
    
    # Create a test script
    test_file = os.path.join(parent_dir, 'test_azure_patch.py')
    with open(test_file, 'w') as f:
        f.write('''#!/usr/bin/env python
"""
Test script for the Azure SDK patch.
"""

import sys
print("Testing Azure SDK patch...")

try:
    import azure_sdk_patch
    print("✓ Patch imported successfully")
except ImportError as e:
    print(f"✗ Failed to import patch: {e}")

try:
    from azure.identity import DefaultAzureCredential
    print("✓ DefaultAzureCredential imported successfully")
except ImportError as e:
    print(f"✗ Failed to import DefaultAzureCredential: {e}")

try:
    from azure.mgmt.compute import ComputeManagementClient
    print("✓ ComputeManagementClient imported successfully")
except ImportError as e:
    print(f"✗ Failed to import ComputeManagementClient: {e}")

try:
    from azure.core.exceptions import HttpResponseError
    print("✓ HttpResponseError imported successfully")
except ImportError as e:
    print(f"✗ Failed to import HttpResponseError: {e}")

print("Test complete.")
''')
    logger.info(f"Created test script: {test_file}")
    os.chmod(test_file, 0o755)  # Make it executable
    
    logger.info("\nSetup complete!")
    logger.info(f"To use the patched Azure SDK, add the following line to your code:")
    logger.info("import azure_sdk_patch")
    logger.info("\nYou can test the patch by running:")
    logger.info(f"python {test_file}")

if __name__ == '__main__':
    main() 