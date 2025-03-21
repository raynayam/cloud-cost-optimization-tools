"""
Report generation utilities for Cloud Cost Optimization Tools.
"""

import os
import json
import csv
import logging
import smtplib
import matplotlib.pyplot as plt
import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Dict, Any, List, Optional
from datetime import datetime

class ReportGenerator:
    """
    Generates optimization reports in various formats.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the report generator.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.logger = logging.getLogger("cloud-cost-optimizer")
    
    def generate_report(self, recommendations: Dict[str, Any], 
                        format: str = "html", output_file: str = None) -> str:
        """
        Generate a report based on recommendations.
        
        Args:
            recommendations: Cost optimization recommendations
            format: Report format (html, csv, json)
            output_file: Path to save the report
            
        Returns:
            Path to the generated report
        """
        if format not in ["html", "csv", "json"]:
            raise ValueError(f"Unsupported report format: {format}")
        
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"{self.config['general']['output_dir']}/report_{timestamp}.{format}"
        
        self.logger.info(f"Generating {format.upper()} report: {output_file}")
        
        # Process recommendations to a structured format
        processed_data = self._process_recommendations(recommendations)
        
        # Generate the appropriate format
        if format == "html":
            self._generate_html_report(processed_data, output_file)
        elif format == "csv":
            self._generate_csv_report(processed_data, output_file)
        elif format == "json":
            self._generate_json_report(processed_data, output_file)
        
        return output_file
    
    def _process_recommendations(self, recommendations: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process recommendations into a structured format for reporting.
        
        Args:
            recommendations: Raw recommendations data
            
        Returns:
            List of structured recommendation items
        """
        processed_items = []
        
        # Process AWS recommendations
        if 'aws' in recommendations:
            aws_recs = recommendations['aws']
            
            # Process EC2 recommendations
            if 'ec2' in aws_recs:
                for item in aws_recs['ec2']:
                    processed_items.append({
                        'cloud_provider': 'AWS',
                        'service': 'EC2',
                        'resource_id': item.get('instance_id', 'N/A'),
                        'resource_name': item.get('instance_name', 'N/A'),
                        'region': item.get('region', 'N/A'),
                        'recommendation_type': item.get('recommendation_type', 'N/A'),
                        'current_state': item.get('current_state', {}),
                        'recommended_state': item.get('recommended_state', {}),
                        'estimated_savings': item.get('estimated_monthly_savings', 0),
                        'confidence': item.get('confidence', 'Medium'),
                        'details': item.get('details', ''),
                    })
            
            # Process S3 recommendations
            if 's3' in aws_recs:
                for item in aws_recs['s3']:
                    processed_items.append({
                        'cloud_provider': 'AWS',
                        'service': 'S3',
                        'resource_id': item.get('bucket_name', 'N/A'),
                        'resource_name': item.get('bucket_name', 'N/A'),
                        'region': item.get('region', 'N/A'),
                        'recommendation_type': item.get('recommendation_type', 'N/A'),
                        'current_state': item.get('current_state', {}),
                        'recommended_state': item.get('recommended_state', {}),
                        'estimated_savings': item.get('estimated_monthly_savings', 0),
                        'confidence': item.get('confidence', 'Medium'),
                        'details': item.get('details', ''),
                    })
            
            # Process RDS recommendations
            if 'rds' in aws_recs:
                for item in aws_recs['rds']:
                    processed_items.append({
                        'cloud_provider': 'AWS',
                        'service': 'RDS',
                        'resource_id': item.get('db_instance_id', 'N/A'),
                        'resource_name': item.get('db_instance_name', 'N/A'),
                        'region': item.get('region', 'N/A'),
                        'recommendation_type': item.get('recommendation_type', 'N/A'),
                        'current_state': item.get('current_state', {}),
                        'recommended_state': item.get('recommended_state', {}),
                        'estimated_savings': item.get('estimated_monthly_savings', 0),
                        'confidence': item.get('confidence', 'Medium'),
                        'details': item.get('details', ''),
                    })
        
        # Process Azure recommendations
        if 'azure' in recommendations:
            azure_recs = recommendations['azure']
            
            # Process VM recommendations
            if 'vm' in azure_recs:
                for item in azure_recs['vm']:
                    processed_items.append({
                        'cloud_provider': 'Azure',
                        'service': 'Virtual Machine',
                        'resource_id': item.get('vm_id', 'N/A'),
                        'resource_name': item.get('vm_name', 'N/A'),
                        'region': item.get('region', 'N/A'),
                        'recommendation_type': item.get('recommendation_type', 'N/A'),
                        'current_state': item.get('current_state', {}),
                        'recommended_state': item.get('recommended_state', {}),
                        'estimated_savings': item.get('estimated_monthly_savings', 0),
                        'confidence': item.get('confidence', 'Medium'),
                        'details': item.get('details', ''),
                    })
            
            # Process Storage recommendations
            if 'storage' in azure_recs:
                for item in azure_recs['storage']:
                    processed_items.append({
                        'cloud_provider': 'Azure',
                        'service': 'Storage',
                        'resource_id': item.get('storage_id', 'N/A'),
                        'resource_name': item.get('storage_name', 'N/A'),
                        'region': item.get('region', 'N/A'),
                        'recommendation_type': item.get('recommendation_type', 'N/A'),
                        'current_state': item.get('current_state', {}),
                        'recommended_state': item.get('recommended_state', {}),
                        'estimated_savings': item.get('estimated_monthly_savings', 0),
                        'confidence': item.get('confidence', 'Medium'),
                        'details': item.get('details', ''),
                    })
        
        # Sort by potential savings
        processed_items.sort(key=lambda x: x.get('estimated_savings', 0), reverse=True)
        
        return processed_items
    
    def _generate_html_report(self, data: List[Dict[str, Any]], output_file: str) -> None:
        """
        Generate an HTML report.
        
        Args:
            data: Processed recommendation data
            output_file: Output file path
        """
        # Calculate total potential savings
        total_savings = sum(item.get('estimated_savings', 0) for item in data)
        
        # Generate charts if enabled
        charts_html = ""
        if self.config['reporting'].get('include_charts', True):
            charts_dir = os.path.dirname(output_file)
            charts_html = self._generate_charts(data, charts_dir)
        
        # Generate recommendations table
        recommendations_html = self._generate_recommendations_table(data)
        
        # Create HTML content
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Cloud Cost Optimization Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                h1, h2, h3 {{ color: #2c3e50; }}
                .summary {{ background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 30px; }}
                .summary h2 {{ margin-top: 0; }}
                .savings {{ color: #27ae60; font-weight: bold; font-size: 24px; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 30px; }}
                th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f2f2f2; }}
                tr:hover {{ background-color: #f5f5f5; }}
                .chart-container {{ margin: 30px 0; }}
                .footer {{ font-size: 12px; color: #7f8c8d; margin-top: 50px; text-align: center; }}
                .service-aws {{ color: #FF9900; }}
                .service-azure {{ color: #0089D6; }}
            </style>
        </head>
        <body>
            <h1>Cloud Cost Optimization Report</h1>
            <div class="summary">
                <h2>Summary</h2>
                <p>Report generated on: <strong>{timestamp}</strong></p>
                <p>Total potential monthly savings: <span class="savings">${total_savings:.2f}</span></p>
                <p>Total recommendations: <strong>{len(data)}</strong></p>
            </div>
            
            {charts_html}
            
            <h2>Recommendations</h2>
            {recommendations_html}
            
            <div class="footer">
                <p>Generated by Cloud Cost Optimization Tools</p>
            </div>
        </body>
        </html>
        """
        
        # Write HTML content to file
        with open(output_file, 'w') as f:
            f.write(html_content)
    
    def _generate_recommendations_table(self, data: List[Dict[str, Any]]) -> str:
        """
        Generate HTML table of recommendations.
        
        Args:
            data: Processed recommendation data
            
        Returns:
            HTML string for the recommendations table
        """
        if not data:
            return "<p>No recommendations available.</p>"
        
        html = """
        <table>
            <thead>
                <tr>
                    <th>Provider</th>
                    <th>Service</th>
                    <th>Resource</th>
                    <th>Region</th>
                    <th>Recommendation</th>
                    <th>Estimated Savings</th>
                    <th>Confidence</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for item in data:
            provider_class = "service-aws" if item['cloud_provider'] == 'AWS' else "service-azure"
            html += f"""
                <tr>
                    <td class="{provider_class}">{item['cloud_provider']}</td>
                    <td>{item['service']}</td>
                    <td>{item['resource_name']}</td>
                    <td>{item['region']}</td>
                    <td>{item['recommendation_type']}</td>
                    <td>${item.get('estimated_savings', 0):.2f}/month</td>
                    <td>{item.get('confidence', 'Medium')}</td>
                </tr>
            """
        
        html += """
            </tbody>
        </table>
        """
        
        return html
    
    def _generate_charts(self, data: List[Dict[str, Any]], output_dir: str) -> str:
        """
        Generate charts for the report.
        
        Args:
            data: Processed recommendation data
            output_dir: Directory to save charts
            
        Returns:
            HTML string for the charts section
        """
        if not data:
            return ""
        
        # Ensure the output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Convert data to DataFrame for easier manipulation
        df = pd.DataFrame(data)
        
        # Generate chart paths
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        savings_by_provider_path = f"savings_by_provider_{timestamp}.png"
        savings_by_service_path = f"savings_by_service_{timestamp}.png"
        
        # 1. Savings by Cloud Provider
        plt.figure(figsize=(10, 6))
        provider_savings = df.groupby('cloud_provider')['estimated_savings'].sum()
        provider_savings.plot(kind='bar', color=['#FF9900', '#0089D6'])
        plt.title('Potential Monthly Savings by Cloud Provider')
        plt.xlabel('Cloud Provider')
        plt.ylabel('Potential Savings ($)')
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, savings_by_provider_path))
        plt.close()
        
        # 2. Savings by Service
        plt.figure(figsize=(12, 6))
        service_savings = df.groupby(['cloud_provider', 'service'])['estimated_savings'].sum().unstack()
        service_savings.plot(kind='bar', stacked=True)
        plt.title('Potential Monthly Savings by Service')
        plt.xlabel('Cloud Provider')
        plt.ylabel('Potential Savings ($)')
        plt.legend(title='Service')
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, savings_by_service_path))
        plt.close()
        
        # Generate HTML for charts
        charts_html = f"""
        <h2>Cost Optimization Charts</h2>
        <div class="chart-container">
            <h3>Potential Savings by Cloud Provider</h3>
            <img src="{savings_by_provider_path}" alt="Savings by Provider" width="80%">
        </div>
        <div class="chart-container">
            <h3>Potential Savings by Service</h3>
            <img src="{savings_by_service_path}" alt="Savings by Service" width="80%">
        </div>
        """
        
        return charts_html
    
    def _generate_csv_report(self, data: List[Dict[str, Any]], output_file: str) -> None:
        """
        Generate a CSV report.
        
        Args:
            data: Processed recommendation data
            output_file: Output file path
        """
        if not data:
            return
        
        # Define CSV columns
        fieldnames = [
            'cloud_provider', 'service', 'resource_id', 'resource_name', 'region',
            'recommendation_type', 'estimated_savings', 'confidence', 'details'
        ]
        
        # Write CSV file
        with open(output_file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for item in data:
                # Create a new dict with only the fields we want
                row = {field: item.get(field, '') for field in fieldnames}
                # Convert complex objects to strings
                if 'details' in row and isinstance(row['details'], dict):
                    row['details'] = json.dumps(row['details'])
                writer.writerow(row)
    
    def _generate_json_report(self, data: List[Dict[str, Any]], output_file: str) -> None:
        """
        Generate a JSON report.
        
        Args:
            data: Processed recommendation data
            output_file: Output file path
        """
        # Determine total savings
        total_savings = sum(item.get('estimated_savings', 0) for item in data)
        
        # Create report structure
        report = {
            'generated_at': datetime.now().isoformat(),
            'total_potential_savings': total_savings,
            'recommendation_count': len(data),
            'recommendations': data
        }
        
        # Write JSON file
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
    
    def send_email(self, report_file: str) -> bool:
        """
        Send the report via email.
        
        Args:
            report_file: Path to the report file
            
        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.config['reporting']['email']['enabled']:
            return False
        
        email_config = self.config['reporting']['email']
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = email_config['sender']
            msg['To'] = ', '.join(email_config['recipients'])
            msg['Subject'] = "Cloud Cost Optimization Report"
            
            # Add body
            body = """
            Hello,
            
            Attached is the latest Cloud Cost Optimization Report.
            
            This report includes potential cost savings recommendations for your cloud resources.
            
            Regards,
            Cloud Cost Optimization Tools
            """
            msg.attach(MIMEText(body, 'plain'))
            
            # Attach the report
            with open(report_file, 'rb') as f:
                attachment = MIMEApplication(f.read(), Name=os.path.basename(report_file))
            
            attachment['Content-Disposition'] = f'attachment; filename="{os.path.basename(report_file)}"'
            msg.attach(attachment)
            
            # Send email
            server = smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'])
            server.starttls()
            server.login(email_config['smtp_username'], email_config['smtp_password'])
            server.send_message(msg)
            server.quit()
            
            self.logger.info(f"Email sent to {', '.join(email_config['recipients'])}")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to send email: {str(e)}")
            return False 