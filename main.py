#!/usr/bin/env python3
"""
Cloud Cost Optimization Tools

A comprehensive toolkit for analyzing and optimizing cloud resource usage 
and costs across AWS and Azure cloud providers.
"""

import os
import sys
import click
import yaml
import logging
from rich.console import Console
from rich.logging import RichHandler
from typing import List, Dict, Any, Optional

# Import modules
from common.utils.config import load_config, validate_config
from common.utils.logger import setup_logger
from aws.analyzers.cost_explorer import AWSCostExplorer
from aws.analyzers.resource_analyzer import AWSResourceAnalyzer
from aws.optimizers.ec2_optimizer import EC2Optimizer
from aws.optimizers.s3_optimizer import S3Optimizer
from aws.optimizers.rds_optimizer import RDSOptimizer
from azure.analyzers.cost_analyzer import AzureCostAnalyzer
from azure.analyzers.resource_analyzer import AzureResourceAnalyzer
from azure.optimizers.vm_optimizer import VMOptimizer
from azure.optimizers.storage_optimizer import StorageOptimizer
from common.utils.report_generator import ReportGenerator

console = Console()

@click.group()
@click.option('--config', '-c', default='config/config.yaml', help='Path to configuration file')
@click.option('--debug/--no-debug', default=False, help='Enable debug logging')
@click.pass_context
def cli(ctx: click.Context, config: str, debug: bool):
    """Cloud Cost Optimization Tools - Analyze and optimize cloud costs."""
    # Ensure config directory exists
    if not os.path.exists(config):
        console.print(f"[bold red]Error:[/] Configuration file not found: {config}")
        console.print(f"Please copy config/config.example.yaml to {config} and update it with your settings.")
        sys.exit(1)
    
    # Load configuration
    try:
        ctx.obj = {'config': load_config(config)}
        validate_config(ctx.obj['config'])
    except Exception as e:
        console.print(f"[bold red]Error loading configuration:[/] {str(e)}")
        sys.exit(1)
    
    # Set up logging
    log_level = logging.DEBUG if debug else getattr(logging, ctx.obj['config']['general']['log_level'])
    setup_logger(log_level)
    
    # Create output directory if it doesn't exist
    output_dir = ctx.obj['config']['general']['output_dir']
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

@cli.command()
@click.option('--provider', '-p', type=click.Choice(['aws', 'azure', 'all']), default='all', 
              help='Cloud provider to analyze')
@click.option('--service', '-s', help='Specific service to analyze (e.g., ec2, s3, vm)')
@click.option('--region', '-r', help='Specific region to analyze')
@click.pass_context
def analyze(ctx: click.Context, provider: str, service: Optional[str], region: Optional[str]):
    """Analyze cloud resource usage and costs."""
    config = ctx.obj['config']
    logging.info(f"Starting cost analysis for {provider.upper()} provider")
    
    results = {}
    
    if provider in ['aws', 'all'] and config['aws']['enabled']:
        console.print("[bold blue]Analyzing AWS resources and costs...[/]")
        aws_cost_explorer = AWSCostExplorer(config)
        aws_resource_analyzer = AWSResourceAnalyzer(config)
        
        results['aws'] = {
            'costs': aws_cost_explorer.analyze_costs(service, region),
            'resources': aws_resource_analyzer.analyze_resources(service, region)
        }
        
    if provider in ['azure', 'all'] and config['azure']['enabled']:
        console.print("[bold blue]Analyzing Azure resources and costs...[/]")
        azure_cost_analyzer = AzureCostAnalyzer(config)
        azure_resource_analyzer = AzureResourceAnalyzer(config)
        
        results['azure'] = {
            'costs': azure_cost_analyzer.analyze_costs(service, region),
            'resources': azure_resource_analyzer.analyze_resources(service, region)
        }
    
    # Save results to file
    timestamp = os.popen('date +%Y%m%d_%H%M%S').read().strip()
    output_file = f"{config['general']['output_dir']}/analysis_{provider}_{timestamp}.json"
    
    with open(output_file, 'w') as f:
        yaml.dump(results, f, default_flow_style=False)
    
    console.print(f"[bold green]Analysis complete![/] Results saved to {output_file}")
    return results

@cli.command()
@click.option('--provider', '-p', type=click.Choice(['aws', 'azure', 'all']), default='all', 
              help='Cloud provider to optimize')
