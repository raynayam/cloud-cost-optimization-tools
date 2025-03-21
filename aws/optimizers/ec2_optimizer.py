"""
EC2 optimizer module for generating AWS EC2 cost optimization recommendations.
"""

import boto3
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

class EC2Optimizer:
    """
    Analyzes EC2 instances and provides cost optimization recommendations.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize EC2 optimizer.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.logger = logging.getLogger("cloud-cost-optimizer")
        
        # Get EC2 optimization settings
        ec2_config = self.config['aws']['optimization'].get('ec2', {})
        self.min_cpu_utilization = ec2_config.get('min_cpu_utilization', 5.0)
        self.min_uptime_hours = ec2_config.get('min_uptime_hours', 168)
        
        # Initialize clients
        self._initialize_clients()
    
    def _initialize_clients(self) -> None:
        """Initialize AWS clients with appropriate credentials."""
        aws_config = self.config['aws']
        
        # Use profile if specified
        if 'profile' in aws_config:
            session = boto3.Session(profile_name=aws_config['profile'])
            self.ec2_client = session.client('ec2')
            self.cloudwatch_client = session.client('cloudwatch')
        # Otherwise use access keys
        elif 'access_key_id' in aws_config and 'secret_access_key' in aws_config:
            self.ec2_client = boto3.client(
                'ec2',
                aws_access_key_id=aws_config['access_key_id'],
                aws_secret_access_key=aws_config['secret_access_key'],
                region_name=self.config['general'].get('default_region', 'us-east-1')
            )
            self.cloudwatch_client = boto3.client(
                'cloudwatch',
                aws_access_key_id=aws_config['access_key_id'],
                aws_secret_access_key=aws_config['secret_access_key'],
                region_name=self.config['general'].get('default_region', 'us-east-1')
            )
        else:
            # Use default credentials provider chain
            self.ec2_client = boto3.client('ec2')
            self.cloudwatch_client = boto3.client('cloudwatch')
    
    def generate_recommendations(self, analysis_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate EC2 cost optimization recommendations.
        
        Args:
            analysis_data: Data from cost analysis phase
            
        Returns:
            List of EC2 optimization recommendations
        """
        self.logger.info("Generating EC2 cost optimization recommendations")
        
        # Get regions to analyze
        regions = self.config['aws'].get('regions', ['us-east-1'])
        
        all_recommendations = []
        
        for region in regions:
            try:
                # Set region for clients
                self.ec2_client = boto3.client(
                    'ec2', 
                    region_name=region,
                    aws_access_key_id=self.config['aws'].get('access_key_id'),
                    aws_secret_access_key=self.config['aws'].get('secret_access_key')
                ) if 'access_key_id' in self.config['aws'] else boto3.client('ec2', region_name=region)
                
                self.cloudwatch_client = boto3.client(
                    'cloudwatch', 
                    region_name=region,
                    aws_access_key_id=self.config['aws'].get('access_key_id'),
                    aws_secret_access_key=self.config['aws'].get('secret_access_key')
                ) if 'access_key_id' in self.config['aws'] else boto3.client('cloudwatch', region_name=region)
                
                # Find instances in the region
                instances = self._get_instances(region)
                
                # Find underutilized instances
                underutilized = self._find_underutilized_instances(instances, region)
                all_recommendations.extend(underutilized)
                
                # Find idle instances
                idle = self._find_idle_instances(instances, region)
                all_recommendations.extend(idle)
                
                # Find instances with opportunity for reserved instances
                ri_opportunities = self._find_ri_opportunities(instances, region)
                all_recommendations.extend(ri_opportunities)
                
            except Exception as e:
                self.logger.error(f"Error analyzing EC2 instances in region {region}: {str(e)}")
        
        # Sort recommendations by estimated savings
        all_recommendations.sort(key=lambda x: x.get('estimated_monthly_savings', 0), reverse=True)
        
        return all_recommendations
    
    def _get_instances(self, region: str) -> List[Dict[str, Any]]:
        """
        Get EC2 instances in the specified region.
        
        Args:
            region: AWS region
            
        Returns:
            List of EC2 instance details
        """
        try:
            response = self.ec2_client.describe_instances()
            
            instances = []
            for reservation in response.get('Reservations', []):
                for instance in reservation.get('Instances', []):
                    # Only include running instances
                    if instance.get('State', {}).get('Name') == 'running':
                        # Get instance name from tags
                        name = "Unnamed"
                        for tag in instance.get('Tags', []):
                            if tag.get('Key') == 'Name':
                                name = tag.get('Value')
                                break
                        
                        instances.append({
                            'instance_id': instance.get('InstanceId'),
                            'instance_name': name,
                            'instance_type': instance.get('InstanceType'),
                            'launch_time': instance.get('LaunchTime'),
                            'availability_zone': instance.get('Placement', {}).get('AvailabilityZone'),
                            'region': region,
                            'platform': instance.get('Platform', 'Linux/UNIX'),
                            'vpc_id': instance.get('VpcId'),
                            'private_ip': instance.get('PrivateIpAddress'),
                            'public_ip': instance.get('PublicIpAddress'),
                            'tags': instance.get('Tags', [])
                        })
            
            return instances
        except Exception as e:
            self.logger.error(f"Error getting EC2 instances in region {region}: {str(e)}")
            return []
    
    def _find_underutilized_instances(self, instances: List[Dict[str, Any]], region: str) -> List[Dict[str, Any]]:
        """
        Find underutilized EC2 instances based on CPU utilization.
        
        Args:
            instances: List of EC2 instances
            region: AWS region
            
        Returns:
            List of recommendations for underutilized instances
        """
        recommendations = []
        
        for instance in instances:
            instance_id = instance.get('instance_id')
            instance_type = instance.get('instance_type')
            
            # Get CPU utilization metrics
            avg_cpu = self._get_average_cpu_utilization(instance_id, region)
            
            # Check if instance is underutilized
            if avg_cpu is not None and avg_cpu < self.min_cpu_utilization:
                # Determine recommended instance type
                recommended_type = self._recommend_instance_type(instance_type, avg_cpu)
                
                if recommended_type and recommended_type != instance_type:
                    # Calculate estimated savings
                    savings = self._calculate_downsizing_savings(instance_type, recommended_type, region)
                    
                    recommendations.append({
                        'instance_id': instance_id,
                        'instance_name': instance.get('instance_name'),
                        'region': region,
                        'recommendation_type': 'Rightsize Instance',
                        'current_state': {
                            'instance_type': instance_type,
                            'avg_cpu_utilization': avg_cpu,
                        },
                        'recommended_state': {
                            'instance_type': recommended_type,
                            'expected_cpu_utilization': avg_cpu * 2 if 'micro' not in recommended_type else avg_cpu * 1.5,
                        },
                        'estimated_monthly_savings': savings,
                        'confidence': 'High' if avg_cpu < 2.0 else 'Medium',
                        'details': f"Instance has average CPU utilization of {avg_cpu:.1f}%, which is below the threshold of {self.min_cpu_utilization}%. Consider downsizing to {recommended_type}."
                    })
        
        return recommendations
    
    def _get_average_cpu_utilization(self, instance_id: str, region: str) -> Optional[float]:
        """
        Get average CPU utilization for an EC2 instance over the lookback period.
        
        Args:
            instance_id: EC2 instance ID
            region: AWS region
            
        Returns:
            Average CPU utilization percentage or None if data not available
        """
        try:
            # Set lookback period
            lookback_days = self.config['aws']['analysis'].get('lookback_days', 30)
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=lookback_days)
            
            # Get CloudWatch metrics
            response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/EC2',
                MetricName='CPUUtilization',
                Dimensions=[
                    {
                        'Name': 'InstanceId',
                        'Value': instance_id
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # Daily average
                Statistics=['Average']
            )
            
            # Calculate average CPU utilization
            datapoints = response.get('Datapoints', [])
            if not datapoints:
                return None
            
            total_cpu = sum(dp.get('Average', 0) for dp in datapoints)
            avg_cpu = total_cpu / len(datapoints)
            
            return avg_cpu
        except Exception as e:
            self.logger.error(f"Error getting CPU utilization for instance {instance_id}: {str(e)}")
            return None
    
    def _recommend_instance_type(self, current_type: str, avg_cpu: float) -> Optional[str]:
        """
        Recommend an appropriate instance type based on current usage.
        
        Args:
            current_type: Current instance type
            avg_cpu: Average CPU utilization
            
        Returns:
            Recommended instance type or None if no recommendation
        """
        # This is a simplified recommendation. In a real-world scenario,
        # we would consider more factors like memory, network, etc.
        
        # Extract instance family and size
        if '.' not in current_type:
            return None
        
        family, size = current_type.split('.')
        
        # Map of instance size downgrades
        size_map = {
            'xlarge': 'large',
            'large': 'medium',
            'medium': 'small',
            '2xlarge': 'xlarge',
            '4xlarge': '2xlarge',
            '8xlarge': '4xlarge',
            '16xlarge': '8xlarge',
            '12xlarge': '6xlarge',
            '24xlarge': '12xlarge',
            '10xlarge': '4xlarge',
            '6xlarge': '3xlarge',
            '3xlarge': 'xlarge'
        }
        
        # If CPU usage is very low, recommend downsizing
        if size in size_map and avg_cpu < self.min_cpu_utilization:
            return f"{family}.{size_map[size]}"
        
        return None
    
    def _calculate_downsizing_savings(self, current_type: str, recommended_type: str, region: str) -> float:
        """
        Calculate estimated monthly savings from EC2 instance downsizing.
        
        Args:
            current_type: Current instance type
            recommended_type: Recommended instance type
            region: AWS region
            
        Returns:
            Estimated monthly savings in USD
        """
        # This is a simplified calculation. In a real-world scenario,
        # we would use actual pricing data from AWS Price List API.
        
        # Rough pricing estimates for on-demand Linux instances (USD per hour)
        pricing = {
            't3.nano': 0.0052,
            't3.micro': 0.0104,
            't3.small': 0.0208,
            't3.medium': 0.0416,
            't3.large': 0.0832,
            't3.xlarge': 0.1664,
            't3.2xlarge': 0.3328,
            'm5.large': 0.096,
            'm5.xlarge': 0.192,
            'm5.2xlarge': 0.384,
            'm5.4xlarge': 0.768,
            'm5.8xlarge': 1.536,
            'm5.12xlarge': 2.304,
            'm5.16xlarge': 3.072,
            'm5.24xlarge': 4.608,
            'c5.large': 0.085,
            'c5.xlarge': 0.17,
            'c5.2xlarge': 0.34,
            'c5.4xlarge': 0.68,
            'c5.9xlarge': 1.53,
            'c5.12xlarge': 2.04,
            'c5.18xlarge': 3.06,
            'c5.24xlarge': 4.08,
            'r5.large': 0.126,
            'r5.xlarge': 0.252,
            'r5.2xlarge': 0.504,
            'r5.4xlarge': 1.008,
            'r5.8xlarge': 2.016,
            'r5.12xlarge': 3.024,
            'r5.16xlarge': 4.032,
            'r5.24xlarge': 6.048,
        }
        
        # Get pricing for current and recommended types
        current_hourly = pricing.get(current_type, 0.0)
        recommended_hourly = pricing.get(recommended_type, 0.0)
        
        # If we don't have pricing data, make a rough estimate
        if current_hourly == 0.0 or recommended_hourly == 0.0:
            # Extract size from types
            if '.' not in current_type or '.' not in recommended_type:
                return 0.0
            
            current_family, current_size = current_type.split('.')
            recommended_family, recommended_size = recommended_type.split('.')
            
            # Rough size multipliers
            size_multipliers = {
                'nano': 0.25,
                'micro': 0.5,
                'small': 1,
                'medium': 2,
                'large': 4,
                'xlarge': 8,
                '2xlarge': 16,
                '4xlarge': 32,
                '8xlarge': 64,
                '12xlarge': 96,
                '16xlarge': 128,
                '24xlarge': 192
            }
            
            # If we don't have the exact instance types, estimate based on size difference
            if current_size in size_multipliers and recommended_size in size_multipliers:
                size_ratio = size_multipliers[current_size] / size_multipliers[recommended_size]
                # Assume linear pricing based on size
                return (size_ratio - 1) * 30 * 24 * 0.1  # Rough estimate of $0.10/hour for a medium instance
        
        # Calculate monthly savings (30 days, 24 hours)
        hourly_savings = current_hourly - recommended_hourly
        monthly_savings = hourly_savings * 24 * 30
        
        return monthly_savings
    
    def _find_idle_instances(self, instances: List[Dict[str, Any]], region: str) -> List[Dict[str, Any]]:
        """
        Find idle EC2 instances with no significant CPU activity.
        
        Args:
            instances: List of EC2 instances
            region: AWS region
            
        Returns:
            List of recommendations for idle instances
        """
        recommendations = []
        
        for instance in instances:
            instance_id = instance.get('instance_id')
            instance_type = instance.get('instance_type')
            
            # Get CPU utilization metrics
            avg_cpu = self._get_average_cpu_utilization(instance_id, region)
            
            # Check if instance is idle (very low CPU)
            if avg_cpu is not None and avg_cpu < 1.0:
                # Get hourly cost of the instance
                hourly_cost = self._get_instance_hourly_cost(instance_type, region)
                monthly_cost = hourly_cost * 24 * 30
                
                recommendations.append({
                    'instance_id': instance_id,
                    'instance_name': instance.get('instance_name'),
                    'region': region,
                    'recommendation_type': 'Terminate Idle Instance',
                    'current_state': {
                        'instance_type': instance_type,
                        'avg_cpu_utilization': avg_cpu,
                    },
                    'recommended_state': {
                        'action': 'Terminate'
                    },
                    'estimated_monthly_savings': monthly_cost,
                    'confidence': 'High' if avg_cpu < 0.5 else 'Medium',
                    'details': f"Instance has average CPU utilization of {avg_cpu:.1f}%, indicating it might be idle. Consider terminating if not needed."
                })
        
        return recommendations
    
    def _get_instance_hourly_cost(self, instance_type: str, region: str) -> float:
        """
        Get the hourly cost of an EC2 instance type.
        
        Args:
            instance_type: EC2 instance type
            region: AWS region
            
        Returns:
            Hourly cost in USD
        """
        # This is a simplified pricing lookup. In a real-world scenario,
        # we would use the AWS Price List API for accurate pricing.
        
        # Rough pricing estimates for on-demand Linux instances (USD per hour)
        pricing = {
            't3.nano': 0.0052,
            't3.micro': 0.0104,
            't3.small': 0.0208,
            't3.medium': 0.0416,
            't3.large': 0.0832,
            't3.xlarge': 0.1664,
            't3.2xlarge': 0.3328,
            'm5.large': 0.096,
            'm5.xlarge': 0.192,
            'm5.2xlarge': 0.384,
            'm5.4xlarge': 0.768,
            'm5.8xlarge': 1.536,
            'm5.12xlarge': 2.304,
            'm5.16xlarge': 3.072,
            'm5.24xlarge': 4.608,
            'c5.large': 0.085,
            'c5.xlarge': 0.17,
            'c5.2xlarge': 0.34,
            'c5.4xlarge': 0.68,
            'c5.9xlarge': 1.53,
            'c5.12xlarge': 2.04,
            'c5.18xlarge': 3.06,
            'c5.24xlarge': 4.08,
            'r5.large': 0.126,
            'r5.xlarge': 0.252,
            'r5.2xlarge': 0.504,
            'r5.4xlarge': 1.008,
            'r5.8xlarge': 2.016,
            'r5.12xlarge': 3.024,
            'r5.16xlarge': 4.032,
            'r5.24xlarge': 6.048,
        }
        
        return pricing.get(instance_type, 0.1)  # Default to $0.1/hour if unknown
    
    def _find_ri_opportunities(self, instances: List[Dict[str, Any]], region: str) -> List[Dict[str, Any]]:
        """
        Find EC2 instances that are good candidates for Reserved Instances.
        
        Args:
            instances: List of EC2 instances
            region: AWS region
            
        Returns:
            List of recommendations for Reserved Instance purchases
        """
        recommendations = []
        
        # Group instances by type
        instance_types = {}
        for instance in instances:
            instance_type = instance.get('instance_type')
            uptime_hours = self._get_instance_uptime_hours(instance)
            
            if uptime_hours >= self.min_uptime_hours:
                instance_types[instance_type] = instance_types.get(instance_type, 0) + 1
        
        # Generate recommendations for types with multiple instances
        for instance_type, count in instance_types.items():
            if count >= 2:
                hourly_cost = self._get_instance_hourly_cost(instance_type, region)
                on_demand_monthly = hourly_cost * 24 * 30 * count
                ri_monthly = on_demand_monthly * 0.6  # Assume 40% savings with RIs
                savings = on_demand_monthly - ri_monthly
                
                recommendations.append({
                    'instance_id': f"multiple_{instance_type}",
                    'instance_name': f"{count} x {instance_type} instances",
                    'region': region,
                    'recommendation_type': 'Purchase Reserved Instances',
                    'current_state': {
                        'instance_type': instance_type,
                        'count': count,
                        'pricing_model': 'On-Demand'
                    },
                    'recommended_state': {
                        'instance_type': instance_type,
                        'count': count,
                        'pricing_model': 'Reserved Instance (1 year)'
                    },
                    'estimated_monthly_savings': savings,
                    'confidence': 'High' if count > 5 else 'Medium',
                    'details': f"Found {count} instances of type {instance_type} that are good candidates for Reserved Instances. Consider purchasing Reserved Instances for approximately 40% savings."
                })
        
        return recommendations
    
    def _get_instance_uptime_hours(self, instance: Dict[str, Any]) -> float:
        """
        Calculate the uptime hours of an EC2 instance.
        
        Args:
            instance: EC2 instance details
            
        Returns:
            Uptime hours
        """
        launch_time = instance.get('launch_time')
        if not launch_time:
            return 0
        
        # Calculate hours between launch time and now
        now = datetime.utcnow()
        uptime = now - launch_time.replace(tzinfo=None)
        uptime_hours = uptime.total_seconds() / 3600
        
        return uptime_hours 