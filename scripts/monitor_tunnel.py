#!/usr/bin/env python3
"""
Tunnel Monitoring and Optimization Script

This script monitors the WireGuard tunnel performance, logs metrics,
and optimizes parameters based on the mathematical model.

Features:
- Measure throughput, latency, and packet loss using speedtest-cli and ping
- Log metrics to CSV file for analysis
- Adjust MTU or buffer sizes based on the mathematical model
- Alert the user if tunnel uptime drops below 99.9%
- Analyze metrics to suggest ISP upgrades
"""

import os
import sys
import time
import logging
import json
import csv
import subprocess
import threading
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Add local imports
sys.path.append('.')
from models.network_optimization import NetworkOptimizer, NetworkParameters, NetworkMetrics
from models.reinforcement_learning import RoutingAgent, state_from_metrics

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

class TunnelMonitor:
    """
    Monitors WireGuard tunnel performance and optimizes parameters.
    """
    def __init__(self, config_dir='./config', logs_dir='./logs', wireguard_mgr=None):
        """
        Initialize the tunnel monitor.
        
        Args:
            config_dir: Directory containing configuration files
            logs_dir: Directory for log files
            wireguard_mgr: WireGuard manager instance (optional)
        """
        self.config_dir = Path(config_dir)
        self.logs_dir = Path(logs_dir)
        self.wireguard_mgr = wireguard_mgr
        
        # Create directories if they don't exist
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # Metrics log file
        self.metrics_file = self.logs_dir / 'tunnel_metrics.csv'
        
        # Alert settings
        self.alert_email = os.environ.get('ALERT_EMAIL')
        self.smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.environ.get('SMTP_PORT', '587'))
        self.smtp_username = os.environ.get('SMTP_USERNAME')
        self.smtp_password = os.environ.get('SMTP_PASSWORD')
        
        # Initialize metrics history
        self.metrics_history = []
        self._load_metrics_history()
        
        # Create network optimizer
        self.network_optimizer = NetworkOptimizer()
        
        # Load optimization agent if available
        try:
            self.routing_agent = RoutingAgent(model_dir='./models/saved_rl')
            logger.info("Loaded routing optimization agent")
        except Exception as e:
            logger.warning(f"Could not load routing optimization agent: {e}")
            self.routing_agent = None
            
        # Monitoring thread
        self.monitor_thread = None
        self.monitoring = False
        
        # Last alert time (to avoid spamming)
        self.last_alert_time = None
        
    def _load_metrics_history(self):
        """
        Load metrics history from CSV file.
        """
        if not self.metrics_file.exists():
            # Create the metrics file with headers
            with open(self.metrics_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'tunnel_active', 'download_mbps', 'upload_mbps',
                    'latency_ms', 'packet_loss_percent', 'mtu', 'uptime_seconds'
                ])
            return
            
        try:
            with open(self.metrics_file, 'r', newline='') as f:
                reader = csv.DictReader(f)
                self.metrics_history = list(reader)
                
            logger.info(f"Loaded {len(self.metrics_history)} historical metrics")
            
        except Exception as e:
            logger.error(f"Error loading metrics history: {e}")
            
    def _add_metrics_to_history(self, metrics):
        """
        Add metrics to history and save to CSV file.
        
        Args:
            metrics: Metrics to add
        """
        # Add to in-memory history
        self.metrics_history.append(metrics)
        
        # Append to CSV file
        try:
            file_exists = self.metrics_file.exists()
            
            with open(self.metrics_file, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=metrics.keys())
                
                if not file_exists:
                    writer.writeheader()
                    
                writer.writerow(metrics)
                
        except Exception as e:
            logger.error(f"Error saving metrics to CSV: {e}")
            
    def measure_tunnel_metrics(self):
        """
        Measure current tunnel performance metrics.
        
        Returns:
            dict: Measured metrics
        """
        # Get tunnel status
        tunnel_active = False
        uptime_seconds = 0
        mtu = 1420  # Default MTU
        
        if self.wireguard_mgr:
            # Get status from WireGuard manager
            status = self.wireguard_mgr.get_tunnel_status()
            tunnel_active = status.get('running', False)
            
            # Calculate uptime
            if tunnel_active and status.get('uptime'):
                uptime_str = status.get('uptime', '')
                
                # Parse uptime string (e.g., "2d 5h 30m 10s")
                days = hours = minutes = seconds = 0
                
                if 'd' in uptime_str:
                    days_match = re.search(r'(\d+)d', uptime_str)
                    if days_match:
                        days = int(days_match.group(1))
                        
                if 'h' in uptime_str:
                    hours_match = re.search(r'(\d+)h', uptime_str)
                    if hours_match:
                        hours = int(hours_match.group(1))
                        
                if 'm' in uptime_str:
                    minutes_match = re.search(r'(\d+)m', uptime_str)
                    if minutes_match:
                        minutes = int(minutes_match.group(1))
                        
                if 's' in uptime_str:
                    seconds_match = re.search(r'(\d+)s', uptime_str)
                    if seconds_match:
                        seconds = int(seconds_match.group(1))
                        
                uptime_seconds = days * 86400 + hours * 3600 + minutes * 60 + seconds
                
            # Get current stats
            current_stats = self.wireguard_mgr.get_current_stats()
            
            # Get MTU from config
            config = self.wireguard_mgr.get_config()
            mtu = config.get('mtu', 1420)
            
        else:
            # Check if WireGuard is running via command line
            try:
                result = subprocess.run(['sudo', 'wg', 'show'], capture_output=True, text=True)
                tunnel_active = result.returncode == 0 and 'interface' in result.stdout.lower()
                
                # Try to extract MTU
                if tunnel_active:
                    mtu_result = subprocess.run(['ip', 'link', 'show', 'wg0'], capture_output=True, text=True)
                    if mtu_result.returncode == 0:
                        mtu_match = re.search(r'mtu (\d+)', mtu_result.stdout)
                        if mtu_match:
                            mtu = int(mtu_match.group(1))
                            
            except Exception as e:
                logger.error(f"Error checking WireGuard status: {e}")
                tunnel_active = False
                
            # Use system tools to get current stats
            current_stats = self._measure_system_stats()
            
        # Create metrics dictionary
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'tunnel_active': tunnel_active,
            'download_mbps': current_stats.get('download_speed', 0),
            'upload_mbps': current_stats.get('upload_speed', 0),
            'latency_ms': current_stats.get('latency', 0),
            'packet_loss_percent': current_stats.get('packet_loss', 0),
            'mtu': mtu,
            'uptime_seconds': uptime_seconds
        }
        
        logger.info(f"Measured tunnel metrics: active={tunnel_active}, "
                   f"download={metrics['download_mbps']:.2f}Mbps, "
                   f"upload={metrics['upload_mbps']:.2f}Mbps, "
                   f"latency={metrics['latency_ms']:.2f}ms, "
                   f"loss={metrics['packet_loss_percent']:.2f}%")
        
        return metrics
        
    def _measure_system_stats(self):
        """
        Measure network statistics using system tools.
        
        Returns:
            dict: Network statistics
        """
        stats = {
            'download_speed': 0,
            'upload_speed': 0,
            'latency': 0,
            'packet_loss': 0
        }
        
        # Measure latency and packet loss with ping
        try:
            # Try a few different hosts in case some are unreachable
            hosts = ['8.8.8.8', '1.1.1.1', 'google.com']
            ping_success = False
            
            for host in hosts:
                cmd = ['ping', '-c', '10', host]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    output = result.stdout
                    
                    # Extract packet loss
                    loss_match = re.search(r'(\d+)% packet loss', output)
                    if loss_match:
                        stats['packet_loss'] = float(loss_match.group(1))
                        
                    # Extract average latency
                    latency_match = re.search(r'min/avg/max/.+ = [\d.]+/([\d.]+)/', output)
                    if latency_match:
                        stats['latency'] = float(latency_match.group(1))
                        
                    ping_success = True
                    break
                    
            if not ping_success:
                logger.warning("Could not measure latency and packet loss with ping")
                
        except Exception as e:
            logger.error(f"Error measuring latency and packet loss: {e}")
            
        # Measure throughput with speedtest-cli if available
        try:
            # Check if speedtest-cli is available
            result = subprocess.run(['which', 'speedtest-cli'], capture_output=True, text=True)
            
            if result.returncode == 0:
                # Run speedtest
                cmd = ['speedtest-cli', '--simple']
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0:
                    output = result.stdout
                    
                    # Extract download speed
                    download_match = re.search(r'Download: ([\d.]+) Mbit/s', output)
                    if download_match:
                        stats['download_speed'] = float(download_match.group(1))
                        
                    # Extract upload speed
                    upload_match = re.search(r'Upload: ([\d.]+) Mbit/s', output)
                    if upload_match:
                        stats['upload_speed'] = float(upload_match.group(1))
                        
            else:
                logger.warning("speedtest-cli not available")
                
                # Use defaults or previous metrics if available
                if self.metrics_history:
                    last_metrics = self.metrics_history[-1]
                    stats['download_speed'] = float(last_metrics.get('download_mbps', 1.5))
                    stats['upload_speed'] = float(last_metrics.get('upload_mbps', 0.75))
                else:
                    stats['download_speed'] = 1.5  # Default 1.5 Mbps download
                    stats['upload_speed'] = 0.75  # Default 0.75 Mbps upload
                
        except Exception as e:
            logger.error(f"Error measuring throughput: {e}")
            
            # Use defaults
            stats['download_speed'] = 1.5  # Default 1.5 Mbps download
            stats['upload_speed'] = 0.75  # Default 0.75 Mbps upload
            
        return stats
        
    def optimize_parameters(self, metrics):
        """
        Optimize tunnel parameters based on the measured metrics.
        
        Args:
            metrics: Current tunnel metrics
            
        Returns:
            dict: Optimization recommendations
        """
        if not metrics['tunnel_active']:
            logger.warning("Cannot optimize parameters when tunnel is not active")
            return None
            
        logger.info("Optimizing tunnel parameters...")
        
        # Convert metrics to NetworkParameters
        params = NetworkParameters(
            b_local=metrics['download_mbps'] / 1000.0,  # Convert Mbps to Gbps
            b_ec2=1.0,  # Assume 1 Gbps EC2 egress
            l_propagation=metrics['latency_ms'] * 0.5,  # Approximate propagation latency
            mtu=metrics['mtu'],
            buffer_size=1000,  # Default buffer size
            packet_size=min(metrics['mtu'] - 20, 1400),  # Adjust packet size based on MTU
            congestion_level=metrics['packet_loss_percent'] / 100.0  # Convert percentage to 0-1 range
        )
        
        # Calculate current metrics with the network optimizer
        current_metrics = self.network_optimizer.calculate_metrics(params)
        
        # Determine if parameters need adjustment
        needs_adjustment = (
            metrics['packet_loss_percent'] > 1.0 or  # High packet loss
            metrics['latency_ms'] > 100 or          # High latency
            metrics['download_mbps'] < 1.0          # Low throughput
        )
        
        if needs_adjustment:
            logger.info("Network performance needs improvement, optimizing parameters...")
            
            # Find optimal parameters
            optimal_params, optimal_metrics = self.network_optimizer.optimize_parameters()
            
            # Check if there's a significant improvement
            throughput_improvement = (optimal_metrics.effective_throughput / current_metrics.effective_throughput - 1) * 100
            latency_improvement = (1 - optimal_metrics.total_latency / current_metrics.total_latency) * 100
            
            if throughput_improvement > 5 or latency_improvement > 5:
                logger.info(f"Found better parameters: MTU={optimal_params.mtu}, Buffer={optimal_params.buffer_size}")
                logger.info(f"Expected improvements: Throughput +{throughput_improvement:.1f}%, Latency +{latency_improvement:.1f}%")
                
                # Apply changes if we have access to the WireGuard manager
                if self.wireguard_mgr:
                    # Update configuration
                    config_update = {
                        'mtu': optimal_params.mtu
                    }
                    
                    result = self.wireguard_mgr.update_config(config_update)
                    
                    if result.get('success', False):
                        logger.info("Applied new parameters to WireGuard configuration")
                    else:
                        logger.error(f"Failed to update WireGuard configuration: {result.get('error', 'Unknown error')}")
                else:
                    logger.info("WireGuard manager not available, parameters not applied")
                    
                # Try using the routing agent if available
                if self.routing_agent:
                    state = state_from_metrics(current_metrics)
                    action = self.routing_agent.choose_action(state, explore=False)
                    
                    logger.info(f"Routing agent recommends action: {self.routing_agent.actions[action]['name']}")
                    
                    if self.wireguard_mgr:
                        param_dict = {
                            'mtu': metrics['mtu'],
                            'direct_tunnel': True,
                            'prioritize_aws': False
                        }
                        
                        new_param_dict = self.routing_agent.apply_action(action, param_dict)
                        
                        # Apply action
                        config_update = {
                            'mtu': new_param_dict['mtu'],
                            'direct_tunnel': new_param_dict['direct_tunnel']
                        }
                        
                        result = self.wireguard_mgr.update_config(config_update)
                        
                        if result.get('success', False):
                            logger.info("Applied RL agent recommendations to WireGuard configuration")
                        else:
                            logger.error(f"Failed to update WireGuard configuration: {result.get('error', 'Unknown error')}")
                
                return {
                    'needed_adjustment': True,
                    'mtu': optimal_params.mtu,
                    'buffer_size': optimal_params.buffer_size,
                    'throughput_improvement': throughput_improvement,
                    'latency_improvement': latency_improvement
                }
            else:
                logger.info("Current parameters are already optimal")
                
        else:
            logger.info("Network performance is good, no parameter adjustment needed")
            
        return {
            'needed_adjustment': False,
            'mtu': metrics['mtu'],
            'buffer_size': 1000,
            'throughput_improvement': 0,
            'latency_improvement': 0
        }
        
    def check_tunnel_health(self, metrics):
        """
        Check the health of the tunnel and send alerts if needed.
        
        Args:
            metrics: Current tunnel metrics
            
        Returns:
            dict: Health check results
        """
        # Get recent history (last 24 hours)
        recent_history = []
        
        for m in self.metrics_history:
            try:
                timestamp = datetime.fromisoformat(m['timestamp'])
                if (datetime.now() - timestamp) < timedelta(hours=24):
                    recent_history.append(m)
            except (ValueError, KeyError):
                continue
                
        if not recent_history:
            recent_history = [metrics]
            
        # Calculate uptime percentage
        active_count = sum(1 for m in recent_history if m.get('tunnel_active') in (True, 'True'))
        total_count = len(recent_history)
        
        uptime_percent = (active_count / total_count) * 100 if total_count > 0 else 0
        
        # Calculate average metrics
        avg_download = sum(float(m.get('download_mbps', 0)) for m in recent_history) / total_count if total_count > 0 else 0
        avg_upload = sum(float(m.get('upload_mbps', 0)) for m in recent_history) / total_count if total_count > 0 else 0
        avg_latency = sum(float(m.get('latency_ms', 0)) for m in recent_history) / total_count if total_count > 0 else 0
        avg_packet_loss = sum(float(m.get('packet_loss_percent', 0)) for m in recent_history) / total_count if total_count > 0 else 0
        
        # Determine if there are issues that need attention
        has_issues = (
            uptime_percent < 99.9 or
            avg_packet_loss > 5.0 or
            (metrics['tunnel_active'] and avg_download < 0.5)  # Low throughput when tunnel is active
        )
        
        # Get ISP upgrade recommendation if throughput is low
        upgrade_recommendation = None
        
        if avg_download < 1.0:
            report = self.network_optimizer.generate_report()
            upgrade_recommendation = report['upgrade_recommendation']['recommendation']
            
        # Send alert if there are issues
        if has_issues:
            self._send_alert(metrics, uptime_percent, avg_download, avg_latency, avg_packet_loss, upgrade_recommendation)
            
        health = {
            'uptime_percent': uptime_percent,
            'avg_download_mbps': avg_download,
            'avg_upload_mbps': avg_upload,
            'avg_latency_ms': avg_latency,
            'avg_packet_loss_percent': avg_packet_loss,
            'has_issues': has_issues,
            'upgrade_recommendation': upgrade_recommendation
        }
        
        return health
        
    def _send_alert(self, metrics, uptime_percent, avg_download, avg_latency, avg_packet_loss, upgrade_recommendation=None):
        """
        Send an alert email about tunnel issues.
        
        Args:
            metrics: Current metrics
            uptime_percent: Tunnel uptime percentage
            avg_download: Average download speed in Mbps
            avg_latency: Average latency in ms
            avg_packet_loss: Average packet loss in percent
            upgrade_recommendation: ISP upgrade recommendation if any
            
        Returns:
            bool: True if alert was sent, False otherwise
        """
        # Skip if no email configured
        if not self.alert_email or not self.smtp_username or not self.smtp_password:
            logger.warning("Alert email not configured, skipping alert")
            return False
            
        # Rate limit alerts (no more than one per hour)
        if self.last_alert_time and (datetime.now() - self.last_alert_time) < timedelta(hours=1):
            logger.info("Skipping alert due to rate limiting")
            return False
            
        try:
            subject = "WireGuard VPN Tunnel Alert"
            
            body = f"""
            <html>
            <body>
            <h2>WireGuard VPN Tunnel Alert</h2>
            <p>There are issues with your VPN tunnel that need attention.</p>
            
            <h3>Current Status</h3>
            <ul>
                <li>Tunnel Active: {"Yes" if metrics['tunnel_active'] else "No"}</li>
                <li>Uptime: {uptime_percent:.2f}%</li>
                <li>Download Speed: {metrics['download_mbps']:.2f} Mbps</li>
                <li>Upload Speed: {metrics['upload_mbps']:.2f} Mbps</li>
                <li>Latency: {metrics['latency_ms']:.2f} ms</li>
                <li>Packet Loss: {metrics['packet_loss_percent']:.2f}%</li>
            </ul>
            
            <h3>24-Hour Averages</h3>
            <ul>
                <li>Download Speed: {avg_download:.2f} Mbps</li>
                <li>Latency: {avg_latency:.2f} ms</li>
                <li>Packet Loss: {avg_packet_loss:.2f}%</li>
            </ul>
            """
            
            if not metrics['tunnel_active']:
                body += """
                <h3>Issue: Tunnel is down</h3>
                <p>The WireGuard tunnel is currently not active. Please check your connection and restart the tunnel if needed.</p>
                """
                
            if uptime_percent < 99.9:
                body += f"""
                <h3>Issue: Low uptime</h3>
                <p>The tunnel uptime is {uptime_percent:.2f}%, which is below the target of 99.9%. This indicates stability issues.</p>
                """
                
            if avg_packet_loss > 5.0:
                body += f"""
                <h3>Issue: High packet loss</h3>
                <p>The average packet loss is {avg_packet_loss:.2f}%, which is above the acceptable threshold of 5%.</p>
                """
                
            if metrics['tunnel_active'] and avg_download < 0.5:
                body += f"""
                <h3>Issue: Low throughput</h3>
                <p>The average download speed is {avg_download:.2f} Mbps, which is below the expected minimum of 0.5 Mbps.</p>
                """
                
            if upgrade_recommendation:
                body += f"""
                <h3>ISP Upgrade Recommendation</h3>
                <p>{upgrade_recommendation}</p>
                """
                
            body += """
            <p>Please check your VPN tunnel configuration and network connection.</p>
            
            <p>This is an automated alert from your WireGuard VPN Tunnel Manager.</p>
            </body>
            </html>
            """
            
            # Create email
            msg = MIMEMultipart()
            msg['From'] = self.smtp_username
            msg['To'] = self.alert_email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'html'))
            
            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Sent alert email to {self.alert_email}")
            self.last_alert_time = datetime.now()
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending alert email: {e}")
            return False
            
    def start_monitoring(self, interval=60):
        """
        Start continuous monitoring in a background thread.
        
        Args:
            interval: Monitoring interval in seconds
            
        Returns:
            bool: True if monitoring started, False otherwise
        """
        if self.monitoring:
            logger.warning("Monitoring already running")
            return False
            
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, args=(interval,))
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        logger.info(f"Started tunnel monitoring with {interval}s interval")
        return True
        
    def stop_monitoring(self):
        """
        Stop the monitoring thread.
        
        Returns:
            bool: True if monitoring was stopped, False otherwise
        """
        if not self.monitoring:
            logger.warning("Monitoring not running")
            return False
            
        self.monitoring = False
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
            
        logger.info("Stopped tunnel monitoring")
        return True
        
    def _monitoring_loop(self, interval):
        """
        Background thread for continuous monitoring.
        
        Args:
            interval: Monitoring interval in seconds
        """
        while self.monitoring:
            try:
                # Measure metrics
                metrics = self.measure_tunnel_metrics()
                
                # Add to history
                self._add_metrics_to_history(metrics)
                
                # Optimize parameters if tunnel is active
                if metrics['tunnel_active']:
                    optimization = self.optimize_parameters(metrics)
                    
                    if optimization and optimization.get('needed_adjustment', False):
                        logger.info(f"Applied parameter adjustments: MTU={optimization['mtu']}, Buffer={optimization['buffer_size']}")
                        
                # Check tunnel health
                health = self.check_tunnel_health(metrics)
                
                if health['has_issues']:
                    logger.warning(f"Tunnel health issues detected: uptime={health['uptime_percent']:.2f}%, "
                                 f"packet_loss={health['avg_packet_loss_percent']:.2f}%")
                else:
                    logger.info(f"Tunnel health is good: uptime={health['uptime_percent']:.2f}%, "
                              f"download={health['avg_download_mbps']:.2f}Mbps")
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                
            # Sleep until next check
            time.sleep(interval)


