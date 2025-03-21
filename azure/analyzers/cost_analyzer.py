"""
Azure Cost Analyzer module for analyzing Azure cost data.
"""

import logging
import datetime
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import (
    QueryDefinition, 
    QueryDataset, 
    QueryAggregation,
    QueryGrouping,
    QueryTimePeriod,
    TimeframeType
)
from azure.core.exceptions import HttpResponseError

class AzureCostAnalyzer:
    """
    Analyzes Azure cost data using Azure Cost Management API.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Azure Cost Analyzer.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.logger = logging.getLogger("cloud-cost-optimizer")
        
        # Initialize the Cost Management client
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Initialize the Azure Cost Management client with appropriate credentials."""
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
            
            # Initialize Cost Management client
            self.client = CostManagementClient(credential)
            
            self.logger.info("Azure Cost Management client initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Azure Cost Management client: {str(e)}")
            self.client = None
    
    def analyze_costs(self, service: Optional[str] = None, region: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze Azure costs using Cost Management.
        
        Args:
            service: Specific Azure service to analyze (e.g., compute, storage)
            region: Specific Azure region to analyze
            
        Returns:
            Dictionary containing cost analysis results
        """
        self.logger.info(f"Analyzing Azure costs for service={service}, region={region}")
        
        if not self.client:
            self.logger.error("Azure Cost Management client not initialized")
            return {
                "error": "Azure Cost Management client not initialized"
            }
        
        # Get configuration
        azure_config = self.config['azure']
        lookback_days = azure_config['analysis'].get('lookback_days', 30)
        subscription_ids = azure_config.get('subscription_ids', [])
        
        if not subscription_ids:
            self.logger.error("No Azure subscription IDs specified in configuration")
            return {
                "error": "No Azure subscription IDs specified in configuration"
            }
        
        # Set time period
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=lookback_days)
        
        all_costs = {}
        cost_by_service = {}
        cost_by_region = {}
        daily_costs = []
        total_cost = 0
        
        # Analyze each subscription
        for subscription_id in subscription_ids:
            try:
                # Get cost by subscription
                subscription_costs = self._get_subscription_costs(
                    subscription_id, start_date, end_date
                )
                
                if subscription_costs:
                    all_costs[subscription_id] = subscription_costs
                    total_cost += subscription_costs.get('total', 0)
                
                # Get cost by service
                service_costs = self._get_costs_by_dimension(
                    subscription_id, start_date, end_date, 'ServiceName'
                )
                
                for svc, cost in service_costs.items():
                    if service and service.lower() != svc.lower():
                        continue
                    
                    cost_by_service[svc] = cost_by_service.get(svc, 0) + cost
                
                # Get cost by region
                region_costs = self._get_costs_by_dimension(
                    subscription_id, start_date, end_date, 'ResourceLocation'
                )
                
                for loc, cost in region_costs.items():
                    if region and region.lower() != loc.lower():
                        continue
                    
                    cost_by_region[loc] = cost_by_region.get(loc, 0) + cost
                
                # Get daily costs
                daily = self._get_daily_costs(subscription_id, start_date, end_date)
                for date, cost in daily.items():
                    found = False
                    for entry in daily_costs:
                        if entry['date'] == date:
                            entry['cost'] += cost
                            found = True
                            break
                    
                    if not found:
                        daily_costs.append({
                            'date': date,
                            'cost': cost
                        })
            
            except Exception as e:
                self.logger.error(f"Error analyzing costs for subscription {subscription_id}: {str(e)}")
        
        # Sort daily costs by date
        daily_costs.sort(key=lambda x: x['date'])
        
        # Get advisor recommendations (cost management recommendations)
        recommendations = self._get_advisor_recommendations(subscription_ids)
        
        # Compile results
        results = {
            'time_period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'total_cost': {
                'amount': total_cost,
                'currency': 'USD'  # Default currency
            },
            'costs_by_subscription': all_costs,
            'cost_by_service': cost_by_service,
            'cost_by_region': cost_by_region,
            'daily_costs': daily_costs,
            'savings_recommendations': recommendations
        }
        
        return results
    
    def _get_subscription_costs(self, subscription_id: str, 
                                start_date: datetime.date, 
                                end_date: datetime.date) -> Dict[str, Any]:
        """
        Get costs for a specific subscription.
        
        Args:
            subscription_id: Azure subscription ID
            start_date: Start date for cost data
            end_date: End date for cost data
            
        Returns:
            Dictionary with subscription cost data
        """
        try:
            # Create query definition
            query = QueryDefinition(
                type="ActualCost",
                timeframe="Custom",
                time_period=QueryTimePeriod(
                    from_property=start_date.strftime("%Y-%m-%dT00:00:00Z"),
                    to=end_date.strftime("%Y-%m-%dT23:59:59Z")
                ),
                dataset=QueryDataset(
                    granularity="None",
                    aggregation={
                        "totalCost": QueryAggregation(name="PreTaxCost", function="Sum")
                    }
                )
            )
            
            # Get subscription scope
            scope = f"/subscriptions/{subscription_id}"
            
            # Execute query
            response = self.client.query.usage(scope=scope, parameters=query)
            
            # Process response
            total_cost = 0
            currency = "USD"
            
            if response.rows:
                total_cost = float(response.rows[0][0])
                currency = response.columns[0].get('unit', 'USD')
            
            return {
                "subscription_id": subscription_id,
                "total": total_cost,
                "currency": currency
            }
        except Exception as e:
            self.logger.error(f"Error getting costs for subscription {subscription_id}: {str(e)}")
            return {}
    
    def _get_costs_by_dimension(self, subscription_id: str, 
                               start_date: datetime.date, 
                               end_date: datetime.date,
                               dimension: str) -> Dict[str, float]:
        """
        Get costs grouped by a specific dimension (e.g., ServiceName, ResourceLocation).
        
        Args:
            subscription_id: Azure subscription ID
            start_date: Start date for cost data
            end_date: End date for cost data
            dimension: Dimension to group by
            
        Returns:
            Dictionary mapping dimension values to costs
        """
        try:
            # Create query definition
            query = QueryDefinition(
                type="ActualCost",
                timeframe="Custom",
                time_period=QueryTimePeriod(
                    from_property=start_date.strftime("%Y-%m-%dT00:00:00Z"),
                    to=end_date.strftime("%Y-%m-%dT23:59:59Z")
                ),
                dataset=QueryDataset(
                    granularity="None",
                    aggregation={
                        "totalCost": QueryAggregation(name="PreTaxCost", function="Sum")
                    },
                    grouping=[
                        QueryGrouping(
                            type="Dimension",
                            name=dimension
                        )
                    ]
                )
            )
            
            # Get subscription scope
            scope = f"/subscriptions/{subscription_id}"
            
            # Execute query
            response = self.client.query.usage(scope=scope, parameters=query)
            
            # Process response
            results = {}
            
            for row in response.rows:
                # First column is the dimension value, second is the cost
                dimension_value = row[0] if row[0] else "Unknown"
                cost = float(row[1]) if len(row) > 1 else 0
                
                results[dimension_value] = cost
            
            return results
        except Exception as e:
            self.logger.error(f"Error getting costs by {dimension} for subscription {subscription_id}: {str(e)}")
            return {}
    
    def _get_daily_costs(self, subscription_id: str, 
                         start_date: datetime.date, 
                         end_date: datetime.date) -> Dict[str, float]:
        """
        Get daily costs for a subscription.
        
        Args:
            subscription_id: Azure subscription ID
            start_date: Start date for cost data
            end_date: End date for cost data
            
        Returns:
            Dictionary mapping dates to costs
        """
        try:
            # Create query definition
            query = QueryDefinition(
                type="ActualCost",
                timeframe="Custom",
                time_period=QueryTimePeriod(
                    from_property=start_date.strftime("%Y-%m-%dT00:00:00Z"),
                    to=end_date.strftime("%Y-%m-%dT23:59:59Z")
                ),
                dataset=QueryDataset(
                    granularity="Daily",
                    aggregation={
                        "totalCost": QueryAggregation(name="PreTaxCost", function="Sum")
                    }
                )
            )
            
            # Get subscription scope
            scope = f"/subscriptions/{subscription_id}"
            
            # Execute query
            response = self.client.query.usage(scope=scope, parameters=query)
            
            # Process response
            results = {}
            
            for row in response.rows:
                # First column is the date, second is the cost
                date_str = row[0]
                cost = float(row[1]) if len(row) > 1 else 0
                
                # Convert date string to YYYY-MM-DD format
                date_parts = date_str.split('T')[0].split('-')
                date_formatted = f"{date_parts[0]}-{date_parts[1]}-{date_parts[2]}"
                
                results[date_formatted] = cost
            
            return results
        except Exception as e:
            self.logger.error(f"Error getting daily costs for subscription {subscription_id}: {str(e)}")
            return {}
    
    def _get_advisor_recommendations(self, subscription_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get Azure Advisor cost recommendations.
        
        Args:
            subscription_ids: List of Azure subscription IDs
            
        Returns:
            List of cost optimization recommendations
        """
        # This would normally use the Azure Advisor API to get cost recommendations.
        # Since we're building a mock-up and Advisor client requires special permissions,
        # we'll return some sample recommendations.
        
        self.logger.info("Getting Azure Advisor cost recommendations (simulated)")
        
        # Sample recommendations for demonstration purposes
        sample_recommendations = [
            {
                "recommendation_id": "cost-rightsize-vms",
                "subscription_id": subscription_ids[0] if subscription_ids else "unknown",
                "resource_id": f"/subscriptions/{subscription_ids[0]}/resourceGroups/sample-rg/providers/Microsoft.Compute/virtualMachines/sample-vm" if subscription_ids else "",
                "recommendation_type": "Rightsize or shutdown underutilized virtual machines",
                "resource_name": "sample-vm",
                "resource_type": "Virtual Machine",
                "estimated_monthly_savings": 45.30,
                "confidence": "High",
                "details": "Your virtual machine has been running at less than 5% CPU utilization for the last 30 days. Consider downsizing or shutting down this VM."
            },
            {
                "recommendation_id": "cost-unused-disks",
                "subscription_id": subscription_ids[0] if subscription_ids else "unknown",
                "resource_id": f"/subscriptions/{subscription_ids[0]}/resourceGroups/sample-rg/providers/Microsoft.Compute/disks/unused-disk" if subscription_ids else "",
                "recommendation_type": "Delete or deallocate unused managed disks",
                "resource_name": "unused-disk",
                "resource_type": "Managed Disk",
                "estimated_monthly_savings": 12.80,
                "confidence": "High",
                "details": "You have unattached managed disks that are incurring costs. Consider deleting these disks if the data is no longer needed."
            },
            {
                "recommendation_id": "cost-reserved-instances",
                "subscription_id": subscription_ids[0] if subscription_ids else "unknown",
                "resource_id": "",
                "recommendation_type": "Purchase reserved instances",
                "resource_name": "Multiple VMs",
                "resource_type": "Virtual Machine",
                "estimated_monthly_savings": 320.45,
                "confidence": "Medium",
                "details": "You have several virtual machines running continuously. Consider purchasing reserved instances for 12-36 months for savings of up to a 60%."
            }
        ]
        
        return sample_recommendations 