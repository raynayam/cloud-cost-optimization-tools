"""
Configuration utilities for Cloud Cost Optimization Tools.
"""

import os
import yaml
from typing import Dict, Any

def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        Dict containing the configuration
        
    Raises:
        FileNotFoundError: If the configuration file doesn't exist
        yaml.YAMLError: If the YAML file is invalid
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Invalid YAML in configuration file: {str(e)}")
    
    return config

def validate_config(config: Dict[str, Any]) -> bool:
    """
    Validate the configuration structure and required fields.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        True if configuration is valid
        
    Raises:
        ValueError: If configuration is invalid
    """
    # Check for required top-level sections
    required_sections = ['general', 'aws', 'azure', 'reporting']
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Missing required configuration section: {section}")
    
    # Validate general section
    if 'output_dir' not in config['general']:
        raise ValueError("Missing 'output_dir' in general configuration")
    if 'log_level' not in config['general']:
        raise ValueError("Missing 'log_level' in general configuration")
    
    # Validate that at least one cloud provider is enabled
    if not config['aws'].get('enabled', False) and not config['azure'].get('enabled', False):
        raise ValueError("At least one cloud provider must be enabled")
    
    # Validate AWS configuration if enabled
    if config['aws'].get('enabled', False):
        if not ('profile' in config['aws'] or 
                ('access_key_id' in config['aws'] and 'secret_access_key' in config['aws'])):
            raise ValueError("AWS configuration must include either 'profile' or 'access_key_id' and 'secret_access_key'")
    
    # Validate Azure configuration if enabled
    if config['azure'].get('enabled', False):
        if 'auth_method' not in config['azure']:
            raise ValueError("Missing 'auth_method' in Azure configuration")
        
        if config['azure']['auth_method'] == 'service_principal':
            required_azure_fields = ['tenant_id', 'client_id', 'client_secret', 'subscription_ids']
            for field in required_azure_fields:
                if field not in config['azure']:
                    raise ValueError(f"Missing required Azure configuration for service principal: {field}")
    
    return True 