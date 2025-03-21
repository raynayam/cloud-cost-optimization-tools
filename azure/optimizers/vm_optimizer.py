"""
Azure VM optimizer module for generating Azure VM cost optimization recommendations.
"""

import logging
import os
import sys
import importlib.util
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# Add site-packages to path if running in a virtualenv
if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
    venv_site_packages = os.path.join(sys.prefix, 'lib', f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages')
    if venv_site_packages not in sys.path:
        sys.path.insert(0, venv_site_packages)

# Helper function to find a module in site-packages
def find_module(module_name):
    """Find a module in site-packages."""
    # Look for the module in site-packages
    for path in sys.path:
        if 'site-packages' in path and os.path.exists(path):
            # For top-level modules
            if '.' not in module_name:
                module_path = os.path.join(path, module_name)
                if os.path.exists(module_path):
                    return module_path
            # For packages
            else:
                parts = module_name.split('.')
                module_path = os.path.join(path, *parts)
                if os.path.exists(module_path):
                    return module_path
                # Check for .py file
                module_path = os.path.join(path, *parts[:-1], f"{parts[-1]}.py")
                if os.path.exists(module_path):
                    return module_path
    return None

# Function to load and import a module
def import_from_path(module_name, module_path):
    """Import a module from a specific path."""
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

# Initialize variables for Azure modules
DefaultAzureCredential = None
ClientSecretCredential = None
ComputeManagementClient = None
MonitorManagementClient = None
HttpResponseError = None
_azure_imports_successful = True
_import_error = None

# Try to import Azure modules
try:
    # Try normal import first
    from azure.identity import DefaultAzureCredential, ClientSecretCredential
    from azure.mgmt.compute import ComputeManagementClient
    from azure.mgmt.monitor import MonitorManagementClient
    from azure.core.exceptions import HttpResponseError
    _azure_imports_successful = True
    _import_error = None
except ImportError as e:
    _azure_imports_successful = False
    _import_error = str(e)
    
    # If normal import fails, try to import from the mini SDK
    try:
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
        from azure_mini_sdk import (
            DefaultAzureCredential,
            ClientSecretCredential,
            ComputeManagementClient,
            MonitorManagementClient,
            HttpResponseError
        )
        _azure_imports_successful = True
        logging.warning("Using Azure Mini SDK (mock implementation) - Limited functionality available")
    except ImportError as mini_e:
        _import_error = f"Failed to import Azure SDK: {e}. Also failed to import Azure Mini SDK: {mini_e}"
        logging.error(_import_error)

class VMOptimizer:
    """
    Analyzes Azure VMs and provides cost optimization recommendations.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Azure VM optimizer.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.logger = logging.getLogger("cloud-cost-optimizer")
        
        # Get VM optimization settings
        vm_config = self.config['azure']['optimization'].get('vm', {})
        self.min_cpu_utilization = vm_config.get('min_cpu_utilization', 5.0)
        self.min_uptime_hours = vm_config.get('min_uptime_hours', 168)
        
        # Initialize clients
        self._initialize_clients()
    
    def _initialize_clients(self) -> None:
        """Initialize Azure clients with appropriate credentials."""
        if not _azure_imports_successful:
            self.logger.error(f"Azure SDK import failed: {_import_error}")
            self.logger.error("Please install the Azure SDK packages with: pip install azure-identity azure-mgmt-compute azure-mgmt-monitor")
            self.compute_clients = {}
            self.monitor_clients = {}
            return
            
        azure_config = self.config['azure']
        
        # Choose authentication method
        auth_method = azure_config.get('auth_method', 'cli')
        
        try:
            if auth_method == 'cli':
                # Use Azure CLI authentication
                credential = DefaultAzureCredential()
            elif auth_method == 'service_principal':
                # Use Service Principal authentication
                credential = ClientSecretCredential(
                    tenant_id=azure_config['tenant_id'],
                    client_id=azure_config['client_id'],
                    client_secret=azure_config['client_secret']
                )
            else:
                raise ValueError(f"Unsupported authentication method: {auth_method}")
            
            # Initialize the clients
            self.compute_clients = {}
            self.monitor_clients = {}
            
            # Create clients for each subscription
            for subscription_id in azure_config.get('subscription_ids', []):
                self.compute_clients[subscription_id] = ComputeManagementClient(
                    credential, subscription_id
                )
                self.monitor_clients[subscription_id] = MonitorManagementClient(
                    credential, subscription_id
                )
            
            self.logger.info("Azure clients initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Azure clients: {str(e)}")
            self.compute_clients = {}
            self.monitor_clients = {}
    
    def generate_recommendations(self, analysis_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate Azure VM cost optimization recommendations.
        
        Args:
            analysis_data: Data from cost analysis phase
            
        Returns:
            List of VM optimization recommendations
        """
        self.logger.info("Generating Azure VM cost optimization recommendations")
        
        if not self.compute_clients:
            self.logger.error("Azure clients not initialized")
            return []
        
        all_recommendations = []
        
        # Get Azure subscription IDs
        subscription_ids = self.config['azure'].get('subscription_ids', [])
        
        for subscription_id in subscription_ids:
            try:
                # Get VMs for this subscription
                vms = self._get_vms(subscription_id)
                
                # Find underutilized VMs
                underutilized_vms = self._find_underutilized_vms(subscription_id, vms)
                all_recommendations.extend(underutilized_vms)
                
                # Find idle VMs
                idle_vms = self._find_idle_vms(subscription_id, vms)
                all_recommendations.extend(idle_vms)
                
                # Find VMs with reserved instance opportunities
                ri_opportunities = self._find_ri_opportunities(subscription_id, vms)
                all_recommendations.extend(ri_opportunities)
                
            except Exception as e:
                self.logger.error(f"Error analyzing VMs for subscription {subscription_id}: {str(e)}")
        
        # Sort recommendations by estimated savings
        all_recommendations.sort(key=lambda x: x.get('estimated_monthly_savings', 0), reverse=True)
        
        return all_recommendations
    
    def _get_vms(self, subscription_id: str) -> List[Dict[str, Any]]:
        """
        Get Azure VMs for a subscription.
        
        Args:
            subscription_id: Azure subscription ID
            
        Returns:
            List of VM details
        """
        try:
            compute_client = self.compute_clients.get(subscription_id)
            if not compute_client:
                self.logger.error(f"Compute client not found for subscription {subscription_id}")
                return []
            
            # Get all VMs in the subscription
            vms_list = list(compute_client.virtual_machines.list_all())
            
            # Get detailed information for each VM
            vms = []
            for vm in vms_list:
                # Convert Azure object to dict for easier processing
                vm_dict = {
                    'id': vm.id,
                    'name': vm.name,
                    'location': vm.location,
                    'vm_size': vm.hardware_profile.vm_size,
                    'os_type': vm.storage_profile.os_disk.os_type,
                    'resource_group': self._extract_resource_group(vm.id),
                    'tags': vm.tags if vm.tags else {},
                    'power_state': self._get_vm_power_state(subscription_id, vm.id),
                    'subscription_id': subscription_id
                }
                
                vms.append(vm_dict)
            
            return vms
        except Exception as e:
            self.logger.error(f"Error getting VMs for subscription {subscription_id}: {str(e)}")
            return []
    
    def _extract_resource_group(self, resource_id: str) -> str:
        """
        Extract resource group name from resource ID.
        
        Args:
            resource_id: Azure resource ID
            
        Returns:
            Resource group name
        """
        # Format: /subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/...
        parts = resource_id.split('/')
        if len(parts) > 4 and parts[3] == 'resourceGroups':
            return parts[4]
        return ""
    
    def _get_vm_power_state(self, subscription_id: str, vm_id: str) -> str:
        """
        Get the power state of a VM.
        
        In a real implementation, this would use the Azure Instance View API.
        For this mock-up, we'll assume all VMs are running.
        
        Args:
            subscription_id: Azure subscription ID
            vm_id: VM resource ID
            
        Returns:
            Power state string (e.g., "running", "stopped")
        """
        # Simulated response - in real implementation would use compute_client.virtual_machines.instance_view
        return "running"
    
    def _find_underutilized_vms(self, subscription_id: str, vms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Find underutilized Azure VMs based on CPU utilization.
        
        Args:
            subscription_id: Azure subscription ID
            vms: List of VM details
            
        Returns:
            List of recommendations for underutilized VMs
        """
        recommendations = []
        
        for vm in vms:
            # Only analyze running VMs
            if vm.get('power_state') != 'running':
                continue
            
            vm_name = vm.get('name')
            vm_size = vm.get('vm_size')
            resource_group = vm.get('resource_group')
            location = vm.get('location')
            
            # Get CPU utilization metrics
            avg_cpu = self._get_average_cpu_utilization(
                subscription_id, vm.get('id'), resource_group, vm_name
            )
            
            # Check if VM is underutilized
            if avg_cpu is not None and avg_cpu < self.min_cpu_utilization:
                # Determine recommended VM size
                recommended_size = self._recommend_vm_size(vm_size, avg_cpu)
                
                if recommended_size and recommended_size != vm_size:
                    # Calculate estimated savings
                    savings = self._calculate_downsizing_savings(vm_size, recommended_size, location)
                    
                    recommendations.append({
                        'vm_id': vm.get('id'),
                        'vm_name': vm_name,
                        'subscription_id': subscription_id,
                        'resource_group': resource_group,
                        'region': location,
                        'recommendation_type': 'Rightsize VM',
                        'current_state': {
                            'vm_size': vm_size,
                            'avg_cpu_utilization': avg_cpu,
                        },
                        'recommended_state': {
                            'vm_size': recommended_size,
                            'expected_cpu_utilization': avg_cpu * 2,
                        },
                        'estimated_monthly_savings': savings,
                        'confidence': 'High' if avg_cpu < 2.0 else 'Medium',
                        'details': f"VM has average CPU utilization of {avg_cpu:.1f}%, which is below the threshold of {self.min_cpu_utilization}%. Consider downsizing to {recommended_size}."
                    })
        
        return recommendations
    
    def _get_average_cpu_utilization(self, subscription_id: str, vm_id: str, 
                                    resource_group: str, vm_name: str) -> Optional[float]:
        """
        Get average CPU utilization for an Azure VM over the lookback period.
        
        Args:
            subscription_id: Azure subscription ID
            vm_id: VM resource ID
            resource_group: Resource group name
            vm_name: VM name
            
        Returns:
            Average CPU utilization percentage or None if data not available
        """
        try:
            # For the sake of demonstration, we'll simulate getting metrics
            # In a real implementation, this would use the Monitor client to query metrics
            
            # Simulation logic - generate a random CPU utilization based on VM name
            # This is just to provide diverse examples
            import hashlib
            
            # Generate a hash of the VM name to get a consistent "random" value
            name_hash = hashlib.md5(vm_name.encode()).hexdigest()
            hash_value = int(name_hash, 16)
            
            # Use the hash to generate a CPU value between 0.5% and 20%
            avg_cpu = (hash_value % 195) / 10.0 + 0.5
            
            return avg_cpu
        except Exception as e:
            self.logger.error(f"Error getting CPU utilization for VM {vm_name}: {str(e)}")
            return None
    
    def _recommend_vm_size(self, current_size: str, avg_cpu: float) -> Optional[str]:
        """
        Recommend an appropriate VM size based on current usage.
        
        Args:
            current_size: Current VM size
            avg_cpu: Average CPU utilization
            
        Returns:
            Recommended VM size or None if no recommendation
        """
        # This is a simplified recommendation. In a real-world scenario,
        # we would consider more factors like memory, network, etc.
        
        # Map of VM size downgrades
        size_map = {
            # General purpose
            'Standard_D2s_v3': 'Standard_D1s_v3',
            'Standard_D4s_v3': 'Standard_D2s_v3',
            'Standard_D8s_v3': 'Standard_D4s_v3',
            'Standard_D16s_v3': 'Standard_D8s_v3',
            'Standard_D32s_v3': 'Standard_D16s_v3',
            'Standard_D64s_v3': 'Standard_D32s_v3',
            
            # Memory optimized
            'Standard_E2s_v3': 'Standard_E1s_v3',
            'Standard_E4s_v3': 'Standard_E2s_v3',
            'Standard_E8s_v3': 'Standard_E4s_v3',
            'Standard_E16s_v3': 'Standard_E8s_v3',
            'Standard_E32s_v3': 'Standard_E16s_v3',
            'Standard_E64s_v3': 'Standard_E32s_v3',
            
            # Compute optimized
            'Standard_F2s_v2': 'Standard_F1s_v2',
            'Standard_F4s_v2': 'Standard_F2s_v2',
            'Standard_F8s_v2': 'Standard_F4s_v2',
            'Standard_F16s_v2': 'Standard_F8s_v2',
            'Standard_F32s_v2': 'Standard_F16s_v2',
            'Standard_F64s_v2': 'Standard_F32s_v2',
            
            # B-series
            'Standard_B2s': 'Standard_B1s',
            'Standard_B2ms': 'Standard_B1ms',
            'Standard_B4ms': 'Standard_B2ms',
            'Standard_B8ms': 'Standard_B4ms',
            'Standard_B12ms': 'Standard_B8ms',
            'Standard_B16ms': 'Standard_B12ms',
            'Standard_B20ms': 'Standard_B16ms'
        }
        
        # If CPU usage is very low, recommend downsizing
        if current_size in size_map and avg_cpu < self.min_cpu_utilization:
            return size_map[current_size]
        
        return None
    
    def _calculate_downsizing_savings(self, current_size: str, recommended_size: str, location: str) -> float:
        """
        Calculate estimated monthly savings from Azure VM downsizing.
        
        Args:
            current_size: Current VM size
            recommended_size: Recommended VM size
            location: Azure region
            
        Returns:
            Estimated monthly savings in USD
        """
        # This is a simplified calculation. In a real-world scenario,
        # we would use the Azure Retail Prices API for accurate pricing.
        
        # Rough pricing estimates for pay-as-you-go VMs in US East (USD per hour)
        pricing = {
            # General purpose (D-series)
            'Standard_D1s_v3': 0.0768,
            'Standard_D2s_v3': 0.1536,
            'Standard_D4s_v3': 0.3072,
            'Standard_D8s_v3': 0.6144,
            'Standard_D16s_v3': 1.2288,
            'Standard_D32s_v3': 2.4576,
            'Standard_D64s_v3': 4.9152,
            
            # Memory optimized (E-series)
            'Standard_E1s_v3': 0.0768,
            'Standard_E2s_v3': 0.1536,
            'Standard_E4s_v3': 0.3072,
            'Standard_E8s_v3': 0.6144,
            'Standard_E16s_v3': 1.2288,
            'Standard_E32s_v3': 2.4576,
            'Standard_E64s_v3': 4.9152,
            
            # Compute optimized (F-series)
            'Standard_F1s_v2': 0.05,
            'Standard_F2s_v2': 0.1,
            'Standard_F4s_v2': 0.2,
            'Standard_F8s_v2': 0.4,
            'Standard_F16s_v2': 0.8,
            'Standard_F32s_v2': 1.6,
            'Standard_F64s_v2': 3.2,
            
            # Burstable (B-series)
            'Standard_B1s': 0.012,
            'Standard_B1ms': 0.0218,
            'Standard_B2s': 0.0436,
            'Standard_B2ms': 0.0832,
            'Standard_B4ms': 0.166,
            'Standard_B8ms': 0.333,
            'Standard_B12ms': 0.499,
            'Standard_B16ms': 0.666,
            'Standard_B20ms': 0.832
        }
        
        # Get pricing for current and recommended sizes
        current_hourly = pricing.get(current_size, 0.0)
        recommended_hourly = pricing.get(recommended_size, 0.0)
        
        # If we don't have pricing data, make a rough estimate based on size names
        if current_hourly == 0.0 or recommended_hourly == 0.0:
            # Extract the VM size number (e.g., D2, D4)
            import re
            
            current_size_match = re.search(r'(\d+)', current_size)
            recommended_size_match = re.search(r'(\d+)', recommended_size)
            
            if current_size_match and recommended_size_match:
                current_size_num = int(current_size_match.group(1))
                recommended_size_num = int(recommended_size_match.group(1))
                
                # Assume linear pricing based on size number
                if current_size_num > 0 and recommended_size_num > 0:
                    size_ratio = current_size_num / recommended_size_num
                    # Use a base price of $0.1/hour for a size "1" VM
                    current_hourly = 0.1 * current_size_num
                    recommended_hourly = 0.1 * recommended_size_num
        
        # Calculate monthly savings (30 days, 24 hours)
        hourly_savings = current_hourly - recommended_hourly
        monthly_savings = hourly_savings * 24 * 30
        
        return monthly_savings
    
    def _find_idle_vms(self, subscription_id: str, vms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Find idle Azure VMs with no significant CPU activity.
        
        Args:
            subscription_id: Azure subscription ID
            vms: List of VM details
            
        Returns:
            List of recommendations for idle VMs
        """
        recommendations = []
        
        for vm in vms:
            # Only analyze running VMs
            if vm.get('power_state') != 'running':
                continue
            
            vm_name = vm.get('name')
            vm_size = vm.get('vm_size')
            resource_group = vm.get('resource_group')
            location = vm.get('location')
            
            # Get CPU utilization metrics
            avg_cpu = self._get_average_cpu_utilization(
                subscription_id, vm.get('id'), resource_group, vm_name
            )
            
            # Check if VM is idle (very low CPU)
            if avg_cpu is not None and avg_cpu < 1.0:
                # Get hourly cost of the VM
                hourly_cost = self._get_vm_hourly_cost(vm_size, location)
                monthly_cost = hourly_cost * 24 * 30
                
                recommendations.append({
                    'vm_id': vm.get('id'),
                    'vm_name': vm_name,
                    'subscription_id': subscription_id,
                    'resource_group': resource_group,
                    'region': location,
                    'recommendation_type': 'Stop or Deallocate Idle VM',
                    'current_state': {
                        'vm_size': vm_size,
                        'avg_cpu_utilization': avg_cpu,
                        'power_state': 'running'
                    },
                    'recommended_state': {
                        'power_state': 'deallocated'
                    },
                    'estimated_monthly_savings': monthly_cost,
                    'confidence': 'High' if avg_cpu < 0.5 else 'Medium',
                    'details': f"VM has average CPU utilization of {avg_cpu:.1f}%, indicating it might be idle. Consider stopping or deallocating if not needed."
                })
        
        return recommendations
    
    def _get_vm_hourly_cost(self, vm_size: str, location: str) -> float:
        """
        Get the hourly cost of an Azure VM size.
        
        Args:
            vm_size: Azure VM size
            location: Azure region
            
        Returns:
            Hourly cost in USD
        """
        # This is a simplified pricing lookup. In a real-world scenario,
        # we would use the Azure Retail Prices API for accurate pricing.
        
        # Rough pricing estimates for pay-as-you-go VMs in US East (USD per hour)
        pricing = {
            # General purpose (D-series)
            'Standard_D1s_v3': 0.0768,
            'Standard_D2s_v3': 0.1536,
            'Standard_D4s_v3': 0.3072,
            'Standard_D8s_v3': 0.6144,
            'Standard_D16s_v3': 1.2288,
            'Standard_D32s_v3': 2.4576,
            'Standard_D64s_v3': 4.9152,
            
            # Memory optimized (E-series)
            'Standard_E1s_v3': 0.0768,
            'Standard_E2s_v3': 0.1536,
            'Standard_E4s_v3': 0.3072,
            'Standard_E8s_v3': 0.6144,
            'Standard_E16s_v3': 1.2288,
            'Standard_E32s_v3': 2.4576,
            'Standard_E64s_v3': 4.9152,
            
            # Compute optimized (F-series)
            'Standard_F1s_v2': 0.05,
            'Standard_F2s_v2': 0.1,
            'Standard_F4s_v2': 0.2,
            'Standard_F8s_v2': 0.4,
            'Standard_F16s_v2': 0.8,
            'Standard_F32s_v2': 1.6,
            'Standard_F64s_v2': 3.2,
            
            # Burstable (B-series)
            'Standard_B1s': 0.012,
            'Standard_B1ms': 0.0218,
            'Standard_B2s': 0.0436,
            'Standard_B2ms': 0.0832,
            'Standard_B4ms': 0.166,
            'Standard_B8ms': 0.333,
            'Standard_B12ms': 0.499,
            'Standard_B16ms': 0.666,
            'Standard_B20ms': 0.832
        }
        
        return pricing.get(vm_size, 0.1)  # Default to $0.1/hour if unknown
    
    def _find_ri_opportunities(self, subscription_id: str, vms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Find Azure VMs that are good candidates for Reserved Instances.
        
        Args:
            subscription_id: Azure subscription ID
            vms: List of VM details
            
        Returns:
            List of recommendations for Reserved Instance purchases
        """
        recommendations = []
        
        # Group VMs by size and location
        vm_groups = {}
        for vm in vms:
            # Only include running VMs
            if vm.get('power_state') != 'running':
                continue
            
            vm_size = vm.get('vm_size')
            location = vm.get('location')
            
            # Create a key for grouping
            group_key = f"{vm_size}_{location}"
            
            if group_key not in vm_groups:
                vm_groups[group_key] = {
                    'size': vm_size,
                    'location': location,
                    'count': 0,
                    'vms': []
                }
            
            vm_groups[group_key]['count'] += 1
            vm_groups[group_key]['vms'].append(vm.get('id'))
        
        # Generate recommendations for groups with multiple VMs
        for group_key, group in vm_groups.items():
            if group['count'] >= 2:
                vm_size = group['size']
                location = group['location']
                count = group['count']
                
                hourly_cost = self._get_vm_hourly_cost(vm_size, location)
                on_demand_monthly = hourly_cost * 24 * 30 * count
                
                # Calculate savings for 1-year and 3-year RIs
                one_year_savings = on_demand_monthly * 0.35  # Assume 35% savings with 1-year RI
                three_year_savings = on_demand_monthly * 0.6  # Assume 60% savings with 3-year RI
                
                # Recommend the 3-year RI if count >= 5, otherwise 1-year
                if count >= 5:
                    ri_term = "3-year"
                    savings = three_year_savings
                    savings_percentage = "60%"
                else:
                    ri_term = "1-year"
                    savings = one_year_savings
                    savings_percentage = "35%"
                
                recommendations.append({
                    'vm_id': ",".join(group['vms'][:3]) + (f"... and {count-3} more" if count > 3 else ""),
                    'vm_name': f"{count} x {vm_size} VMs",
                    'subscription_id': subscription_id,
                    'region': location,
                    'recommendation_type': 'Purchase Reserved Instances',
                    'current_state': {
                        'vm_size': vm_size,
                        'count': count,
                        'pricing_model': 'Pay-as-you-go'
                    },
                    'recommended_state': {
                        'vm_size': vm_size,
                        'count': count,
                        'pricing_model': f'Reserved Instance ({ri_term})'
                    },
                    'estimated_monthly_savings': savings,
                    'confidence': 'High' if count > 5 else 'Medium',
                    'details': f"Found {count} VMs of size {vm_size} that are good candidates for Reserved Instances. Consider purchasing {ri_term} Reserved Instances for approximately {savings_percentage} savings."
                })
        
        return recommendations 