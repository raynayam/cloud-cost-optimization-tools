#!/usr/bin/env python3
"""
Quick start script for Cloud Cost Optimization Tools.

This script demonstrates how to use the Cloud Cost Optimization Tools
to analyze and optimize cloud costs.
"""

import os
import sys
import logging
import yaml
from rich.console import Console

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from common.utils.logger import setup_logger
from common.utils.config import load_config, validate_config
from aws.analyzers.cost_explorer import AWSCostExplorer
from aws.analyzers.resource_analyzer import AWSResourceAnalyzer
from aws.optimizers.ec2_optimizer import EC2Optimizer
from aws.optimizers.s3_optimizer import S3Optimizer
from azure.analyzers.cost_analyzer import AzureCostAnalyzer
from azure.optimizers.vm_optimizer import VMOptimizer
from common.utils.report_generator import ReportGenerator

# Set up console and logger
console = Console()
logger = setup_logger()

def main():
    """Run a sample analysis and optimization workflow."""
    console.print("[bold blue]Cloud Cost Optimization Tools - Quick Start[/]")
    
    # Load configuration
    try:
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
        if not os.path.exists(config_path):
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.example.yaml')
            console.print(f"[yellow]Warning:[/] Using example configuration. Copy config.example.yaml to config.yaml and update with your settings for production use.")
        
        config = load_config(config_path)
        validate_config(config)
    except Exception as e:
        console.print(f"[bold red]Error loading configuration:[/] {str(e)}")
        return
    
    # Create output directory if it doesn't exist
    output_dir = config['general']['output_dir']
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Step 1: Analyze cloud costs
    console.print("\n[bold]Step 1: Analyzing cloud costs...[/]")
    analysis_results = analyze_costs(config)
    
    # Step 2: Generate optimization recommendations
    console.print("\n[bold]Step 2: Generating optimization recommendations...[/]")
    recommendations = generate_recommendations(config, analysis_results)
    
    # Step 3: Generate report
    console.print("\n[bold]Step 3: Generating optimization report...[/]")
    report_file = generate_report(config, recommendations)
    
    console.print(f"\n[bold green]Quick start completed![/] Report saved to: {report_file}")
    console.print("\nNext steps:")
    console.print("1. Review the report for cost optimization opportunities")
    console.print("2. Implement recommended changes in your cloud environments")
    console.print("3. Run the tool periodically to identify new optimization opportunities")

def analyze_costs(config):
    """Analyze cloud costs for AWS and Azure."""
    results = {}
    
    # Analyze AWS costs if enabled
    if config['aws'].get('enabled', False):
        console.print("[blue]Analyzing AWS costs...[/]")
        try:
            aws_cost_explorer = AWSCostExplorer(config)
            aws_resource_analyzer = AWSResourceAnalyzer(config)
            
            results['aws'] = {
                'costs': aws_cost_explorer.analyze_costs(),
                'resources': aws_resource_analyzer.analyze_resources() if 'resource_analyzer' in sys.modules else {}
            }
            console.print("[green]AWS cost analysis completed.[/]")
        except Exception as e:
            console.print(f"[red]Error analyzing AWS costs: {str(e)}[/]")
    
    # Analyze Azure costs if enabled
    if config['azure'].get('enabled', False):
        console.print("[blue]Analyzing Azure costs...[/]")
        try:
            azure_cost_analyzer = AzureCostAnalyzer(config)
            
            results['azure'] = {
                'costs': azure_cost_analyzer.analyze_costs()
            }
            console.print("[green]Azure cost analysis completed.[/]")
        except Exception as e:
            console.print(f"[red]Error analyzing Azure costs: {str(e)}[/]")
    
    # Save analysis results
    timestamp = os.popen('date +%Y%m%d_%H%M%S').read().strip()
    output_file = f"{config['general']['output_dir']}/analysis_{timestamp}.yaml"
    
    with open(output_file, 'w') as f:
        yaml.dump(results, f, default_flow_style=False)
    
    console.print(f"Analysis results saved to: {output_file}")
    return results

def generate_recommendations(config, analysis_data):
    """Generate cost optimization recommendations."""
    recommendations = {}
    
    # Generate AWS recommendations if enabled
    if config['aws'].get('enabled', False):
        console.print("[blue]Generating AWS optimization recommendations...[/]")
        try:
            ec2_optimizer = EC2Optimizer(config)
            s3_optimizer = S3Optimizer(config)
            
            aws_recommendations = {
                'ec2': ec2_optimizer.generate_recommendations(analysis_data.get('aws', {})),
                's3': s3_optimizer.generate_recommendations(analysis_data.get('aws', {}))
            }
            recommendations['aws'] = aws_recommendations
            console.print("[green]AWS recommendations generated.[/]")
        except Exception as e:
            console.print(f"[red]Error generating AWS recommendations: {str(e)}[/]")
    
    # Generate Azure recommendations if enabled
    if config['azure'].get('enabled', False):
        console.print("[blue]Generating Azure optimization recommendations...[/]")
        try:
            vm_optimizer = VMOptimizer(config)
            
            azure_recommendations = {
                'vm': vm_optimizer.generate_recommendations(analysis_data.get('azure', {}))
            }
            recommendations['azure'] = azure_recommendations
            console.print("[green]Azure recommendations generated.[/]")
        except Exception as e:
            console.print(f"[red]Error generating Azure recommendations: {str(e)}[/]")
    
    # Save recommendations
    timestamp = os.popen('date +%Y%m%d_%H%M%S').read().strip()
    output_file = f"{config['general']['output_dir']}/recommendations_{timestamp}.yaml"
    
    with open(output_file, 'w') as f:
        yaml.dump(recommendations, f, default_flow_style=False)
    
    console.print(f"Recommendations saved to: {output_file}")
    return recommendations

def generate_report(config, recommendations):
    """Generate a cost optimization report."""
    console.print("[blue]Generating cost optimization report...[/]")
    
    try:
        report_generator = ReportGenerator(config)
        
        # Generate HTML report
        timestamp = os.popen('date +%Y%m%d_%H%M%S').read().strip()
        output_file = f"{config['general']['output_dir']}/report_{timestamp}.html"
        
        report_generator.generate_report(recommendations, 'html', output_file)
        console.print("[green]Report generated successfully.[/]")
        
        return output_file
    except Exception as e:
        console.print(f"[red]Error generating report: {str(e)}[/]")
        return None

if __name__ == "__main__":
    main() 