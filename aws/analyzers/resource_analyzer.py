#!/usr/bin/env python3
"""
AWS resource analyzer module for Cloud Cost Optimization Tools.

This module analyzes AWS resource utilization across multiple services.
"""

import logging
import boto3
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import time

class AWSResourceAnalyzer:
    """
    Analyzes AWS resources utilization and provides detailed insights.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize AWS resource analyzer with configuration settings.

        Args:
            config: Configuration dictionary containing AWS settings
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Get analysis settings
        self.settings = config['aws'].get('analysis', {})
        self.lookback_days = self.settings.get('lookback_days', 14)
        self.services = self.settings.get('services', ['ec2', 's3', 'rds', 'ebs'])
        
        # Initialize AWS clients
        self.regions = config['aws'].get('regions', ['us-east-1'])
        self.ec2_clients = {}
        self.s3_client = None
        self.rds_clients = {}
        self.cloudwatch_clients = {}
        self._initialize_clients()

    def _initialize_clients(self):
        """Initialize AWS clients for resource analysis."""
        self.logger.debug("Initializing AWS clients for resource analyzer")
        
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
            if 'ec2' in self.services:
                self.ec2_clients[region] = session.client('ec2', region_name=region)
            
            if 'rds' in self.services:
                self.rds_clients[region] = session.client('rds', region_name=region)
            
            self.cloudwatch_clients[region] = session.client('cloudwatch', region_name=region)
        
        # S3 is a global service
        if 's3' in self.services:
            self.s3_client = session.client('s3', region_name=self.regions[0])

    def analyze_resources(self) -> Dict[str, Any]:
        """
        Analyze AWS resources across enabled services.

        Returns:
            Dictionary containing resource analysis results
        """
        self.logger.info("Starting AWS resource analysis")
        results = {}
        
        try:
            # Analyze EC2 resources if enabled
            if 'ec2' in self.services:
                self.logger.info("Analyzing EC2 resources")
                results['ec2'] = self._analyze_ec2()
            
            # Analyze S3 resources if enabled
            if 's3' in self.services:
                self.logger.info("Analyzing S3 resources")
                results['s3'] = self._analyze_s3()
            
            # Analyze RDS resources if enabled
            if 'rds' in self.services:
                self.logger.info("Analyzing RDS resources")
                results['rds'] = self._analyze_rds()
            
            # Analyze EBS resources if enabled
            if 'ebs' in self.services:
                self.logger.info("Analyzing EBS resources")
                results['ebs'] = self._analyze_ebs()
            
            self.logger.info("AWS resource analysis completed")
            return results
        
        except Exception as e:
            self.logger.error(f"Error during AWS resource analysis: {str(e)}")
            return {"error": str(e)}

    def _analyze_ec2(self) -> Dict[str, Any]:
        """
        Analyze EC2 instances across all regions.

        Returns:
            Dictionary containing EC2 resource analysis
        """
        ec2_data = {
            "instances_by_region": {},
            "instances_by_type": {},
            "instances_by_state": {
                "running": 0,
                "stopped": 0,
                "terminated": 0,
                "other": 0
            },
            "total_instances": 0,
            "utilization": {}
        }
        
        # Process each region
        for region, ec2 in self.ec2_clients.items():
            instances = []
            cloudwatch = self.cloudwatch_clients[region]
            
            # Get all instances in the region
            try:
                paginator = ec2.get_paginator('describe_instances')
                for page in paginator.paginate():
                    for reservation in page['Reservations']:
                        for instance in reservation['Instances']:
                            instance_id = instance['InstanceId']
                            instance_type = instance['InstanceType']
                            state = instance['State']['Name']
                            
                            # Get instance tags
                            tags = {}
                            if 'Tags' in instance:
                                for tag in instance['Tags']:
                                    tags[tag['Key']] = tag['Value']
                            
                            # Update counters
                            ec2_data["total_instances"] += 1
                            
                            if state == 'running':
                                ec2_data["instances_by_state"]["running"] += 1
                            elif state == 'stopped':
                                ec2_data["instances_by_state"]["stopped"] += 1
                            elif state == 'terminated':
                                ec2_data["instances_by_state"]["terminated"] += 1
                            else:
                                ec2_data["instances_by_state"]["other"] += 1
                            
                            # Update instance type counts
                            if instance_type not in ec2_data["instances_by_type"]:
                                ec2_data["instances_by_type"][instance_type] = 0
                            ec2_data["instances_by_type"][instance_type] += 1
                            
                            # Get utilization metrics for running instances
                            utilization = {}
                            if state == 'running':
                                utilization = self._get_ec2_utilization(cloudwatch, instance_id)
                            
                            # Add instance details
                            instances.append({
                                "instance_id": instance_id,
                                "instance_type": instance_type,
                                "state": state,
                                "az": instance.get('Placement', {}).get('AvailabilityZone', 'unknown'),
                                "launch_time": instance.get('LaunchTime', '').isoformat() if 'LaunchTime' in instance else '',
                                "tags": tags,
                                "utilization": utilization
                            })
            
            except Exception as e:
                self.logger.error(f"Error analyzing EC2 instances in {region}: {str(e)}")
            
            # Add region data
            ec2_data["instances_by_region"][region] = instances
        
        # Calculate average utilization across all instances
        utilization_data = {}
        running_instances = 0
        
        for region, instances in ec2_data["instances_by_region"].items():
            for instance in instances:
                if instance["state"] == "running" and "utilization" in instance:
                    running_instances += 1
                    for metric, value in instance["utilization"].items():
                        if metric not in utilization_data:
                            utilization_data[metric] = []
                        utilization_data[metric].append(value)
        
        # Calculate averages
        for metric, values in utilization_data.items():
            if values:
                ec2_data["utilization"][metric] = sum(values) / len(values)
        
        return ec2_data

    def _get_ec2_utilization(self, cloudwatch: Any, instance_id: str) -> Dict[str, float]:
        """
        Get EC2 instance utilization metrics.

        Args:
            cloudwatch: CloudWatch client
            instance_id: EC2 instance ID

        Returns:
            Dictionary containing utilization metrics
        """
        metrics = {
            "CPUUtilization": 0.0,
            "NetworkIn": 0.0,
            "NetworkOut": 0.0,
            "DiskReadOps": 0.0,
            "DiskWriteOps": 0.0
        }
        
        end_time = datetime.now()
        start_time = end_time - timedelta(days=self.lookback_days)
        
        try:
            for metric_name in metrics.keys():
                response = cloudwatch.get_metric_statistics(
                    Namespace='AWS/EC2',
                    MetricName=metric_name,
                    Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=86400,  # 1 day
                    Statistics=['Average']
                )
                
                if 'Datapoints' in response and response['Datapoints']:
                    # Calculate the average of all datapoints
                    metrics[metric_name] = sum(point['Average'] for point in response['Datapoints']) / len(response['Datapoints'])
        
        except Exception as e:
            self.logger.warning(f"Error getting utilization metrics for instance {instance_id}: {str(e)}")
        
        return metrics

    def _analyze_s3(self) -> Dict[str, Any]:
        """
        Analyze S3 buckets.

        Returns:
            Dictionary containing S3 resource analysis
        """
        s3_data = {
            "total_buckets": 0,
            "total_size_bytes": 0,
            "buckets": [],
            "storage_class_distribution": {}
        }
        
        try:
            # List all buckets
            response = self.s3_client.list_buckets()
            s3_data["total_buckets"] = len(response['Buckets'])
            
            # Get metrics for each bucket
            for bucket in response['Buckets']:
                bucket_name = bucket['Name']
                bucket_details = {
                    "name": bucket_name,
                    "creation_date": bucket.get('CreationDate', '').isoformat() if 'CreationDate' in bucket else '',
                    "size_bytes": 0,
                    "object_count": 0,
                    "storage_classes": {}
                }
                
                # Get bucket location
                try:
                    location = self.s3_client.get_bucket_location(Bucket=bucket_name)
                    bucket_details["region"] = location.get('LocationConstraint', 'us-east-1') or 'us-east-1'
                except Exception as e:
                    self.logger.warning(f"Error getting location for bucket {bucket_name}: {str(e)}")
                    bucket_details["region"] = "unknown"
                
                # Get bucket metrics from CloudWatch
                region = bucket_details.get("region", "us-east-1")
                cloudwatch = self.cloudwatch_clients.get(region, self.cloudwatch_clients[self.regions[0]])
                
                try:
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
                        bucket_details["size_bytes"] = size_response['Datapoints'][-1]['Average']
                        s3_data["total_size_bytes"] += bucket_details["size_bytes"]
                    
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
                        bucket_details["object_count"] = count_response['Datapoints'][-1]['Average']
                except Exception as e:
                    self.logger.warning(f"Error getting metrics for bucket {bucket_name}: {str(e)}")
                
                # Get storage class distribution (sample of objects)
                try:
                    paginator = self.s3_client.get_paginator('list_objects_v2')
                    storage_classes = {}
                    
                    for page in paginator.paginate(Bucket=bucket_name, MaxKeys=1000):
                        if 'Contents' not in page:
                            continue
                            
                        for obj in page['Contents']:
                            storage_class = obj.get('StorageClass', 'STANDARD')
                            
                            # Update storage class count for bucket
                            if storage_class not in storage_classes:
                                storage_classes[storage_class] = 0
                            storage_classes[storage_class] += 1
                            
                            # Update global storage class distribution
                            if storage_class not in s3_data["storage_class_distribution"]:
                                s3_data["storage_class_distribution"][storage_class] = 0
                            s3_data["storage_class_distribution"][storage_class] += 1
                    
                    bucket_details["storage_classes"] = storage_classes
                except Exception as e:
                    self.logger.warning(f"Error getting storage classes for bucket {bucket_name}: {str(e)}")
                
                s3_data["buckets"].append(bucket_details)
        
        except Exception as e:
            self.logger.error(f"Error analyzing S3 buckets: {str(e)}")
        
        return s3_data

    def _analyze_rds(self) -> Dict[str, Any]:
        """
        Analyze RDS instances across all regions.

        Returns:
            Dictionary containing RDS resource analysis
        """
        rds_data = {
            "instances_by_region": {},
            "instances_by_engine": {},
            "instances_by_class": {},
            "total_instances": 0,
            "storage_allocated_gb": 0,
            "utilization": {}
        }
        
        # Process each region
        for region, rds in self.rds_clients.items():
            instances = []
            cloudwatch = self.cloudwatch_clients[region]
            
            try:
                # Get all DB instances in the region
                paginator = rds.get_paginator('describe_db_instances')
                for page in paginator.paginate():
                    for instance in page['DBInstances']:
                        instance_id = instance['DBInstanceIdentifier']
                        instance_class = instance['DBInstanceClass']
                        engine = instance['Engine']
                        status = instance['DBInstanceStatus']
                        
                        # Update counters
                        rds_data["total_instances"] += 1
                        
                        # Update engine counts
                        if engine not in rds_data["instances_by_engine"]:
                            rds_data["instances_by_engine"][engine] = 0
                        rds_data["instances_by_engine"][engine] += 1
                        
                        # Update instance class counts
                        if instance_class not in rds_data["instances_by_class"]:
                            rds_data["instances_by_class"][instance_class] = 0
                        rds_data["instances_by_class"][instance_class] += 1
                        
                        # Add storage allocation
                        storage_gb = instance.get('AllocatedStorage', 0)
                        rds_data["storage_allocated_gb"] += storage_gb
                        
                        # Get utilization metrics
                        utilization = self._get_rds_utilization(cloudwatch, instance_id)
                        
                        # Add instance details
                        instances.append({
                            "instance_id": instance_id,
                            "instance_class": instance_class,
                            "engine": engine,
                            "engine_version": instance.get('EngineVersion', ''),
                            "status": status,
                            "storage_gb": storage_gb,
                            "multi_az": instance.get('MultiAZ', False),
                            "publicly_accessible": instance.get('PubliclyAccessible', False),
                            "utilization": utilization
                        })
            
            except Exception as e:
                self.logger.error(f"Error analyzing RDS instances in {region}: {str(e)}")
            
            # Add region data
            rds_data["instances_by_region"][region] = instances
        
        # Calculate average utilization across all instances
        utilization_data = {}
        active_instances = 0
        
        for region, instances in rds_data["instances_by_region"].items():
            for instance in instances:
                if instance["status"] == "available" and "utilization" in instance:
                    active_instances += 1
                    for metric, value in instance["utilization"].items():
                        if metric not in utilization_data:
                            utilization_data[metric] = []
                        utilization_data[metric].append(value)
        
        # Calculate averages
        for metric, values in utilization_data.items():
            if values:
                rds_data["utilization"][metric] = sum(values) / len(values)
        
        return rds_data

    def _get_rds_utilization(self, cloudwatch: Any, instance_id: str) -> Dict[str, float]:
        """
        Get RDS instance utilization metrics.

        Args:
            cloudwatch: CloudWatch client
            instance_id: RDS instance ID

        Returns:
            Dictionary containing utilization metrics
        """
        metrics = {
            "CPUUtilization": 0.0,
            "DatabaseConnections": 0.0,
            "FreeableMemory": 0.0,
            "ReadIOPS": 0.0,
            "WriteIOPS": 0.0,
            "FreeStorageSpace": 0.0
        }
        
        end_time = datetime.now()
        start_time = end_time - timedelta(days=self.lookback_days)
        
        try:
            for metric_name in metrics.keys():
                response = cloudwatch.get_metric_statistics(
                    Namespace='AWS/RDS',
                    MetricName=metric_name,
                    Dimensions=[{'Name': 'DBInstanceIdentifier', 'Value': instance_id}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=86400,  # 1 day
                    Statistics=['Average']
                )
                
                if 'Datapoints' in response and response['Datapoints']:
                    # Calculate the average of all datapoints
                    metrics[metric_name] = sum(point['Average'] for point in response['Datapoints']) / len(response['Datapoints'])
        
        except Exception as e:
            self.logger.warning(f"Error getting utilization metrics for RDS instance {instance_id}: {str(e)}")
        
        return metrics

    def _analyze_ebs(self) -> Dict[str, Any]:
        """
        Analyze EBS volumes across all regions.

        Returns:
            Dictionary containing EBS resource analysis
        """
        ebs_data = {
            "volumes_by_region": {},
            "volumes_by_type": {},
            "volumes_by_state": {
                "available": 0,
                "in-use": 0,
                "other": 0
            },
            "total_volumes": 0,
            "total_size_gb": 0,
            "unattached_volumes": 0,
            "unattached_size_gb": 0
        }
        
        # Process each region
        for region, ec2 in self.ec2_clients.items():
            volumes = []
            
            try:
                # Get all volumes in the region
                paginator = ec2.get_paginator('describe_volumes')
                for page in paginator.paginate():
                    for volume in page['Volumes']:
                        volume_id = volume['VolumeId']
                        volume_type = volume['VolumeType']
                        state = volume['State']
                        size_gb = volume['Size']
                        
                        # Update counters
                        ebs_data["total_volumes"] += 1
                        ebs_data["total_size_gb"] += size_gb
                        
                        # Update volume type counts
                        if volume_type not in ebs_data["volumes_by_type"]:
                            ebs_data["volumes_by_type"][volume_type] = 0
                        ebs_data["volumes_by_type"][volume_type] += 1
                        
                        # Update state counts
                        if state == 'available':
                            ebs_data["volumes_by_state"]["available"] += 1
                            ebs_data["unattached_volumes"] += 1
                            ebs_data["unattached_size_gb"] += size_gb
                        elif state == 'in-use':
                            ebs_data["volumes_by_state"]["in-use"] += 1
                        else:
                            ebs_data["volumes_by_state"]["other"] += 1
                        
                        # Get attachment information
                        attachments = []
                        if 'Attachments' in volume:
                            for attachment in volume['Attachments']:
                                attachments.append({
                                    "instance_id": attachment.get('InstanceId', ''),
                                    "device": attachment.get('Device', ''),
                                    "state": attachment.get('State', '')
                                })
                        
                        # Add volume details
                        volumes.append({
                            "volume_id": volume_id,
                            "volume_type": volume_type,
                            "state": state,
                            "size_gb": size_gb,
                            "iops": volume.get('Iops', 0),
                            "encrypted": volume.get('Encrypted', False),
                            "multi_attach_enabled": volume.get('MultiAttachEnabled', False),
                            "availability_zone": volume.get('AvailabilityZone', ''),
                            "create_time": volume.get('CreateTime', '').isoformat() if 'CreateTime' in volume else '',
                            "attachments": attachments
                        })
            
            except Exception as e:
                self.logger.error(f"Error analyzing EBS volumes in {region}: {str(e)}")
            
            # Add region data
            ebs_data["volumes_by_region"][region] = volumes
        
        return ebs_data 