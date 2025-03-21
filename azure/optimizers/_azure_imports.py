"""
Azure imports and utility functions for dealing with possible import errors.
"""

import os
import sys
import importlib.util
import logging

# Check if Azure modules are installed
_azure_imports_successful = True
_import_error = None

def check_module_installed(module_name):
    """Check if a Python module is installed and can be imported."""
    try:
        spec = importlib.util.find_spec(module_name)
        return spec is not None
    except ModuleNotFoundError:
        return False

# Try to import Azure modules
try:
    if check_module_installed('azure.identity'):
        from azure.identity import DefaultAzureCredential, ClientSecretCredential
    else:
        _azure_imports_successful = False
        _import_error = "azure.identity package not found"
        
    if check_module_installed('azure.mgmt.compute'):
        from azure.mgmt.compute import ComputeManagementClient
    else:
        _azure_imports_successful = False
        _import_error = "azure.mgmt.compute package not found"
        
    if check_module_installed('azure.mgmt.monitor'):
        from azure.mgmt.monitor import MonitorManagementClient
    else:
        _azure_imports_successful = False
        _import_error = "azure.mgmt.monitor package not found"
        
    if check_module_installed('azure.core.exceptions'):
        from azure.core.exceptions import HttpResponseError
    else:
        _azure_imports_successful = False
        _import_error = "azure.core.exceptions package not found"
        
except ImportError as e:
    _azure_imports_successful = False
    _import_error = str(e)

def get_import_status():
    """Return the status of Azure imports."""
    return _azure_imports_successful, _import_error 