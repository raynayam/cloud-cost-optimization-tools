#!/usr/bin/env python
"""
Test script to verify imports are working correctly for the Cloud Cost Optimization Tools.
"""

try:
    print("Testing boto3 import...")
    import boto3
    print("✓ boto3 imported successfully")
except ImportError as e:
    print(f"✗ Failed to import boto3: {e}")

try:
    print("\nTesting azure imports...")
    try:
        from azure.identity import DefaultAzureCredential, ClientSecretCredential
        print("✓ azure.identity imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import azure.identity: {e}")
        print("Trying mini-SDK fallback...")
        try:
            from azure_mini_sdk import DefaultAzureCredential, ClientSecretCredential
            print("✓ azure.identity imported from mini-SDK (mock implementation)")
        except ImportError as mini_e:
            print(f"✗ Failed to import mini-SDK: {mini_e}")
    
    try:
        from azure.mgmt.compute import ComputeManagementClient
        print("✓ azure.mgmt.compute imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import azure.mgmt.compute: {e}")
        print("Trying mini-SDK fallback...")
        try:
            from azure_mini_sdk import ComputeManagementClient
            print("✓ azure.mgmt.compute imported from mini-SDK (mock implementation)")
        except ImportError as mini_e:
            print(f"✗ Failed to import mini-SDK: {mini_e}")
    
    try:
        from azure.mgmt.monitor import MonitorManagementClient
        print("✓ azure.mgmt.monitor imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import azure.mgmt.monitor: {e}")
        print("Trying mini-SDK fallback...")
        try:
            from azure_mini_sdk import MonitorManagementClient
            print("✓ azure.mgmt.monitor imported from mini-SDK (mock implementation)")
        except ImportError as mini_e:
            print(f"✗ Failed to import mini-SDK: {mini_e}")
    
    try:
        from azure.mgmt.costmanagement import CostManagementClient
        print("✓ azure.mgmt.costmanagement imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import azure.mgmt.costmanagement: {e}")
    
    try:
        from azure.core.exceptions import HttpResponseError
        print("✓ azure.core.exceptions imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import azure.core.exceptions: {e}")
        print("Trying mini-SDK fallback...")
        try:
            from azure_mini_sdk import HttpResponseError
            print("✓ azure.core.exceptions imported from mini-SDK (mock implementation)")
        except ImportError as mini_e:
            print(f"✗ Failed to import mini-SDK: {mini_e}")
except ImportError as e:
    print(f"✗ Failed to import Azure modules: {e}")

try:
    print("\nTesting other common imports...")
    import pytest
    print("✓ pytest imported successfully")
    
    import pandas
    print("✓ pandas imported successfully")
    
    import matplotlib.pyplot as plt
    print("✓ matplotlib imported successfully")
    
    import yaml
    print("✓ yaml imported successfully")
    
    from rich.console import Console
    print("✓ rich imported successfully")
except ImportError as e:
    print(f"✗ Failed to import: {e}")

print("\nAll import tests completed.") 