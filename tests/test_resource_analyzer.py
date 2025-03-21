#!/usr/bin/env python3
"""
Tests for the AWS resource analyzer module.
"""

import os
import sys
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, Mock

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from aws.analyzers.resource_analyzer import AWSResourceAnalyzer

class TestAWSResourceAnalyzer:
    """Test suite for the AWSResourceAnalyzer class."""

    @pytest.fixture
    def sample_config(self):
        """Return a sample configuration for testing."""
        return {
            'general': {
                'output_dir': 'reports',
                'log_level': 'INFO'
            },
            'aws': {
                'enabled': True,
                'profile': 'default',
                'regions': ['us-east-1', 'us-west-2'],
                'analysis': {
                    'lookback_days': 14,
                    'services': ['ec2', 's3', 'rds', 'ebs']
                }
            }
        }

    @pytest.fixture
    def mock_boto3_session(self):
        """Create a mock boto3 session with mock clients."""
        # Mock EC2 client
        mock_ec2 = MagicMock()
        mock_ec2.get_paginator.return_value.paginate.return_value = []
        
        # Mock S3 client
        mock_s3 = MagicMock()
        mock_s3.list_buckets.return_value = {'Buckets': []}
        
        # Mock RDS client
        mock_rds = MagicMock()
        mock_rds.get_paginator.return_value.paginate.return_value = []
        
        # Mock CloudWatch client
        mock_cloudwatch = MagicMock()
        mock_cloudwatch.get_metric_statistics.return_value = {'Datapoints': []}
        
        # Mock session
        mock_session = MagicMock()
        mock_session.client.side_effect = lambda service, region_name=None: {
            'ec2': mock_ec2,
            's3': mock_s3,
            'rds': mock_rds,
            'cloudwatch': mock_cloudwatch
        }[service]
        
        return mock_session

    @patch('boto3.Session')
    def test_initialize_clients_with_profile(self, mock_session_cls, sample_config, mock_boto3_session):
        """Test client initialization with AWS profile."""
        # Setup
        mock_session_cls.return_value = mock_boto3_session
        
        # Initialize analyzer
        analyzer = AWSResourceAnalyzer(sample_config)
        
        # Assert session was created with profile
        mock_session_cls.assert_called_once_with(profile_name='default')
        
        # Assert EC2 clients were created for each region
        assert len(analyzer.ec2_clients) == 2
        assert 'us-east-1' in analyzer.ec2_clients
        assert 'us-west-2' in analyzer.ec2_clients
        
        # Assert CloudWatch clients were created for each region
        assert len(analyzer.cloudwatch_clients) == 2
        
        # Assert S3 client was created
        assert analyzer.s3_client is not None

    @patch('boto3.Session')
    def test_initialize_clients_with_access_keys(self, mock_session_cls, sample_config, mock_boto3_session):
        """Test client initialization with AWS access keys."""
        # Modify config to use access keys
        config = sample_config.copy()
        config['aws'] = config['aws'].copy()
        del config['aws']['profile']
        config['aws']['access_key_id'] = 'test-access-key'
        config['aws']['secret_access_key'] = 'test-secret-key'
        
        # Setup
        mock_session_cls.return_value = mock_boto3_session
        
        # Initialize analyzer
        analyzer = AWSResourceAnalyzer(config)
        
        # Assert session was created with access keys
        mock_session_cls.assert_called_once_with(
            aws_access_key_id='test-access-key',
            aws_secret_access_key='test-secret-key',
            region_name='us-east-1'
        )

    @patch.object(AWSResourceAnalyzer, '_initialize_clients')
    @patch.object(AWSResourceAnalyzer, '_analyze_ec2')
    @patch.object(AWSResourceAnalyzer, '_analyze_s3')
    @patch.object(AWSResourceAnalyzer, '_analyze_rds')
    @patch.object(AWSResourceAnalyzer, '_analyze_ebs')
    def test_analyze_resources(self, mock_analyze_ebs, mock_analyze_rds, 
                              mock_analyze_s3, mock_analyze_ec2, 
                              mock_init_clients, sample_config):
        """Test the analyze_resources method."""
        # Setup
        mock_init_clients.return_value = None
        mock_analyze_ec2.return_value = {'test_ec2_key': 'test_ec2_value'}
        mock_analyze_s3.return_value = {'test_s3_key': 'test_s3_value'}
        mock_analyze_rds.return_value = {'test_rds_key': 'test_rds_value'}
        mock_analyze_ebs.return_value = {'test_ebs_key': 'test_ebs_value'}
        
        # Initialize analyzer
        analyzer = AWSResourceAnalyzer(sample_config)
        
        # Call method
        results = analyzer.analyze_resources()
        
        # Assert all analysis methods were called
        mock_analyze_ec2.assert_called_once()
        mock_analyze_s3.assert_called_once()
        mock_analyze_rds.assert_called_once()
        mock_analyze_ebs.assert_called_once()
        
        # Assert results were combined correctly
        assert 'ec2' in results
        assert results['ec2'] == {'test_ec2_key': 'test_ec2_value'}
        assert 's3' in results
        assert results['s3'] == {'test_s3_key': 'test_s3_value'}
        assert 'rds' in results
        assert results['rds'] == {'test_rds_key': 'test_rds_value'}
        assert 'ebs' in results
        assert results['ebs'] == {'test_ebs_key': 'test_ebs_value'}

    @patch.object(AWSResourceAnalyzer, '_initialize_clients')
    def test_analyze_ec2(self, mock_init_clients, sample_config):
        """Test the _analyze_ec2 method."""
        # Setup
        mock_init_clients.return_value = None
        
        # Create mock EC2 client
        mock_ec2 = MagicMock()
        
        # Mock paginator
        mock_paginator = MagicMock()
        mock_page = {
            'Reservations': [
                {
                    'Instances': [
                        {
                            'InstanceId': 'i-12345678',
                            'InstanceType': 't2.micro',
                            'State': {'Name': 'running'},
                            'Placement': {'AvailabilityZone': 'us-east-1a'},
                            'LaunchTime': datetime(2023, 1, 1, tzinfo=timezone.utc),
                            'Tags': [
                                {'Key': 'Name', 'Value': 'Test Instance'},
                                {'Key': 'Environment', 'Value': 'Development'}
                            ]
                        }
                    ]
                }
            ]
        }
        mock_paginator.paginate.return_value = [mock_page]
        mock_ec2.get_paginator.return_value = mock_paginator
        
        # Mock CloudWatch client
        mock_cloudwatch = MagicMock()
        mock_cloudwatch.get_metric_statistics.return_value = {
            'Datapoints': [
                {
                    'Average': 10.5,
                    'Timestamp': datetime(2023, 1, 1, tzinfo=timezone.utc)
                }
            ]
        }
        
        # Initialize analyzer
        analyzer = AWSResourceAnalyzer(sample_config)
        analyzer.ec2_clients = {'us-east-1': mock_ec2}
        analyzer.cloudwatch_clients = {'us-east-1': mock_cloudwatch}
        
        # Mock the _get_ec2_utilization method
        analyzer._get_ec2_utilization = MagicMock(return_value={
            'CPUUtilization': 10.5,
            'NetworkIn': 1024.0,
            'NetworkOut': 2048.0,
            'DiskReadOps': 100.0,
            'DiskWriteOps': 200.0
        })
        
        # Call method
        results = analyzer._analyze_ec2()
        
        # Assert paginator was called
        mock_ec2.get_paginator.assert_called_once_with('describe_instances')
        
        # Assert results structure
        assert 'instances_by_region' in results
        assert 'us-east-1' in results['instances_by_region']
        assert len(results['instances_by_region']['us-east-1']) == 1
        assert results['instances_by_region']['us-east-1'][0]['instance_id'] == 'i-12345678'
        assert results['instances_by_region']['us-east-1'][0]['instance_type'] == 't2.micro'
        assert results['instances_by_region']['us-east-1'][0]['state'] == 'running'
        
        # Assert counters
        assert 'total_instances' in results
        assert results['total_instances'] == 1
        assert 'instances_by_state' in results
        assert results['instances_by_state']['running'] == 1
        assert 't2.micro' in results['instances_by_type']
        assert results['instances_by_type']['t2.micro'] == 1

    @patch.object(AWSResourceAnalyzer, '_initialize_clients')
    def test_analyze_s3(self, mock_init_clients, sample_config):
        """Test the _analyze_s3 method."""
        # Setup
        mock_init_clients.return_value = None
        
        # Create mock S3 client
        mock_s3 = MagicMock()
        mock_s3.list_buckets.return_value = {
            'Buckets': [
                {
                    'Name': 'test-bucket',
                    'CreationDate': datetime(2023, 1, 1, tzinfo=timezone.utc)
                }
            ]
        }
        mock_s3.get_bucket_location.return_value = {'LocationConstraint': 'us-east-1'}
        
        # Mock paginator
        mock_paginator = MagicMock()
        mock_page = {
            'Contents': [
                {
                    'Key': 'test-object-1',
                    'Size': 1024,
                    'StorageClass': 'STANDARD',
                    'LastModified': datetime(2023, 1, 1, tzinfo=timezone.utc)
                },
                {
                    'Key': 'test-object-2',
                    'Size': 2048,
                    'StorageClass': 'STANDARD_IA',
                    'LastModified': datetime(2023, 1, 2, tzinfo=timezone.utc)
                }
            ]
        }
        mock_paginator.paginate.return_value = [mock_page]
        mock_s3.get_paginator.return_value = mock_paginator
        
        # Mock CloudWatch client
        mock_cloudwatch = MagicMock()
        mock_cloudwatch.get_metric_statistics.side_effect = [
            {
                # Bucket size
                'Datapoints': [
                    {
                        'Average': 3072.0,
                        'Timestamp': datetime(2023, 1, 1, tzinfo=timezone.utc)
                    }
                ]
            },
            {
                # Object count
                'Datapoints': [
                    {
                        'Average': 2.0,
                        'Timestamp': datetime(2023, 1, 1, tzinfo=timezone.utc)
                    }
                ]
            }
        ]
        
        # Initialize analyzer
        analyzer = AWSResourceAnalyzer(sample_config)
        analyzer.s3_client = mock_s3
        analyzer.cloudwatch_clients = {'us-east-1': mock_cloudwatch}
        
        # Call method
        results = analyzer._analyze_s3()
        
        # Assert list_buckets was called
        mock_s3.list_buckets.assert_called_once()
        
        # Assert results structure
        assert 'total_buckets' in results
        assert results['total_buckets'] == 1
        assert 'buckets' in results
        assert len(results['buckets']) == 1
        assert results['buckets'][0]['name'] == 'test-bucket'
        assert results['buckets'][0]['region'] == 'us-east-1'
        assert results['buckets'][0]['size_bytes'] == 3072.0
        assert results['buckets'][0]['object_count'] == 2.0
        
        # Assert storage class distribution
        assert 'storage_class_distribution' in results
        assert 'STANDARD' in results['storage_class_distribution']
        assert results['storage_class_distribution']['STANDARD'] == 1
        assert 'STANDARD_IA' in results['storage_class_distribution']
        assert results['storage_class_distribution']['STANDARD_IA'] == 1

    @patch.object(AWSResourceAnalyzer, '_initialize_clients')
    def test_get_ec2_utilization(self, mock_init_clients, sample_config):
        """Test the _get_ec2_utilization method."""
        # Setup
        mock_init_clients.return_value = None
        
        # Create mock CloudWatch client
        mock_cloudwatch = MagicMock()
        mock_cloudwatch.get_metric_statistics.return_value = {
            'Datapoints': [
                {
                    'Average': 10.5,
                    'Timestamp': datetime(2023, 1, 1, tzinfo=timezone.utc)
                },
                {
                    'Average': 15.2,
                    'Timestamp': datetime(2023, 1, 2, tzinfo=timezone.utc)
                }
            ]
        }
        
        # Initialize analyzer
        analyzer = AWSResourceAnalyzer(sample_config)
        
        # Call method
        results = analyzer._get_ec2_utilization(mock_cloudwatch, 'i-12345678')
        
        # Assert get_metric_statistics was called for each metric
        assert mock_cloudwatch.get_metric_statistics.call_count == 5
        
        # Assert results
        assert 'CPUUtilization' in results
        assert results['CPUUtilization'] == 12.85  # Average of 10.5 and 15.2

if __name__ == "__main__":
    pytest.main(["-v", __file__]) 