@click.option('--service', '-s', help='Specific service to optimize (e.g., ec2, s3, vm)')
@click.option('--region', '-r', help='Specific region to optimize')
@click.option('--analysis-file', '-f', help='Use previously generated analysis file')
@click.pass_context
def recommend(ctx: click.Context, provider: str, service: Optional[str], 
              region: Optional[str], analysis_file: Optional[str]):
    """Generate cost optimization recommendations."""
    config = ctx.obj['config']
    logging.info(f"Generating optimization recommendations for {provider.upper()} provider")
    
    # Load analysis data
    analysis_data = {}
    if analysis_file:
        if not os.path.exists(analysis_file):
            console.print(f"[bold red]Error:[/] Analysis file not found: {analysis_file}")
            sys.exit(1)
        with open(analysis_file, 'r') as f:
            analysis_data = yaml.safe_load(f)
    else:
        # Run analysis if no file provided
        analysis_data = ctx.invoke(analyze, provider=provider, service=service, region=region)
    
    recommendations = {}
    
    if provider in ['aws', 'all'] and config['aws']['enabled']:
        console.print("[bold blue]Generating AWS optimization recommendations...[/]")
        ec2_optimizer = EC2Optimizer(config)
        s3_optimizer = S3Optimizer(config)
        rds_optimizer = RDSOptimizer(config)
        
        aws_recommendations = {}
        if not service or service == 'ec2':
            aws_recommendations['ec2'] = ec2_optimizer.generate_recommendations(analysis_data.get('aws', {}))
        if not service or service == 's3':
            aws_recommendations['s3'] = s3_optimizer.generate_recommendations(analysis_data.get('aws', {}))
        if not service or service == 'rds':
            aws_recommendations['rds'] = rds_optimizer.generate_recommendations(analysis_data.get('aws', {}))
        
        recommendations['aws'] = aws_recommendations
        
    if provider in ['azure', 'all'] and config['azure']['enabled']:
        console.print("[bold blue]Generating Azure optimization recommendations...[/]")
        vm_optimizer = VMOptimizer(config)
        storage_optimizer = StorageOptimizer(config)
        
        azure_recommendations = {}
        if not service or service == 'vm':
            azure_recommendations['vm'] = vm_optimizer.generate_recommendations(analysis_data.get('azure', {}))
        if not service or service == 'storage':
            azure_recommendations['storage'] = storage_optimizer.generate_recommendations(analysis_data.get('azure', {}))
        
        recommendations['azure'] = azure_recommendations
    
    # Save recommendations to file
    timestamp = os.popen('date +%Y%m%d_%H%M%S').read().strip()
    output_file = f"{config['general']['output_dir']}/recommendations_{provider}_{timestamp}.json"
    
    with open(output_file, 'w') as f:
        yaml.dump(recommendations, f, default_flow_style=False)
    
    console.print(f"[bold green]Recommendations generated![/] Results saved to {output_file}")
    return recommendations

@cli.command()
@click.option('--recommendations-file', '-f', help='Use previously generated recommendations file')
@click.option('--format', type=click.Choice(['html', 'csv', 'json']), default=None, 
              help='Report format (defaults to config setting)')
@click.option('--output-file', '-o', help='Output file path')
@click.pass_context
def report(ctx: click.Context, recommendations_file: Optional[str], 
           format: Optional[str], output_file: Optional[str]):
    """Generate cost optimization report."""
    config = ctx.obj['config']
    logging.info("Generating cost optimization report")
    
    # Get report format from config if not specified
    if not format:
        format = config['reporting']['format']
    
    # Use recommendations file or generate new recommendations
    recommendations = {}
    if recommendations_file:
        if not os.path.exists(recommendations_file):
            console.print(f"[bold red]Error:[/] Recommendations file not found: {recommendations_file}")
            sys.exit(1)
        with open(recommendations_file, 'r') as f:
            recommendations = yaml.safe_load(f)
    else:
        # Run recommend if no file provided
        recommendations = ctx.invoke(recommend, provider='all', service=None, region=None, analysis_file=None)
    
    # Generate report
    console.print("[bold blue]Generating cost optimization report...[/]")
    report_generator = ReportGenerator(config)
    
    if not output_file:
        timestamp = os.popen('date +%Y%m%d_%H%M%S').read().strip()
        output_file = f"{config['general']['output_dir']}/report_{timestamp}.{format}"
    
    report_generator.generate_report(recommendations, format, output_file)
    
    console.print(f"[bold green]Report generated![/] Saved to {output_file}")
    
    # Send email if enabled
    if config['reporting']['email']['enabled']:
        report_generator.send_email(output_file)
        console.print("[bold green]Report sent via email.[/]")

if __name__ == "__main__":
    cli(obj={}) 