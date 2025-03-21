"""
Azure SDK Import Patch

This module patches the sys.path to include the local Azure SDK modules.
"""

import os
import sys
import importlib.util
import types

# Add the azure_sdk directory to the path
azure_sdk_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'azure_sdk')
if azure_sdk_dir not in sys.path:
    sys.path.insert(0, azure_sdk_dir)

# Create an azure module if it doesn't exist
if 'azure' not in sys.modules:
    azure_module = types.ModuleType('azure')
    sys.modules['azure'] = azure_module

# Create a patch for the identity module
if 'azure.identity' not in sys.modules:
    if os.path.exists(os.path.join(azure_sdk_dir, 'identity')):
        identity_module = types.ModuleType('azure.identity')
        
        # Import DefaultAzureCredential and ClientSecretCredential
        identity_init_file = os.path.join(azure_sdk_dir, 'identity', '__init__.py')
        if os.path.exists(identity_init_file):
            spec = importlib.util.spec_from_file_location('azure.identity.__init__', identity_init_file)
            identity_init = importlib.util.module_from_spec(spec)
            sys.modules['azure.identity'] = identity_init
            spec.loader.exec_module(identity_init)
            
            # Copy attributes from identity_init to identity_module
            for attr_name in dir(identity_init):
                if not attr_name.startswith('_'):
                    setattr(identity_module, attr_name, getattr(identity_init, attr_name))
            
            # Add identity module to azure module
            setattr(sys.modules['azure'], 'identity', identity_module)

# Create a patch for the mgmt module
if 'azure.mgmt' not in sys.modules:
    if os.path.exists(os.path.join(azure_sdk_dir, 'mgmt')):
        mgmt_module = types.ModuleType('azure.mgmt')
        sys.modules['azure.mgmt'] = mgmt_module
        
        # Add mgmt module to azure module
        setattr(sys.modules['azure'], 'mgmt', mgmt_module)
        
        # Import compute and monitor modules
        if os.path.exists(os.path.join(azure_sdk_dir, 'mgmt', 'compute')):
            compute_init_file = os.path.join(azure_sdk_dir, 'mgmt', 'compute', '__init__.py')
            if os.path.exists(compute_init_file):
                spec = importlib.util.spec_from_file_location('azure.mgmt.compute.__init__', compute_init_file)
                compute_init = importlib.util.module_from_spec(spec)
                sys.modules['azure.mgmt.compute'] = compute_init
                spec.loader.exec_module(compute_init)
                
                # Add compute module to mgmt module
                setattr(mgmt_module, 'compute', compute_init)
        
        if os.path.exists(os.path.join(azure_sdk_dir, 'mgmt', 'monitor')):
            monitor_init_file = os.path.join(azure_sdk_dir, 'mgmt', 'monitor', '__init__.py')
            if os.path.exists(monitor_init_file):
                spec = importlib.util.spec_from_file_location('azure.mgmt.monitor.__init__', monitor_init_file)
                monitor_init = importlib.util.module_from_spec(spec)
                sys.modules['azure.mgmt.monitor'] = monitor_init
                spec.loader.exec_module(monitor_init)
                
                # Add monitor module to mgmt module
                setattr(mgmt_module, 'monitor', monitor_init)

# Create a patch for the core module
if 'azure.core' not in sys.modules:
    if os.path.exists(os.path.join(azure_sdk_dir, 'core')):
        core_module = types.ModuleType('azure.core')
        sys.modules['azure.core'] = core_module
        
        # Add core module to azure module
        setattr(sys.modules['azure'], 'core', core_module)
        
        # Import exceptions module
        if os.path.exists(os.path.join(azure_sdk_dir, 'core', 'exceptions.py')):
            exceptions_file = os.path.join(azure_sdk_dir, 'core', 'exceptions.py')
            spec = importlib.util.spec_from_file_location('azure.core.exceptions', exceptions_file)
            exceptions_module = importlib.util.module_from_spec(spec)
            sys.modules['azure.core.exceptions'] = exceptions_module
            spec.loader.exec_module(exceptions_module)
            
            # Add exceptions module to core module
            setattr(core_module, 'exceptions', exceptions_module)

print("Azure SDK patch applied successfully.")
