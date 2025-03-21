"""
AWS Cost Explorer module for analyzing AWS cost data.
"""

import boto3
import logging
import datetime
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

class AWSCostExplorer:
    """
    Analyzes AWS cost data using AWS Cost Explorer API.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize AWS Cost Explorer analyzer.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.logger = logging.getLogger("cloud-cost-optimizer")
        
        # Initialize the Cost Explorer client
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Initialize the AWS Cost Explorer client with appropriate credentials."""
        aws_config = self.config['aws']
        
        # Use profile if specified
        if 'profile' in aws_config:
            session = boto3.Session(profile_name=aws_config['profile'])
            self.client = session.client('ce')
        # Otherwise use access keys
        elif 'access_key_id' in aws_config and 'secret_access_key' in aws_config:
            self.client = boto3.client(
                'ce',
                aws_access_key_id=aws_config['access_key_id'],
                aws_secret_access_key=aws_config['secret_access_key'],
                region_name=self.config['general'].get('default_region', 'us-east-1')
            )
        else:
            # Use default credentials provider chain
            self.client = boto3.client('ce')
    
    def analyze_costs(self, service: Optional[str] = None, region: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze AWS costs using Cost Explorer.
        
        Args:
            service: Specific AWS service to analyze (e.g., ec2, s3)
            region: Specific AWS region to analyze
            
        Returns:
            Dictionary containing cost analysis results
        """
        self.logger.info(f"Analyzing AWS costs for service={service}, region={region}")
        
        # Get configuration
        aws_config = self.config['aws']
        lookback_days = aws_config['analysis']['lookback_days']
        
        # Set up time period
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=lookback_days)
        
        # Prepare filters
        filters = self._prepare_filters(service, region)
        
        # Get cost and usage data
        cost_data = self._get_cost_and_usage(start_date, end_date, filters)
        
        # Get cost by service
        cost_by_service = self._get_cost_by_service(start_date, end_date, filters)
        
        # Get cost by region if no specific region is specified
        cost_by_region = {}
        if not region:
            cost_by_region = self._get_cost_by_region(start_date, end_date, filters)
        
        # Get recommendations from AWS Cost Explorer
        recommendations = self._get_rightsizing_recommendations()
        
        # Compile results
        results = {
            'time_period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'total_cost': self._get_total_cost(cost_data),
            'daily_costs': self._process_daily_costs(cost_data),
            'cost_by_service': cost_by_service,
            'cost_by_region': cost_by_region,
            'savings_recommendations': recommendations
        }
        
        return results
    
    def _prepare_filters(self, service: Optional[str] = None, region: Optional[str] = None) -> Dict[str, Any]:
        """
        Prepare filters for Cost Explorer API.
        
        Args:
            service: Specific AWS service to filter
            region: Specific AWS region to filter
            
        Returns:
            Filters dictionary for Cost Explorer API
        """
        filters = {}
        dimensions = []
        
        # Add service filter
        if service:
            dimensions.append({
                'Key': 'SERVICE',
                'Values': [service.upper()]
            })
        # Otherwise use service include/exclude lists from config
        else:
            include_services = self.config['aws']['analysis'].get('include_services', [])
            exclude_services = self.config['aws']['analysis'].get('exclude_services', [])
            
            if include_services:
                dimensions.append({
                    'Key': 'SERVICE',
                    'Values': [s.upper() for s in include_services]
                })
            
            if exclude_services:
                dimensions.append({
                    'Key': 'SERVICE',
                    'Values': [s.upper() for s in exclude_services],
                    'MatchOptions': ['EXCLUDE']
                })
        
        # Add region filter
        if region:
            dimensions.append({
                'Key': 'REGION',
                'Values': [region]
            })
        # Otherwise use regions from config
        else:
            regions = self.config['aws'].get('regions', [])
            if regions:
                dimensions.append({
                    'Key': 'REGION',
                    'Values': regions
                })
        
        if dimensions:
            filters['Dimensions'] = {'Key': 'DIMENSION', 'Values': dimensions}
        
        return filters
    
    def _get_cost_and_usage(self, start_date: datetime.date, end_date: datetime.date, 
                            filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get cost and usage data from AWS Cost Explorer.
        
        Args:
            start_date: Start date for cost data
            end_date: End date for cost data
            filters: Filters for Cost Explorer API
            
        Returns:
            Cost and usage data from Cost Explorer
        """
        try:
            response = self.client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date.isoformat(),
                    'End': end_date.isoformat()
                },
                Granularity='DAILY',
                Metrics=['UnblendedCost'],
                GroupBy=[{
                    'Type': 'DIMENSION',
                    'Key': 'SERVICE'
                }],
                Filter=filters
            )
            return response
        except Exception as e:
            self.logger.error(f"Error getting cost and usage data: {str(e)}")
            return {'ResultsByTime': []}
    
    def _get_cost_by_service(self, start_date: datetime.date, end_date: datetime.date, 
                             filters: Dict[str, Any]) -> Dict[str, float]:
        """
        Get cost breakdown by service.
        
        Args:
            start_date: Start date for cost data
            end_date: End date for cost data
            filters: Filters for Cost Explorer API
            
        Returns:
            Dictionary mapping service names to costs
        """
        try:
            response = self.client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date.isoformat(),
                    'End': end_date.isoformat()
                },
                Granularity='MONTHLY',
                Metrics=['UnblendedCost'],
                GroupBy=[{
                    'Type': 'DIMENSION',
                    'Key': 'SERVICE'
                }],
                Filter=filters
            )
            
            result = {}
            for time_period in response.get('ResultsByTime', []):
                for group in time_period.get('Groups', []):
                    service = group.get('Keys', ['Unknown'])[0]
                    amount = float(group.get('Metrics', {}).get('UnblendedCost', {}).get('Amount', 0))
                    result[service] = result.get(service, 0) + amount
            
            return result
        except Exception as e:
            self.logger.error(f"Error getting cost by service: {str(e)}")
            return {}
    
    def _get_cost_by_region(self, start_date: datetime.date, end_date: datetime.date, 
                           filters: Dict[str, Any]) -> Dict[str, float]:
        """
        Get cost breakdown by region.
        
        Args:
            start_date: Start date for cost data
            end_date: End date for cost data
            filters: Filters for Cost Explorer API
            
        Returns:
            Dictionary mapping region names to costs
        """
        try:
            response = self.client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date.isoformat(),
                    'End': end_date.isoformat()
                },
                Granularity='MONTHLY',
                Metrics=['UnblendedCost'],
                GroupBy=[{
                    'Type': 'DIMENSION',
                    'Key': 'REGION'
                }],
                Filter=filters
            )
            
            result = {}
            for time_period in response.get('ResultsByTime', []):
                for group in time_period.get('Groups', []):
                    region = group.get('Keys', ['Unknown'])[0]
                    amount = float(group.get('Metrics', {}).get('UnblendedCost', {}).get('Amount', 0))
                    result[region] = result.get(region, 0) + amount
            
            return result
        except Exception as e:
            self.logger.error(f"Error getting cost by region: {str(e)}")
            return {}
    
    def _get_rightsizing_recommendations(self) -> List[Dict[str, Any]]:
        """
        Get rightsizing recommendations from AWS Cost Explorer.
        
        Returns:
            List of rightsizing recommendations
        """
        try:
            response = self.client.get_rightsizing_recommendation(
                Service='EC2',
                Configuration={
                    'RecommendationTarget': 'CROSS_INSTANCE_FAMILY',
                    'BenefitsConsidered': True
                }
            )
            
            recommendations = []
            for rec in response.get('RightsizingRecommendations', []):
                recommendations.append({
                    'instance_id': rec.get('CurrentInstance', {}).get('ResourceId'),
                    'instance_name': self._get_resource_name(rec.get('CurrentInstance', {}).get('ResourceId')),
                    'current_instance_type': rec.get('CurrentInstance', {}).get('InstanceType'),
                    'recommended_instance_type': rec.get('ModifyRecommendationDetail', {}).get('TargetInstances', [])[0].get('InstanceType') if rec.get('ModifyRecommendationDetail', {}).get('TargetInstances', []) else None,
                    'recommended_action': rec.get('RightsizingType'),
                    'estimated_monthly_savings': float(rec.get('ModifyRecommendationDetail', {}).get('EstimatedMonthlySavings', {}).get('Value', 0)),
                    'savings_percentage': float(rec.get('ModifyRecommendationDetail', {}).get('SavingsPercentage', 0)),
                    'break_even_months': rec.get('ModifyRecommendationDetail', {}).get('EstimatedBreakEvenInMonths', 0)
                })
            
            return recommendations
        except Exception as e:
            self.logger.error(f"Error getting rightsizing recommendations: {str(e)}")
            return []
    
    def _get_resource_name(self, resource_id: str) -> str:
        """
        Get resource name from resource ID using Tags.
        
        Args:
            resource_id: Resource ID to look up
            
        Returns:
            Resource name if found, otherwise resource ID
        """
        if not resource_id:
            return "Unknown"
        
        # For now, just return the ID. In a real implementation, this would look up tags
        # through the appropriate AWS API (e.g., EC2 DescribeTags)
        return resource_id
    
    def _get_total_cost(self, cost_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract total cost from cost data.
        
        Args:
            cost_data: Cost data from Cost Explorer
            
        Returns:
            Dictionary with total cost and currency
        """
        total_amount = 0.0
        currency = "USD"
        
        for period in cost_data.get('ResultsByTime', []):
            for group in period.get('Groups', []):
                metrics = group.get('Metrics', {})
                unblenched_cost = metrics.get('UnblendedCost', {})
                amount = float(unblenched_cost.get('Amount', 0))
                currency = unblenched_cost.get('Unit', currency)
                total_amount += amount
        
        return {
            'amount': total_amount,
            'currency': currency
        }
    
    def _process_daily_costs(self, cost_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process daily cost data into a simpler format.
        
        Args:
            cost_data: Cost data from Cost Explorer
            
        Returns:
            List of daily cost entries
        """
        daily_costs = []
        
        for period in cost_data.get('ResultsByTime', []):
            date = period.get('TimePeriod', {}).get('Start')
            daily_total = 0.0
            
            # Sum services for the day
            for group in period.get('Groups', []):
                service = group.get('Keys', ['Unknown'])[0]
                metrics = group.get('Metrics', {})
                unblenched_cost = metrics.get('UnblendedCost', {})
                amount = float(unblenched_cost.get('Amount', 0))
                daily_total += amount
            
            daily_costs.append({
                'date': date,
                'cost': daily_total
            })
        
        return daily_costs 