def main():
    """Main function to monitor the tunnel."""
    # Parse command line arguments
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor and optimize WireGuard VPN tunnel')
    parser.add_argument('--interval', type=int, default=60,
                       help='Monitoring interval in seconds')
    parser.add_argument('--email', type=str,
                       help='Email address for alerts')
    parser.add_argument('--analyze', action='store_true',
                       help='Analyze historical metrics and exit')
    parser.add_argument('--optimize', action='store_true',
                       help='Measure and optimize tunnel parameters once and exit')
    
    args = parser.parse_args()
    
    # Initialize tunnel monitor
    monitor = TunnelMonitor()
    
    # Set alert email if provided
    if args.email:
        monitor.alert_email = args.email
        
    if args.analyze:
        # Analyze historical metrics
        if len(monitor.metrics_history) > 0:
            # Calculate statistics
            uptime = sum(1 for m in monitor.metrics_history if m.get('tunnel_active') in (True, 'True')) / len(monitor.metrics_history) * 100
            avg_download = sum(float(m.get('download_mbps', 0)) for m in monitor.metrics_history) / len(monitor.metrics_history)
            avg_upload = sum(float(m.get('upload_mbps', 0)) for m in monitor.metrics_history) / len(monitor.metrics_history)
            avg_latency = sum(float(m.get('latency_ms', 0)) for m in monitor.metrics_history) / len(monitor.metrics_history)
            avg_packet_loss = sum(float(m.get('packet_loss_percent', 0)) for m in monitor.metrics_history) / len(monitor.metrics_history)
            
            print("\nTunnel Performance Analysis")
            print("==========================")
            print(f"Total metrics: {len(monitor.metrics_history)}")
            print(f"Tunnel uptime: {uptime:.2f}%")
            print(f"Average download: {avg_download:.2f} Mbps")
            print(f"Average upload: {avg_upload:.2f} Mbps")
            print(f"Average latency: {avg_latency:.2f} ms")
            print(f"Average packet loss: {avg_packet_loss:.2f}%")
            
            # Get ISP upgrade recommendation
            network_optimizer = NetworkOptimizer()
            report = network_optimizer.generate_report()
            upgrade = report['upgrade_recommendation']
            
            print("\nISP Upgrade Analysis")
            print("===================")
            print(f"{upgrade['recommendation']}")
            
            # Plot metrics if matplotlib is available
            try:
                import matplotlib.pyplot as plt
                
                print("\nGenerating performance graphs...")
                
                # Convert timestamps to datetime objects
                timestamps = []
                downloads = []
                uploads = []
                latencies = []
                packet_losses = []
                
                for m in monitor.metrics_history:
                    try:
                        timestamps.append(datetime.fromisoformat(m['timestamp']))
                        downloads.append(float(m.get('download_mbps', 0)))
                        uploads.append(float(m.get('upload_mbps', 0)))
                        latencies.append(float(m.get('latency_ms', 0)))
                        packet_losses.append(float(m.get('packet_loss_percent', 0)))
                    except (ValueError, KeyError):
                        continue
                        
                # Create figure with 3 subplots
                fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 12), sharex=True)
                
                # Plot throughput
                ax1.plot(timestamps, downloads, 'b-', label='Download')
                ax1.plot(timestamps, uploads, 'r-', label='Upload')
                ax1.set_ylabel('Throughput (Mbps)')
                ax1.set_title('VPN Tunnel Performance')
                ax1.legend()
                ax1.grid(True)
                
                # Plot latency
                ax2.plot(timestamps, latencies, 'g-')
                ax2.set_ylabel('Latency (ms)')
                ax2.grid(True)
                
                # Plot packet loss
                ax3.plot(timestamps, packet_losses, 'm-')
                ax3.set_xlabel('Time')
                ax3.set_ylabel('Packet Loss (%)')
                ax3.grid(True)
                
                plt.tight_layout()
                
                # Save figure
                output_file = 'tunnel_performance.png'
                plt.savefig(output_file)
                plt.close()
                
                print(f"Performance graphs saved to {output_file}")
                
            except ImportError:
                print("Matplotlib not available, skipping graphs")
                
        else:
            print("No historical metrics available for analysis")
            
        return 0
        
    elif args.optimize:
        # Measure and optimize tunnel parameters once
        metrics = monitor.measure_tunnel_metrics()
        
        if metrics['tunnel_active']:
            optimization = monitor.optimize_parameters(metrics)
            
            print("\nTunnel Optimization")
            print("===================")
            print(f"MTU: {optimization['mtu']}")
            print(f"Buffer size: {optimization['buffer_size']}")
            
            if optimization['needed_adjustment']:
                print(f"Expected throughput improvement: {optimization['throughput_improvement']:.2f}%")
                print(f"Expected latency improvement: {optimization['latency_improvement']:.2f}%")
            else:
                print("Current parameters are already optimal")
        else:
            print("Tunnel is not active, cannot optimize parameters")
            
        return 0
        
    else:
        # Start continuous monitoring
        monitor.start_monitoring(interval=args.interval)
        
        # Keep the main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping monitoring...")
            monitor.stop_monitoring()
            
        return 0


if __name__ == "__main__":
    sys.exit(main())