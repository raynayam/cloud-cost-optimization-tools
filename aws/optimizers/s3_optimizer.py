#!/usr/bin/env python3
"""
S3 optimizer module for Cloud Cost Optimization Tools.

This module analyzes S3 buckets and provides cost optimization recommendations
based on storage class, access patterns, and lifecycle policies.
"""

import logging
import boto3
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import time

class S3Optimizer:
    """
    Analyzes S3 buckets and generates cost optimization recommendations.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize S3 optimizer with configuration settings.

        Args:
            config: Configuration dictionary containing AWS settings
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Get S3 optimization settings
        self.optimization_settings = config['aws'].get('optimizations', {}).get('s3', {})
        self.infrequent_access_threshold_days = self.optimization_settings.get('infrequent_access_threshold_days', 30)
        self.glacier_threshold_days = self.optimization_settings.get('glacier_threshold_days', 90)
        self.deep_archive_threshold_days = self.optimization_settings.get('deep_archive_threshold_days', 180)
        self.min_size_mb = self.optimization_settings.get('min_size_mb', 128)
        
        # Initialize AWS clients
        self.regions = config['aws'].get('regions', ['us-east-1'])
        self.s3_clients = {}
        self.cloudwatch_clients = {}
        self._initialize_clients()

    def _initialize_clients(self):
        """Initialize AWS S3 and CloudWatch clients for each region."""
        self.logger.debug("Initializing AWS clients for S3 optimizer")
        
        # Check if using profile or access keys
        if 'profile' in self.config['aws']:
            session = boto3.Session(profile_name=self.config['aws']['profile'])
            self.logger.debug(f"Using AWS profile: {self.config['aws']['profile']}")
        elif all(key in self.config['aws'] for key in ['access_key_id', 'secret_access_key']):
            session = boto3.Session(
                aws_access_key_id=self.config['aws']['access_key_id'],
                aws_secret_access_key=self.config['aws']['secret_access_key'],
                region_name=self.regions[0]
            )
            self.logger.debug("Using AWS access keys for authentication")
        else:
            session = boto3.Session()
            self.logger.debug("Using default AWS credentials")
        
        # Create clients for each region
        for region in self.regions:
            self.s3_clients[region] = session.client('s3', region_name=region)
            self.cloudwatch_clients[region] = session.client('cloudwatch', region_name=region)
        
        # Main S3 client (S3 is a global service but we'll use the first region for API calls)
        self.s3 = self.s3_clients[self.regions[0]]

    def generate_recommendations(self, analysis_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate S3 cost optimization recommendations.

        Args:
            analysis_data: The analysis data containing S3 information

        Returns:
            List of recommendations for S3 cost optimization
        """
        self.logger.info("Generating S3 optimization recommendations")
        recommendations = []
        
        try:
            # Get all S3 buckets
            buckets = self._get_buckets()
            
            # Check storage class optimization opportunities
            storage_class_recommendations = self._find_storage_class_opportunities(buckets)
            recommendations.extend(storage_class_recommendations)
            
            # Check lifecycle policy opportunities
            lifecycle_recommendations = self._find_lifecycle_policy_opportunities(buckets)
            recommendations.extend(lifecycle_recommendations)
            
            # Check for versioning and replication cost optimizations
            versioning_recommendations = self._find_versioning_optimization_opportunities(buckets)
            recommendations.extend(versioning_recommendations)
            
            # Check for empty or unused buckets
            unused_bucket_recommendations = self._find_unused_buckets(buckets)
            recommendations.extend(unused_bucket_recommendations)
            
            self.logger.info(f"Generated {len(recommendations)} S3 optimization recommendations")
            return recommendations
        
        except Exception as e:
            self.logger.error(f"Error generating S3 optimization recommendations: {str(e)}")
            return []

    def _get_buckets(self) -> List[Dict[str, Any]]:
        """
        Get all S3 buckets with additional metadata.

        Returns:
            List of S3 buckets with metadata
        """
        self.logger.debug("Retrieving S3 buckets")
        bucket_details = []
        
        try:
            # List all S3 buckets
            response = self.s3.list_buckets()
            
            for bucket in response['Buckets']:
                try:
                    bucket_name = bucket['Name']
                    creation_date = bucket['CreationDate']
                    
                    # Get bucket region
                    location = self.s3.get_bucket_location(Bucket=bucket_name)
                    region = location['LocationConstraint'] or 'us-east-1'
                    
                    # Get bucket stats and settings
                    metrics = self._get_bucket_metrics(bucket_name, region)
                    lifecycle = self._get_bucket_lifecycle(bucket_name)
                    versioning = self._get_bucket_versioning(bucket_name)
                    
                    bucket_details.append({
                        'name': bucket_name,
                        'creation_date': creation_date,
                        'region': region,
                        'metrics': metrics,
                        'lifecycle': lifecycle,
                        'versioning': versioning
                    })
                except Exception as e:
                    self.logger.warning(f"Error getting details for bucket {bucket['Name']}: {str(e)}")
            
            self.logger.debug(f"Retrieved {len(bucket_details)} S3 buckets")
            return bucket_details
        
        except Exception as e:
            self.logger.error(f"Error retrieving S3 buckets: {str(e)}")
            return []

    def _get_bucket_metrics(self, bucket_name: str, region: str) -> Dict[str, Any]:
        """
        Get bucket metrics including size, object count, and access patterns.

        Args:
            bucket_name: Name of the S3 bucket
            region: AWS region where the bucket is located

        Returns:
            Dictionary of bucket metrics
        """
        metrics = {
            'size_bytes': 0,
            'object_count': 0,
            'storage_class_distribution': {},
            'last_accessed': None
        }
        
        try:
            # Get CloudWatch client for the right region
            cloudwatch = self.cloudwatch_clients.get(region, self.cloudwatch_clients[self.regions[0]])
            
            # Get bucket size
            size_response = cloudwatch.get_metric_statistics(
                Namespace='AWS/S3',
                MetricName='BucketSizeBytes',
                Dimensions=[
                    {'Name': 'BucketName', 'Value': bucket_name},
                    {'Name': 'StorageType', 'Value': 'StandardStorage'}
                ],
                StartTime=datetime.now() - timedelta(days=2),
                EndTime=datetime.now(),
                Period=86400,
                Statistics=['Average']
            )
            
            if size_response['Datapoints']:
                metrics['size_bytes'] = size_response['Datapoints'][-1]['Average']
            
            # Get object count
            count_response = cloudwatch.get_metric_statistics(
                Namespace='AWS/S3',
                MetricName='NumberOfObjects',
                Dimensions=[
                    {'Name': 'BucketName', 'Value': bucket_name},
                    {'Name': 'StorageType', 'Value': 'AllStorageTypes'}
                ],
                StartTime=datetime.now() - timedelta(days=2),
                EndTime=datetime.now(),
                Period=86400,
                Statistics=['Average']
            )
            
            if count_response['Datapoints']:
                metrics['object_count'] = count_response['Datapoints'][-1]['Average']
            
            # Get storage class distribution
            paginator = self.s3.get_paginator('list_objects_v2')
            storage_classes = {}
            
            for page in paginator.paginate(Bucket=bucket_name, MaxKeys=1000):
                if 'Contents' not in page:
                    continue
                    
                for obj in page['Contents']:
                    storage_class = obj.get('StorageClass', 'STANDARD')
                    last_modified = obj.get('LastModified')
                    
                    # Update storage class count
                    if storage_class not in storage_classes:
                        storage_classes[storage_class] = 0
                    storage_classes[storage_class] += 1
                    
                    # Track last accessed/modified date
                    if metrics['last_accessed'] is None or last_modified > metrics['last_accessed']:
                        metrics['last_accessed'] = last_modified
            
            metrics['storage_class_distribution'] = storage_classes
            
            return metrics
        
        except Exception as e:
            self.logger.warning(f"Error getting metrics for bucket {bucket_name}: {str(e)}")
            return metrics

    def _get_bucket_lifecycle(self, bucket_name: str) -> Dict[str, Any]:
        """
        Get bucket lifecycle configuration.

        Args:
            bucket_name: Name of the S3 bucket

        Returns:
            Dictionary with lifecycle configuration details
        """
        lifecycle = {
            'has_lifecycle_policy': False,
            'rules': []
        }
        
        try:
            response = self.s3.get_bucket_lifecycle_configuration(Bucket=bucket_name)
            if 'Rules' in response:
                lifecycle['has_lifecycle_policy'] = True
                lifecycle['rules'] = response['Rules']
        except Exception as e:
            if 'NoSuchLifecycleConfiguration' not in str(e):
                self.logger.warning(f"Error getting lifecycle for bucket {bucket_name}: {str(e)}")
        
        return lifecycle

    def _get_bucket_versioning(self, bucket_name: str) -> Dict[str, Any]:
        """
        Get bucket versioning configuration.

        Args:
            bucket_name: Name of the S3 bucket

        Returns:
            Dictionary with versioning details
        """
        versioning = {
            'enabled': False,
            'mfa_delete': False
        }
        
        try:
            response = self.s3.get_bucket_versioning(Bucket=bucket_name)
            versioning['enabled'] = response.get('Status') == 'Enabled'
            versioning['mfa_delete'] = response.get('MFADelete') == 'Enabled'
        except Exception as e:
            self.logger.warning(f"Error getting versioning for bucket {bucket_name}: {str(e)}")
        
        return versioning

    def _find_storage_class_opportunities(self, buckets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Find opportunities to optimize storage classes.

        Args:
            buckets: List of S3 buckets with metrics

        Returns:
            List of storage class optimization recommendations
        """
        self.logger.debug("Finding storage class optimization opportunities")
        recommendations = []
        
        for bucket in buckets:
            bucket_name = bucket['name']
            metrics = bucket['metrics']
            
            # Skip if bucket is empty or too small
            if metrics['size_bytes'] < (self.min_size_mb * 1024 * 1024):
                continue
            
            # Check for objects that could be moved to infrequent access
            if metrics['last_accessed'] is not None:
                days_since_access = (datetime.now().replace(tzinfo=None) - 
                                    metrics['last_accessed'].replace(tzinfo=None)).days
                
                # Recommend IA if not accessed in threshold days
                if days_since_access > self.infrequent_access_threshold_days:
                    potential_savings = self._calculate_ia_savings(metrics['size_bytes'])
                    
                    if days_since_access > self.glacier_threshold_days:
                        # Recommend Glacier for older objects
                        storage_class = 'GLACIER'
                        potential_savings = self._calculate_glacier_savings(metrics['size_bytes'])
                    elif days_since_access > self.deep_archive_threshold_days:
                        # Recommend Glacier Deep Archive for very old objects
                        storage_class = 'DEEP_ARCHIVE'
                        potential_savings = self._calculate_deep_archive_savings(metrics['size_bytes'])
                    else:
                        storage_class = 'STANDARD_IA'
                    
                    recommendations.append({
                        'resource_id': bucket_name,
                        'resource_type': 'S3 Bucket',
                        'recommendation_type': 'Change Storage Class',
                        'recommendation': f"Change storage class to {storage_class} for bucket {bucket_name}",
                        'reason': f"Bucket has not been accessed for {days_since_access} days",
                        'potential_savings': potential_savings,
                        'details': {
                            'current_size_bytes': metrics['size_bytes'],
                            'current_size_gb': metrics['size_bytes'] / (1024 * 1024 * 1024),
                            'days_since_access': days_since_access,
                            'recommended_storage_class': storage_class
                        }
                    })
        
        return recommendations

    def _find_lifecycle_policy_opportunities(self, buckets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Find opportunities to implement or improve lifecycle policies.

        Args:
            buckets: List of S3 buckets with metrics

        Returns:
            List of lifecycle policy recommendations
        """
        self.logger.debug("Finding lifecycle policy optimization opportunities")
        recommendations = []
        
        for bucket in buckets:
            bucket_name = bucket['name']
            lifecycle = bucket['lifecycle']
            metrics = bucket['metrics']
            
            # Skip if bucket is empty or too small
            if metrics['size_bytes'] < (self.min_size_mb * 1024 * 1024):
                continue
            
            # Check if no lifecycle policy exists
            if not lifecycle['has_lifecycle_policy']:
                recommendations.append({
                    'resource_id': bucket_name,
                    'resource_type': 'S3 Bucket',
                    'recommendation_type': 'Add Lifecycle Policy',
                    'recommendation': f"Implement lifecycle policy for bucket {bucket_name}",
                    'reason': "No lifecycle policy found to manage object transitions and expirations",
                    'potential_savings': self._calculate_lifecycle_savings(metrics['size_bytes']),
                    'details': {
                        'current_size_bytes': metrics['size_bytes'],
                        'current_size_gb': metrics['size_bytes'] / (1024 * 1024 * 1024),
                        'suggested_policy': {
                            'transitions': [
                                {'days': self.infrequent_access_threshold_days, 'storage_class': 'STANDARD_IA'},
                                {'days': self.glacier_threshold_days, 'storage_class': 'GLACIER'},
                                {'days': self.deep_archive_threshold_days, 'storage_class': 'DEEP_ARCHIVE'}
                            ]
                        }
                    }
                })
            else:
                # Check if lifecycle policy could be improved
                can_improve = False
                has_ia_transition = False
                has_glacier_transition = False
                has_deep_archive_transition = False
                
                for rule in lifecycle['rules']:
                    if 'Transitions' in rule:
                        for transition in rule['Transitions']:
                            if transition.get('StorageClass') == 'STANDARD_IA':
                                has_ia_transition = True
                            elif transition.get('StorageClass') == 'GLACIER':
                                has_glacier_transition = True
                            elif transition.get('StorageClass') == 'DEEP_ARCHIVE':
                                has_deep_archive_transition = True
                
                if not (has_ia_transition and has_glacier_transition and has_deep_archive_transition):
                    can_improve = True
                
                if can_improve:
                    recommendations.append({
                        'resource_id': bucket_name,
                        'resource_type': 'S3 Bucket',
                        'recommendation_type': 'Improve Lifecycle Policy',
                        'recommendation': f"Improve lifecycle policy for bucket {bucket_name}",
                        'reason': "Current lifecycle policy could be optimized for better cost savings",
                        'potential_savings': self._calculate_lifecycle_savings(metrics['size_bytes']) / 2,  # Partial savings
                        'details': {
                            'current_size_bytes': metrics['size_bytes'],
                            'current_size_gb': metrics['size_bytes'] / (1024 * 1024 * 1024),
                            'missing_transitions': {
                                'standard_ia': not has_ia_transition,
                                'glacier': not has_glacier_transition,
                                'deep_archive': not has_deep_archive_transition
                            }
                        }
                    })
        
        return recommendations

    def _find_versioning_optimization_opportunities(self, buckets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Find opportunities to optimize versioning settings.

        Args:
            buckets: List of S3 buckets with metrics

        Returns:
            List of versioning optimization recommendations
        """
        self.logger.debug("Finding versioning optimization opportunities")
        recommendations = []
        
        for bucket in buckets:
            bucket_name = bucket['name']
            versioning = bucket['versioning']
            lifecycle = bucket['lifecycle']
            metrics = bucket['metrics']
            
            # Check if versioning is enabled but no expiration policy exists
            if versioning['enabled'] and lifecycle['has_lifecycle_policy']:
                has_version_expiration = False
                
                for rule in lifecycle['rules']:
                    if 'NoncurrentVersionExpiration' in rule:
                        has_version_expiration = True
                
                if not has_version_expiration:
                    recommendations.append({
                        'resource_id': bucket_name,
                        'resource_type': 'S3 Bucket',
                        'recommendation_type': 'Add Version Expiration',
                        'recommendation': f"Add noncurrent version expiration to lifecycle policy for bucket {bucket_name}",
                        'reason': "Versioning is enabled but old versions are never expired",
                        'potential_savings': self._calculate_versioning_savings(metrics['size_bytes']),
                        'details': {
                            'current_size_bytes': metrics['size_bytes'],
                            'current_size_gb': metrics['size_bytes'] / (1024 * 1024 * 1024),
                            'versioning_enabled': True,
                            'suggested_policy': {
                                'noncurrent_version_expiration': {
                                    'days': 90
                                }
                            }
                        }
                    })
        
        return recommendations

    def _find_unused_buckets(self, buckets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Find empty or unused buckets that could be deleted.

        Args:
            buckets: List of S3 buckets with metrics

        Returns:
            List of unused bucket recommendations
        """
        self.logger.debug("Finding unused buckets")
        recommendations = []
        
        for bucket in buckets:
            bucket_name = bucket['name']
            metrics = bucket['metrics']
            
            # Check if bucket is empty
            if metrics['object_count'] == 0:
                recommendations.append({
                    'resource_id': bucket_name,
                    'resource_type': 'S3 Bucket',
                    'recommendation_type': 'Delete Bucket',
                    'recommendation': f"Delete empty bucket {bucket_name}",
                    'reason': "Bucket is empty and not being used",
                    'potential_savings': 0.023 * 12,  # Nominal monthly cost for S3 bucket (estimated)
                    'details': {
                        'object_count': 0,
                        'creation_date': bucket['creation_date'].isoformat() if hasattr(bucket['creation_date'], 'isoformat') else str(bucket['creation_date'])
                    }
                })
        
        return recommendations

    def _calculate_ia_savings(self, size_bytes: float) -> float:
        """
        Calculate potential savings from moving to Standard-IA storage class.
        
        Args:
            size_bytes: Size of data in bytes
            
        Returns:
            Estimated annual savings in USD
        """
        size_gb = size_bytes / (1024 * 1024 * 1024)
        # Standard cost ~$0.023 per GB/month, Standard-IA ~$0.0125 per GB/month
        monthly_savings = size_gb * (0.023 - 0.0125)
        return monthly_savings * 12  # Annual savings

    def _calculate_glacier_savings(self, size_bytes: float) -> float:
        """
        Calculate potential savings from moving to Glacier storage class.
        
        Args:
            size_bytes: Size of data in bytes
            
        Returns:
            Estimated annual savings in USD
        """
        size_gb = size_bytes / (1024 * 1024 * 1024)
        # Standard cost ~$0.023 per GB/month, Glacier ~$0.004 per GB/month
        monthly_savings = size_gb * (0.023 - 0.004)
        return monthly_savings * 12  # Annual savings

    def _calculate_deep_archive_savings(self, size_bytes: float) -> float:
        """
        Calculate potential savings from moving to Glacier Deep Archive storage class.
        
        Args:
            size_bytes: Size of data in bytes
            
        Returns:
            Estimated annual savings in USD
        """
        size_gb = size_bytes / (1024 * 1024 * 1024)
        # Standard cost ~$0.023 per GB/month, Deep Archive ~$0.00099 per GB/month
        monthly_savings = size_gb * (0.023 - 0.00099)
        return monthly_savings * 12  # Annual savings

    def _calculate_lifecycle_savings(self, size_bytes: float) -> float:
        """
        Calculate potential savings from implementing a lifecycle policy.
        Assumes 60% of data would move to IA, 30% to Glacier, and 10% to Deep Archive over time.
        
        Args:
            size_bytes: Size of data in bytes
            
        Returns:
            Estimated annual savings in USD
        """
        size_gb = size_bytes / (1024 * 1024 * 1024)
        
        # Distribution of data across storage classes over time
        ia_size_gb = size_gb * 0.6
        glacier_size_gb = size_gb * 0.3
        deep_archive_size_gb = size_gb * 0.1
        
        # Calculate savings for each storage class
        ia_savings = ia_size_gb * (0.023 - 0.0125)
        glacier_savings = glacier_size_gb * (0.023 - 0.004)
        deep_archive_savings = deep_archive_size_gb * (0.023 - 0.00099)
        
        monthly_savings = ia_savings + glacier_savings + deep_archive_savings
        return monthly_savings * 12  # Annual savings

    def _calculate_versioning_savings(self, size_bytes: float) -> float:
        """
        Calculate potential savings from implementing version expiration.
        Assumes versioning increases storage by 50% on average without expiration.
        
        Args:
            size_bytes: Size of data in bytes
            
        Returns:
            Estimated annual savings in USD
        """
        size_gb = size_bytes / (1024 * 1024 * 1024)
        
        # Estimate that versions add 50% to storage costs
        version_size_gb = size_gb * 0.5
        
        # Calculate savings at standard storage rates
        monthly_savings = version_size_gb * 0.023
        return monthly_savings * 12  # Annual savings 