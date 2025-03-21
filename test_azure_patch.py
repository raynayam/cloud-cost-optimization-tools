#!/usr/bin/env python
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
