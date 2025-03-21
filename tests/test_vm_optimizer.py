#!/usr/bin/env python3
"""
Tests for the Azure VM optimizer module.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock, Mock

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from azure.optimizers.vm_optimizer import VMOptimizer

class TestVMOptimizer:
    """Test suite for the VMOptimizer class."""

    @pytest.fixture
    def sample_config(self):
        """Return a sample configuration for testing."""
        return {
            'general': {
                'output_dir': 'reports',
                'log_level': 'INFO'
            },
            'azure': {
                'enabled': True,
                'auth_method': 'cli',
                'subscription_ids': ['subscription-id-1', 'subscription-id-2'],
                'regions': ['eastus', 'westus'],
                'analysis': {
                    'lookback_days': 14,
                    'services': ['compute', 'storage']
                },
                'optimizations': {
                    'vm': {
                        'min_cpu_utilization': 20,
                        'min_uptime_hours': 12
                    }
                }
            }
        }

    @pytest.fixture
    def mock_azure_clients(self):
        """Create mock Azure clients for testing."""
        # Mock ComputeManagementClient
        mock_compute_client = MagicMock()
        mock_compute_client.virtual_machines = MagicMock()
        mock_compute_client.virtual_machines.list_all = MagicMock(return_value=[])
        
        # Mock MonitorManagementClient
        mock_monitor_client = MagicMock()
        mock_monitor_client.metrics = MagicMock()
        mock_monitor_client.metrics.list = MagicMock(return_value=MagicMock())
        
        # Mock CostManagementClient
        mock_cost_client = MagicMock()
        mock_cost_client.query = MagicMock()
        
        return {
            'compute': mock_compute_client,
            'monitor': mock_monitor_client,
            'cost': mock_cost_client
        }

    @patch('azure.identity.DefaultAzureCredential')
    @patch('azure.mgmt.compute.ComputeManagementClient')
    @patch('azure.mgmt.monitor.MonitorManagementClient')
    @patch('azure.mgmt.costmanagement.CostManagementClient')
    def test_initialize_clients_with_cli(self, mock_cost_client_cls, mock_monitor_client_cls, 
                                        mock_compute_client_cls, mock_credential_cls, sample_config):
        """Test client initialization with Azure CLI authentication."""
        # Setup mocks
        mock_credential = MagicMock()
        mock_credential_cls.return_value = mock_credential
        
        mock_compute_client = MagicMock()
        mock_compute_client_cls.return_value = mock_compute_client
        
        mock_monitor_client = MagicMock()
        mock_monitor_client_cls.return_value = mock_monitor_client
        
        mock_cost_client = MagicMock()
        mock_cost_client_cls.return_value = mock_cost_client
        
        # Initialize the optimizer
        optimizer = VMOptimizer(sample_config)
        
        # Check if the credential was created
        mock_credential_cls.assert_called_once()
        
        # Check if clients were created for all subscription IDs
        assert len(optimizer.compute_clients) == 2
        assert len(optimizer.monitor_clients) == 2
        
        # Check if clients were created with the correct credentials
        mock_compute_client_cls.assert_called_with(mock_credential, sample_config['azure']['subscription_ids'][0])
        mock_monitor_client_cls.assert_called_with(mock_credential, sample_config['azure']['subscription_ids'][0])

    @patch('azure.identity.ClientSecretCredential')
    @patch('azure.mgmt.compute.ComputeManagementClient')
    @patch('azure.mgmt.monitor.MonitorManagementClient')
    @patch('azure.mgmt.costmanagement.CostManagementClient')
    def test_initialize_clients_with_sp(self, mock_cost_client_cls, mock_monitor_client_cls, 
                                      mock_compute_client_cls, mock_credential_cls, sample_config):
        """Test client initialization with Service Principal authentication."""
        # Modify config to use service principal
        config = sample_config.copy()
        config['azure']['auth_method'] = 'service_principal'
        config['azure']['tenant_id'] = 'tenant-id'
        config['azure']['client_id'] = 'client-id'
        config['azure']['client_secret'] = 'client-secret'
        
        # Setup mocks
        mock_credential = MagicMock()
        mock_credential_cls.return_value = mock_credential
        
        mock_compute_client = MagicMock()
        mock_compute_client_cls.return_value = mock_compute_client
        
        mock_monitor_client = MagicMock()
        mock_monitor_client_cls.return_value = mock_monitor_client
        
        mock_cost_client = MagicMock()
        mock_cost_client_cls.return_value = mock_cost_client
        
        # Initialize the optimizer
        optimizer = VMOptimizer(config)
        
        # Check if the credential was created with correct parameters
        mock_credential_cls.assert_called_once_with(
            tenant_id='tenant-id',
            client_id='client-id',
            client_secret='client-secret'
        )
        
        # Check if clients were created for all subscription IDs
        assert len(optimizer.compute_clients) == 2
        assert len(optimizer.monitor_clients) == 2

    @patch.object(VMOptimizer, '_initialize_clients')
    def test_generate_recommendations(self, mock_init_clients, sample_config, mock_azure_clients):
        """Test the generation of VM optimization recommendations."""
        # Setup the test
        mock_init_clients.return_value = None
        optimizer = VMOptimizer(sample_config)
        
        # Replace the clients with our mocks
        optimizer.compute_clients = {
            'subscription-id-1': mock_azure_clients['compute'],
            'subscription-id-2': mock_azure_clients['compute']
        }
        optimizer.monitor_clients = {
            'subscription-id-1': mock_azure_clients['monitor'],
            'subscription-id-2': mock_azure_clients['monitor']
        }
        optimizer.cost_clients = {
            'subscription-id-1': mock_azure_clients['cost'],
            'subscription-id-2': mock_azure_clients['cost']
        }
        
        # Mock the internal methods
        optimizer._get_vms = MagicMock(return_value=[
            {
                'id': '/subscriptions/subscription-id-1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1',
                'name': 'vm1',
                'resource_group': 'rg1',
                'size': 'Standard_D2s_v3',
                'location': 'eastus',
                'power_state': 'running',
                'subscription_id': 'subscription-id-1'
            }
        ])
        optimizer._find_underutilized_vms = MagicMock(return_value=[
            {
                'id': '/subscriptions/subscription-id-1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1',
                'name': 'vm1',
                'resource_group': 'rg1',
                'size': 'Standard_D2s_v3',
                'new_size': 'Standard_B2s',
                'current_cpu': 10.5,
                'current_cost': 100.0,
                'new_cost': 50.0,
                'savings': 50.0
            }
        ])
        optimizer._find_idle_vms = MagicMock(return_value=[])
        optimizer._find_ri_opportunities = MagicMock(return_value=[])
        
        # Call the method
        analysis_data = {}
        recommendations = optimizer.generate_recommendations(analysis_data)
        
        # Verify the results
        assert len(recommendations) == 1
        assert recommendations[0]['vm_id'] == 'vm1'
        assert recommendations[0]['recommendation_type'] == 'Resize'
        assert recommendations[0]['current_vm_size'] == 'Standard_D2s_v3'
        assert recommendations[0]['recommended_vm_size'] == 'Standard_B2s'
        assert recommendations[0]['potential_monthly_savings'] == 50.0

    @patch.object(VMOptimizer, '_initialize_clients')
    def test_get_vms(self, mock_init_clients, sample_config):
        """Test retrieving VM information."""
        # Setup the test
        mock_init_clients.return_value = None
        optimizer = VMOptimizer(sample_config)
        
        # Mock the compute client
        mock_compute_client = MagicMock()
        mock_vm1 = MagicMock()
        mock_vm1.id = '/subscriptions/subscription-id-1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1'
        mock_vm1.name = 'vm1'
        mock_vm1.location = 'eastus'
        mock_vm1.hardware_profile.vm_size = 'Standard_D2s_v3'
        
        mock_compute_client.virtual_machines.list_all.return_value = [mock_vm1]
        
        optimizer.compute_clients = {
            'subscription-id-1': mock_compute_client
        }
        
        # Mock power state
        optimizer._get_vm_power_state = MagicMock(return_value='running')
        
        # Call the method
        vms = optimizer._get_vms()
        
        # Verify the results
        assert len(vms) == 1
        assert vms[0]['name'] == 'vm1'
        assert vms[0]['size'] == 'Standard_D2s_v3'
        assert vms[0]['location'] == 'eastus'
        assert vms[0]['power_state'] == 'running'
        
        # Verify the method was called
        mock_compute_client.virtual_machines.list_all.assert_called_once()

    @patch.object(VMOptimizer, '_initialize_clients')
    def test_find_underutilized_vms(self, mock_init_clients, sample_config):
        """Test finding underutilized VMs."""
        # Setup the test
        mock_init_clients.return_value = None
        optimizer = VMOptimizer(sample_config)
        
        # Mock methods
        optimizer._get_average_cpu_utilization = MagicMock(return_value=10.5)
        optimizer._recommend_vm_size = MagicMock(return_value='Standard_B2s')
        optimizer._calculate_downsizing_savings = MagicMock(return_value=50.0)
        optimizer._get_vm_hourly_cost = MagicMock(return_value=0.14)  # $100 per month
        
        # Test data
        vms = [
            {
                'id': '/subscriptions/subscription-id-1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1',
                'name': 'vm1',
                'resource_group': 'rg1',
                'size': 'Standard_D2s_v3',
                'location': 'eastus',
                'power_state': 'running',
                'subscription_id': 'subscription-id-1'
            }
        ]
        
        # Call the method
        results = optimizer._find_underutilized_vms(vms)
        
        # Verify the results
        assert len(results) == 1
        assert results[0]['name'] == 'vm1'
        assert results[0]['size'] == 'Standard_D2s_v3'
        assert results[0]['new_size'] == 'Standard_B2s'
        assert results[0]['current_cpu'] == 10.5
        assert results[0]['savings'] == 50.0
        
        # Verify the methods were called
        optimizer._get_average_cpu_utilization.assert_called_once()
        optimizer._recommend_vm_size.assert_called_once()
        optimizer._calculate_downsizing_savings.assert_called_once()

if __name__ == "__main__":
    pytest.main(["-v", __file__]) 