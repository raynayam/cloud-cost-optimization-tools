"""
Tests for the EC2 optimizer module.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock
import boto3

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from aws.optimizers.ec2_optimizer import EC2Optimizer

class TestEC2Optimizer:
    """Test suite for the EC2 optimizer module."""
    
    @pytest.fixture
    def sample_config(self):
        """Return a sample configuration for testing."""
        return {
            'general': {
                'output_dir': './reports',
                'log_level': 'INFO',
                'default_region': 'us-east-1'
            },
            'aws': {
                'enabled': True,
                'profile': 'default',
                'regions': ['us-east-1', 'us-west-2'],
                'analysis': {
                    'lookback_days': 30,
                    'include_services': ['ec2', 'rds', 's3'],
                },
                'optimization': {
                    'ec2': {
                        'min_cpu_utilization': 5.0,
                        'min_uptime_hours': 168
                    }
                }
            }
        }
    
    @pytest.fixture
    def mock_boto3_session(self):
        """Create a mock boto3 session."""
        mock_session = MagicMock()
        mock_ec2_client = MagicMock()
        mock_cloudwatch_client = MagicMock()
        
        mock_session.client.side_effect = lambda service, **kwargs: {
            'ec2': mock_ec2_client,
            'cloudwatch': mock_cloudwatch_client
        }.get(service, MagicMock())
        
        return mock_session, mock_ec2_client, mock_cloudwatch_client
    
    @patch('boto3.Session')
    def test_initialize_clients(self, mock_boto3_session, sample_config, mock_boto3_session_fixture):
        """Test that clients are initialized correctly."""
        mock_session, _, _ = mock_boto3_session_fixture
        mock_boto3_session.return_value = mock_session
        
        optimizer = EC2Optimizer(sample_config)
        
        # Check that boto3 session was created with the correct profile
        mock_boto3_session.assert_called_once_with(profile_name='default')
        
        # Check that the EC2 and CloudWatch clients were created
        mock_session.client.assert_any_call('ec2')
        mock_session.client.assert_any_call('cloudwatch')
    
    @patch('boto3.client')
    def test_initialize_clients_with_access_keys(self, mock_boto3_client, sample_config):
        """Test that clients are initialized correctly with access keys."""
        # Modify config to use access keys instead of profile
        config = sample_config.copy()
        config['aws'].pop('profile')
        config['aws']['access_key_id'] = 'test-access-key'
        config['aws']['secret_access_key'] = 'test-secret-key'
        
        optimizer = EC2Optimizer(config)
        
        # Check that boto3 clients were created with the correct credentials
        calls = [
            'ec2',
            'cloudwatch'
        ]
        
        for service in calls:
            mock_boto3_client.assert_any_call(
                service,
                aws_access_key_id='test-access-key',
                aws_secret_access_key='test-secret-key',
                region_name='us-east-1'
            )
    
    @patch('boto3.client')
    def test_get_instances(self, mock_boto3_client, sample_config):
        """Test that instances are retrieved correctly."""
        # Create mock EC2 client
        mock_ec2 = MagicMock()
        mock_boto3_client.return_value = mock_ec2
        
        # Mock describe_instances response
        mock_ec2.describe_instances.return_value = {
            'Reservations': [
                {
                    'Instances': [
                        {
                            'InstanceId': 'i-12345678',
                            'InstanceType': 't3.micro',
                            'State': {'Name': 'running'},
                            'LaunchTime': '2023-01-01T00:00:00+00:00',
                            'Placement': {'AvailabilityZone': 'us-east-1a'},
                            'PrivateIpAddress': '10.0.0.1',
                            'PublicIpAddress': '1.2.3.4',
                            'Tags': [{'Key': 'Name', 'Value': 'test-instance'}]
                        }
                    ]
                }
            ]
        }
        
        optimizer = EC2Optimizer(sample_config)
        instances = optimizer._get_instances('us-east-1')
        
        # Check that the instances were retrieved correctly
        assert len(instances) == 1
        assert instances[0]['instance_id'] == 'i-12345678'
        assert instances[0]['instance_type'] == 't3.micro'
        assert instances[0]['instance_name'] == 'test-instance'
        assert instances[0]['region'] == 'us-east-1'
    
    @patch('boto3.client')
    def test_find_underutilized_instances(self, mock_boto3_client, sample_config):
        """Test that underutilized instances are identified correctly."""
        # Create mock clients
        mock_ec2 = MagicMock()
        mock_cloudwatch = MagicMock()
        
        mock_boto3_client.side_effect = lambda service, **kwargs: {
            'ec2': mock_ec2,
            'cloudwatch': mock_cloudwatch
        }.get(service, MagicMock())
        
        # Mock cloudwatch get_metric_statistics response
        mock_cloudwatch.get_metric_statistics.return_value = {
            'Datapoints': [
                {'Average': 3.0},
                {'Average': 2.0},
                {'Average': 4.0}
            ]
        }
        
        optimizer = EC2Optimizer(sample_config)
        
        # Create test instance data
        instances = [
            {
                'instance_id': 'i-12345678',
                'instance_name': 'test-instance',
                'instance_type': 't3.xlarge',
                'region': 'us-east-1'
            }
        ]
        
        recommendations = optimizer._find_underutilized_instances(instances, 'us-east-1')
        
        # Check that an underutilized instance recommendation was generated
        assert len(recommendations) == 1
        assert recommendations[0]['instance_id'] == 'i-12345678'
        assert recommendations[0]['recommendation_type'] == 'Rightsize Instance'
        assert recommendations[0]['current_state']['instance_type'] == 't3.xlarge'
        assert recommendations[0]['current_state']['avg_cpu_utilization'] == 3.0
        assert recommendations[0]['recommended_state']['instance_type'] == 't3.large'
    
    @patch('boto3.client')
    def test_find_idle_instances(self, mock_boto3_client, sample_config):
        """Test that idle instances are identified correctly."""
        # Create mock clients
        mock_ec2 = MagicMock()
        mock_cloudwatch = MagicMock()
        
        mock_boto3_client.side_effect = lambda service, **kwargs: {
            'ec2': mock_ec2,
            'cloudwatch': mock_cloudwatch
        }.get(service, MagicMock())
        
        # Mock cloudwatch get_metric_statistics response
        mock_cloudwatch.get_metric_statistics.return_value = {
            'Datapoints': [
                {'Average': 0.5},
                {'Average': 0.3},
                {'Average': 0.8}
            ]
        }
        
        optimizer = EC2Optimizer(sample_config)
        
        # Create test instance data
        instances = [
            {
                'instance_id': 'i-12345678',
                'instance_name': 'test-instance',
                'instance_type': 't3.micro',
                'region': 'us-east-1'
            }
        ]
        
        recommendations = optimizer._find_idle_instances(instances, 'us-east-1')
        
        # Check that an idle instance recommendation was generated
        assert len(recommendations) == 1
        assert recommendations[0]['instance_id'] == 'i-12345678'
        assert recommendations[0]['recommendation_type'] == 'Terminate Idle Instance'
        assert recommendations[0]['current_state']['avg_cpu_utilization'] == 0.5333333333333333
    
    @patch('boto3.client')
    def test_find_ri_opportunities(self, mock_boto3_client, sample_config):
        """Test that RI opportunities are identified correctly."""
        # Create mock EC2 client
        mock_ec2 = MagicMock()
        mock_boto3_client.return_value = mock_ec2
        
        optimizer = EC2Optimizer(sample_config)
        
        # Create test instance data with multiple instances of the same type
        instances = [
            {
                'instance_id': 'i-12345678',
                'instance_name': 'test-instance-1',
                'instance_type': 't3.large',
                'region': 'us-east-1',
                'launch_time': '2020-01-01T00:00:00+00:00'  # Mock old launch time
            },
            {
                'instance_id': 'i-87654321',
                'instance_name': 'test-instance-2',
                'instance_type': 't3.large',
                'region': 'us-east-1',
                'launch_time': '2020-01-01T00:00:00+00:00'  # Mock old launch time
            },
            {
                'instance_id': 'i-11111111',
                'instance_name': 'test-instance-3',
                'instance_type': 'm5.xlarge',
                'region': 'us-east-1',
                'launch_time': '2020-01-01T00:00:00+00:00'  # Mock old launch time
            }
        ]
        
        # Mock the uptime calculation
        with patch.object(optimizer, '_get_instance_uptime_hours', return_value=1000):
            recommendations = optimizer._find_ri_opportunities(instances, 'us-east-1')
        
        # Check that an RI recommendation was generated for the t3.large instances
        assert len(recommendations) == 2
        assert any(r['instance_type'] == 't3.large' and r['count'] == 2 for r in [r['current_state'] for r in recommendations])
        assert any(r['recommendation_type'] == 'Purchase Reserved Instances' for r in recommendations)

if __name__ == '__main__':
    pytest.main(['-xvs', __file__]) 