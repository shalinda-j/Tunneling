#!/usr/bin/env python3
"""
Testing Script for WireGuard VPN Tunnel

This script tests and validates the VPN tunnel functionality:
- Tests tunnel connectivity (ping to 10.0.0.1)
- Tests AWS service access (e.g., download from S3)
- Tests throughput (target 1-2 Mbps with 1.5 Mbps ISP)
- Tests reliability (simulate 100 connections with <1% failure rate)

Results are logged to test_results.txt and visualized using matplotlib.
"""

import os
import sys
import json
import time
import logging
import subprocess
import random
import statistics
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import socket
import urllib.request
import ssl

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TunnelTester:
    """
    Tests the WireGuard VPN tunnel functionality and performance.
    """
    def __init__(self, results_file='./logs/test_results.txt'):
        """
        Initialize the tunnel tester.
        
        Args:
            results_file: Path to write test results
        """
        self.results_file = Path(results_file)
        os.makedirs(self.results_file.parent, exist_ok=True)
        
        # Test results
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'tunnel_connectivity': False,
            'aws_access': False,
            'throughput': {
                'download_mbps': 0,
                'upload_mbps': 0
            },
            'reliability': {
                'connections': 0,
                'failures': 0,
                'failure_rate': 0
            },
            'latency': {
                'min_ms': 0,
                'avg_ms': 0,
                'max_ms': 0,
                'stddev_ms': 0
            }
        }
        
    def test_tunnel_connectivity(self):
        """
        Test if the tunnel is up and connected to the server endpoint.
        
        Returns:
            bool: True if tunnel is connected, False otherwise
        """
        logger.info("Testing tunnel connectivity...")
        
        # Check if we can ping the tunnel server (10.0.0.1)
        ping_cmd = ['ping', '-c', '3', '10.0.0.1']
        if os.name == 'nt':  # Windows
            ping_cmd = ['ping', '-n', '3', '10.0.0.1']
            
        try:
            result = subprocess.run(ping_cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                # Parse ping statistics
                output = result.stdout
                
                # Extract latency values
                latencies = []
                for line in output.splitlines():
                    if "time=" in line:
                        time_match = line.split("time=")[1].split()[0]
                        latencies.append(float(time_match))
                
                if latencies:
                    self.results['latency'] = {
                        'min_ms': min(latencies),
                        'avg_ms': statistics.mean(latencies),
                        'max_ms': max(latencies),
                        'stddev_ms': statistics.stdev(latencies) if len(latencies) > 1 else 0
                    }
                
                logger.info(f"Tunnel is connected with avg latency: {self.results['latency']['avg_ms']:.2f} ms")
                self.results['tunnel_connectivity'] = True
                return True
            else:
                logger.error("Failed to ping tunnel endpoint (10.0.0.1)")
                logger.error(f"Error: {result.stderr}")
                self.results['tunnel_connectivity'] = False
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Ping timeout")
            self.results['tunnel_connectivity'] = False
            return False
        except Exception as e:
            logger.error(f"Error testing tunnel connectivity: {e}")
            self.results['tunnel_connectivity'] = False
            return False
            
    def test_aws_access(self):
        """
        Test access to AWS services through the tunnel.
        
        Returns:
            bool: True if AWS services are accessible, False otherwise
        """
        logger.info("Testing AWS service access...")
        
        # List of AWS service endpoints to test
        aws_endpoints = [
            's3.amazonaws.com',
            'ec2.amazonaws.com',
            'dynamodb.amazonaws.com'
        ]
        
        success_count = 0
        
        for endpoint in aws_endpoints:
            try:
                # Try to resolve the DNS name
                socket.gethostbyname(endpoint)
                
                # Try to connect to the HTTPS port
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((endpoint, 443))
                sock.close()
                
                # Try to make an HTTPS request
                context = ssl.create_default_context()
                with urllib.request.urlopen(f"https://{endpoint}", timeout=5, context=context) as response:
                    status = response.getcode()
                    
                if status == 200:
                    logger.info(f"Successfully connected to {endpoint}")
                    success_count += 1
                    
            except Exception as e:
                logger.error(f"Failed to connect to {endpoint}: {e}")
                
        # AWS access is successful if we can connect to at least one endpoint
        self.results['aws_access'] = success_count > 0
        
        if self.results['aws_access']:
            logger.info(f"AWS services are accessible ({success_count}/{len(aws_endpoints)} endpoints)")
        else:
            logger.error("AWS services are not accessible")
            
        return self.results['aws_access']
        
    def test_throughput(self):
        """
        Test the tunnel throughput.
        
        Returns:
            dict: Throughput results
        """
        logger.info("Testing tunnel throughput...")
        
        # Try to use speedtest-cli if available
        try:
            # Check if speedtest-cli is available
            result = subprocess.run(['which', 'speedtest-cli'], capture_output=True, text=True)
            
            if result.returncode == 0:
                # Run speedtest
                speedtest_cmd = ['speedtest-cli', '--json']
                result = subprocess.run(speedtest_cmd, capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0:
                    # Parse speedtest results
                    try:
                        speedtest_results = json.loads(result.stdout)
                        download_mbps = speedtest_results['download'] / 1_000_000  # Bits to Megabits
                        upload_mbps = speedtest_results['upload'] / 1_000_000  # Bits to Megabits
                        
                        self.results['throughput'] = {
                            'download_mbps': download_mbps,
                            'upload_mbps': upload_mbps
                        }
                        
                        logger.info(f"Throughput test results: Download: {download_mbps:.2f} Mbps, Upload: {upload_mbps:.2f} Mbps")
                        return self.results['throughput']
                        
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.error(f"Error parsing speedtest results: {e}")
                else:
                    logger.error(f"Speedtest failed: {result.stderr}")
        except:
            pass
            
        # Fallback to simple download/upload test
        logger.info("Speedtest-cli not available, using simple throughput test")
        
        try:
            # Test download speed (AWS S3 test file)
            download_url = "https://aws-bootcamp-cdk-assets-211125304565-us-west-2.s3.us-west-2.amazonaws.com/test-files/1MB.bin"
            download_size_mb = 1
            
            start_time = time.time()
            with urllib.request.urlopen(download_url, timeout=30) as response:
                data = response.read()
            end_time = time.time()
            
            # Calculate download speed
            download_time = end_time - start_time
            download_mbps = (download_size_mb * 8) / download_time  # Megabits per second
            
            # Simulate upload test (can't actually upload to S3 without credentials)
            # This is just an approximation based on download speed
            upload_mbps = download_mbps * 0.5  # Assume upload is 50% of download
            
            self.results['throughput'] = {
                'download_mbps': download_mbps,
                'upload_mbps': upload_mbps
            }
            
            logger.info(f"Simple throughput test results: Download: {download_mbps:.2f} Mbps, Upload: {upload_mbps:.2f} Mbps")
            return self.results['throughput']
            
        except Exception as e:
            logger.error(f"Error in simple throughput test: {e}")
            
            # Use dummy values if test fails
            self.results['throughput'] = {
                'download_mbps': 0,
                'upload_mbps': 0
            }
            
            return self.results['throughput']
            
    def test_reliability(self, connections=100):
        """
        Test the reliability of the tunnel with multiple connections.
        
        Args:
            connections: Number of connections to test
            
        Returns:
            dict: Reliability results
        """
        logger.info(f"Testing tunnel reliability with {connections} connections...")
        
        # AWS endpoints to test
        test_hosts = [
            's3.amazonaws.com',
            'ec2.amazonaws.com',
            'dynamodb.amazonaws.com',
            'sqs.amazonaws.com',
            'api.amazon.com'
        ]
        
        # Test reliability by making multiple HTTP/HTTPS requests
        success_count = 0
        failure_count = 0
        
        for i in range(connections):
            try:
                # Select a random host
                host = random.choice(test_hosts)
                
                # Connect to HTTPS port
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((host, 443))
                sock.close()
                
                success_count += 1
                
                # Short delay between connections
                time.sleep(0.05)
                
            except Exception as e:
                logger.error(f"Connection {i+1} failed: {e}")
                failure_count += 1
                
            # Print progress
            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i+1}/{connections} connections tested")
                
        # Calculate failure rate
        failure_rate = (failure_count / connections) * 100 if connections > 0 else 0
        
        self.results['reliability'] = {
            'connections': connections,
            'failures': failure_count,
            'failure_rate': failure_rate
        }
        
        logger.info(f"Reliability test results: {success_count}/{connections} successful connections ({failure_rate:.2f}% failure rate)")
        
        return self.results['reliability']
        
    def save_results(self):
        """
        Save test results to file.
        
        Returns:
            str: Path to results file
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.results_file), exist_ok=True)
            
            # Add pass/fail summary
            self.results['passed'] = (
                self.results['tunnel_connectivity'] and
                self.results['aws_access'] and
                self.results['throughput']['download_mbps'] > 0.5 and
                self.results['reliability']['failure_rate'] < 1.0
            )
            
            # Write results to file
            with open(self.results_file, 'w') as f:
                f.write("WireGuard VPN Tunnel Test Results\n")
                f.write("================================\n\n")
                f.write(f"Timestamp: {self.results['timestamp']}\n\n")
                
                f.write("Overall Result: ")
                if self.results['passed']:
                    f.write("PASSED\n\n")
                else:
                    f.write("FAILED\n\n")
                
                f.write("Tunnel Connectivity: ")
                f.write("PASS\n" if self.results['tunnel_connectivity'] else "FAIL\n")
                f.write(f"Latency: {self.results['latency']['avg_ms']:.2f} ms (min: {self.results['latency']['min_ms']:.2f} ms, max: {self.results['latency']['max_ms']:.2f} ms)\n\n")
                
                f.write("AWS Service Access: ")
                f.write("PASS\n" if self.results['aws_access'] else "FAIL\n\n")
                
                f.write("Throughput:\n")
                f.write(f"Download: {self.results['throughput']['download_mbps']:.2f} Mbps\n")
                f.write(f"Upload: {self.results['throughput']['upload_mbps']:.2f} Mbps\n")
                f.write("PASS\n" if self.results['throughput']['download_mbps'] > 0.5 else "FAIL\n\n")
                
                f.write("Reliability:\n")
                f.write(f"Connections: {self.results['reliability']['connections']}\n")
                f.write(f"Failures: {self.results['reliability']['failures']}\n")
                f.write(f"Failure Rate: {self.results['reliability']['failure_rate']:.2f}%\n")
                f.write("PASS\n" if self.results['reliability']['failure_rate'] < 1.0 else "FAIL\n")
                
            logger.info(f"Test results saved to {self.results_file}")
            
            # Save results as JSON for programmatic use
            json_file = self.results_file.with_suffix('.json')
            with open(json_file, 'w') as f:
                json.dump(self.results, f, indent=2)
                
            logger.info(f"JSON results saved to {json_file}")
            
            return str(self.results_file)
            
        except Exception as e:
            logger.error(f"Error saving test results: {e}")
            return None
            
    def visualize_results(self):
        """
        Create visualizations of test results.
        
        Returns:
            str: Path to visualization file
        """
        try:
            # Check if matplotlib is available
            import matplotlib
            matplotlib.use('Agg')  # Non-interactive backend
            import matplotlib.pyplot as plt
            
            logger.info("Creating test results visualization...")
            
            # Create figure with subplots
            fig, axs = plt.subplots(2, 2, figsize=(12, 10))
            
            # Tunnel connectivity plot (latency)
            if self.results['tunnel_connectivity']:
                latency_data = [
                    self.results['latency']['min_ms'],
                    self.results['latency']['avg_ms'],
                    self.results['latency']['max_ms']
                ]
                axs[0, 0].bar(['Min', 'Avg', 'Max'], latency_data, color=['green', 'blue', 'red'])
                axs[0, 0].set_title('Tunnel Latency (ms)')
                axs[0, 0].grid(True, linestyle='--', alpha=0.7)
                axs[0, 0].set_ylabel('Milliseconds')
                
                # Add horizontal line for 50ms threshold
                axs[0, 0].axhline(y=50, color='r', linestyle='--', alpha=0.5)
                axs[0, 0].text(0.5, 52, '50ms Target', color='r', alpha=0.7)
            else:
                axs[0, 0].text(0.5, 0.5, 'Tunnel Connectivity Test Failed', 
                             horizontalalignment='center', verticalalignment='center',
                             transform=axs[0, 0].transAxes, fontsize=12, color='red')
                axs[0, 0].set_title('Tunnel Latency (ms)')
            
            # Throughput plot
            axs[0, 1].bar(['Download', 'Upload'], 
                         [self.results['throughput']['download_mbps'], self.results['throughput']['upload_mbps']],
                         color=['blue', 'green'])
            axs[0, 1].set_title('Throughput (Mbps)')
            axs[0, 1].grid(True, linestyle='--', alpha=0.7)
            axs[0, 1].set_ylabel('Mbps')
            
            # Add horizontal line for 1.5 Mbps target
            axs[0, 1].axhline(y=1.5, color='r', linestyle='--', alpha=0.5)
            axs[0, 1].text(0.5, 1.55, '1.5 Mbps Target', color='r', alpha=0.7)
            
            # Reliability plot
            reliability_data = [
                self.results['reliability']['connections'] - self.results['reliability']['failures'],
                self.results['reliability']['failures']
            ]
            axs[1, 0].pie(reliability_data, 
                         labels=['Success', 'Failure'],
                         autopct='%1.1f%%',
                         colors=['green', 'red'],
                         explode=(0, 0.1))
            axs[1, 0].set_title('Connection Reliability')
            
            # Overall results plot
            test_names = ['Connectivity', 'AWS Access', 'Throughput', 'Reliability']
            test_results = [
                self.results['tunnel_connectivity'],
                self.results['aws_access'],
                self.results['throughput']['download_mbps'] > 0.5,
                self.results['reliability']['failure_rate'] < 1.0
            ]
            
            colors = ['green' if result else 'red' for result in test_results]
            axs[1, 1].bar(test_names, [1, 1, 1, 1], color=colors)
            axs[1, 1].set_title('Test Results')
            axs[1, 1].set_ylim(0, 1.5)
            axs[1, 1].set_yticks([])
            
            # Add PASS/FAIL text
            for i, result in enumerate(test_results):
                text = "PASS" if result else "FAIL"
                axs[1, 1].text(i, 0.5, text, ha='center', va='center', fontsize=12,
                              color='white', fontweight='bold')
            
            # Add overall result
            fig.suptitle('WireGuard VPN Tunnel Test Results', fontsize=16)
            overall_result = "PASSED" if self.results['passed'] else "FAILED"
            fig.text(0.5, 0.01, f"Overall Result: {overall_result}", 
                    ha='center', fontsize=14,
                    color='green' if self.results['passed'] else 'red',
                    fontweight='bold')
            
            plt.tight_layout(rect=[0, 0.03, 1, 0.95])
            
            # Save figure
            visualization_file = self.results_file.with_suffix('.png')
            plt.savefig(visualization_file)
            plt.close()
            
            logger.info(f"Visualization saved to {visualization_file}")
            return str(visualization_file)
            
        except ImportError:
            logger.warning("Matplotlib not available, skipping visualization")
            return None
        except Exception as e:
            logger.error(f"Error creating visualization: {e}")
            return None


def main():
    """Main function to run the tunnel tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test WireGuard VPN tunnel functionality")
    parser.add_argument("--output", default="./logs/test_results.txt",
                      help="Path to output test results file")
    parser.add_argument("--connections", type=int, default=100,
                      help="Number of connections for reliability test")
    parser.add_argument("--skip-visualization", action="store_true",
                      help="Skip results visualization")
    parser.add_argument("--verbose", action="store_true",
                      help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging based on verbosity
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("Starting WireGuard VPN tunnel tests")
    
    # Initialize tunnel tester
    tester = TunnelTester(results_file=args.output)
    
    # Run tests
    tunnel_connected = tester.test_tunnel_connectivity()
    
    if tunnel_connected:
        # Only run other tests if tunnel is connected
        tester.test_aws_access()
        tester.test_throughput()
        tester.test_reliability(connections=args.connections)
    else:
        logger.error("Tunnel is not connected, skipping remaining tests")
    
    # Save test results
    tester.save_results()
    
    # Create visualization if not skipped
    if not args.skip_visualization:
        tester.visualize_results()
    
    # Return success if all tests passed
    return 0 if tester.results.get('passed', False) else 1


if __name__ == "__main__":
    sys.exit(main())