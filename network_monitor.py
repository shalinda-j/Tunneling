import os
import time
import logging
import json
import threading
import socket
import subprocess
from datetime import datetime, timedelta
from collections import deque
import math
import random

# Try importing the necessary libraries (would need to be installed)
try:
    import psutil
    import speedtest
except ImportError:
    # Mock implementations for development/testing
    class psutil:
        @staticmethod
        def net_io_counters(pernic=False):
            """Mock network IO counters"""
            if pernic:
                return {'eth0': psutil._NIC(0, 0, 0, 0, 0, 0)}
            return psutil._NIC(1000000, 500000, 1000, 500, 0, 0)
        
        class _NIC:
            def __init__(self, bytes_sent, bytes_recv, packets_sent, packets_recv, errin, errout):
                self.bytes_sent = bytes_sent
                self.bytes_recv = bytes_recv
                self.packets_sent = packets_sent
                self.packets_recv = packets_recv
                self.errin = errin
                self.errout = errout
    
    class speedtest:
        class Speedtest:
            def __init__(self):
                pass
                
            def get_best_server(self):
                return {"host": "test-server.net", "country": "Test Country"}
                
            def download(self):
                return 1500000  # 1.5 Mbps
                
            def upload(self):
                return 750000  # 0.75 Mbps
                
            def results(self):
                return speedtest.SpeedtestResults()
        
        class SpeedtestResults:
            def __init__(self):
                self.dict = {
                    "download": 1500000,
                    "upload": 750000,
                    "ping": 100,
                    "server": {
                        "host": "test-server.net",
                        "country": "Test Country"
                    }
                }

logger = logging.getLogger(__name__)

class NetworkMonitor:
    """
    Monitors network performance and collects statistics
    for the VPN tunnel.
    """
    def __init__(self, stats_history_length=720):  # Default: 12 hours at 1 measurement per minute
        """
        Initialize the network monitor
        
        Args:
            stats_history_length (int): Number of historical stats entries to keep
        """
        self.interface_name = 'wg0'  # Default WireGuard interface name
        self.current_stats = {
            'upload_speed': 0,
            'download_speed': 0,
            'latency': 0,
            'packet_loss': 0,
            'bytes_sent': 0,
            'bytes_received': 0,
            'tunnel_overhead': 0,
            'timestamp': datetime.now().isoformat()
        }
        
        # Queue to store historical stats
        self.stats_history = deque(maxlen=stats_history_length)
        
        # Previous IO values for calculating rates
        self.prev_io = None
        self.prev_time = time.time()
        
        # Start background monitoring thread
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
    
    def _monitor_loop(self):
        """Background thread for continuous monitoring"""
        fast_counter = 0
        slow_counter = 0
        
        while self.running:
            try:
                # Update throughput stats (every 5 seconds)
                self._update_throughput_stats()
                
                fast_counter += 1
                
                # Every minute (12 cycles at 5 seconds each)
                if fast_counter >= 12:
                    fast_counter = 0
                    
                    # Measure latency and packet loss
                    self._update_latency_stats()
                    
                    # Add current stats to history
                    self.stats_history.append(self.current_stats.copy())
                    
                    slow_counter += 1
                
                # Every hour (60 cycles at 1 minute each)
                if slow_counter >= 60:
                    slow_counter = 0
                    
                    # Run a speed test
                    self._run_speed_test()
                
                # Sleep for 5 seconds
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Error in network monitoring loop: {e}")
                time.sleep(10)  # Wait longer if there's an error
    
    def _update_throughput_stats(self):
        """Update the current throughput statistics"""
        try:
            # Get current time for rate calculations
            current_time = time.time()
            time_diff = current_time - self.prev_time
            
            # Get IO counters
            try:
                # Try to get WireGuard interface stats first
                io_stats = psutil.net_io_counters(pernic=True).get(self.interface_name)
                
                # Fall back to total network stats if WireGuard interface not found
                if io_stats is None:
                    io_stats = psutil.net_io_counters(pernic=False)
                    logger.debug(f"Could not find {self.interface_name} interface, using total network stats")
            except Exception:
                # Fall back to total network stats
                io_stats = psutil.net_io_counters(pernic=False)
            
            # Calculate rates if we have previous values
            if self.prev_io:
                # Calculate bytes/sec
                bytes_sent_rate = (io_stats.bytes_sent - self.prev_io.bytes_sent) / time_diff
                bytes_recv_rate = (io_stats.bytes_recv - self.prev_io.bytes_recv) / time_diff
                
                # Convert to Mbps (megabits per second)
                upload_mbps = (bytes_sent_rate * 8) / 1_000_000
                download_mbps = (bytes_recv_rate * 8) / 1_000_000
                
                # Update current stats
                self.current_stats['upload_speed'] = upload_mbps
                self.current_stats['download_speed'] = download_mbps
                self.current_stats['bytes_sent'] = io_stats.bytes_sent
                self.current_stats['bytes_received'] = io_stats.bytes_recv
                
                # Calculate estimated overhead (WireGuard adds about 20-60 bytes per packet)
                avg_packet_size = 1500  # Typical MTU
                wireguard_overhead_bytes = 60  # Approximate overhead per packet
                if io_stats.packets_sent > 0:
                    overhead_percentage = (wireguard_overhead_bytes / avg_packet_size) * 100
                    self.current_stats['tunnel_overhead'] = overhead_percentage
            
            # Save current values for next comparison
            self.prev_io = io_stats
            self.prev_time = current_time
            
            # Update timestamp
            self.current_stats['timestamp'] = datetime.now().isoformat()
            
        except Exception as e:
            logger.error(f"Error updating throughput stats: {e}")
    
    def _update_latency_stats(self):
        """Measure and update latency and packet loss statistics"""
        try:
            # Function to ping a host and measure latency and packet loss
            def ping_host(host, count=10):
                try:
                    # Run ping command
                    if os.name == 'nt':  # Windows
                        cmd = ['ping', '-n', str(count), host]
                    else:  # Linux/Mac
                        cmd = ['ping', '-c', str(count), host]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    
                    # Parse output to extract latency and packet loss
                    if result.returncode == 0:
                        output = result.stdout
                        
                        # Extract packet loss
                        loss_match = None
                        if os.name == 'nt':  # Windows
                            loss_match = re.search(r'(\d+)% loss', output)
                        else:  # Linux/Mac
                            loss_match = re.search(r'(\d+)% packet loss', output)
                        
                        packet_loss = float(loss_match.group(1)) if loss_match else 0
                        
                        # Extract average latency
                        latency_match = None
                        if os.name == 'nt':  # Windows
                            latency_match = re.search(r'Average = (\d+)ms', output)
                        else:  # Linux/Mac
                            latency_match = re.search(r'min/avg/max/.+ = [\d.]+/([\d.]+)/', output)
                        
                        latency = float(latency_match.group(1)) if latency_match else 0
                        
                        return {'latency': latency, 'packet_loss': packet_loss}
                    
                    return {'latency': 0, 'packet_loss': 100}  # If ping failed
                    
                except Exception as e:
                    logger.error(f"Error pinging host {host}: {e}")
                    return {'latency': 0, 'packet_loss': 100}
            
            # For development/testing, we'll mock the values
            import random
            import re
            
            # If we can import socket and run a real ping, do it
            # Otherwise fall back to simulated values
            result = {}
            try:
                # Try to resolve cloudflare DNS to make sure network is working
                socket.gethostbyname('1.1.1.1')
                
                # If that works, try to ping it
                result = ping_host('1.1.1.1')
            except:
                # Simulated values
                result = {
                    'latency': random.uniform(50, 150),  # 50-150ms
                    'packet_loss': random.uniform(0, 10)  # 0-10%
                }
            
            # Update current stats
            self.current_stats['latency'] = result['latency']
            self.current_stats['packet_loss'] = result['packet_loss']
            
        except Exception as e:
            logger.error(f"Error updating latency stats: {e}")
    
    def _run_speed_test(self):
        """Run a speed test to measure connection performance"""
        try:
            logger.info("Starting speed test")
            
            # Create speedtest object
            st = speedtest.Speedtest()
            
            # Get the best server
            st.get_best_server()
            
            # Run download test
            download_speed = st.download() / 1_000_000  # Convert to Mbps
            
            # Run upload test
            upload_speed = st.upload() / 1_000_000  # Convert to Mbps
            
            # Get results
            results = st.results.dict()
            
            logger.info(f"Speed test results: {download_speed:.2f} Mbps down, {upload_speed:.2f} Mbps up")
            
            # We don't update the current stats directly from the speed test
            # since it's a point-in-time measurement, but we store the results separately
            self.speed_test_results = {
                'download': download_speed,
                'upload': upload_speed,
                'ping': results['ping'],
                'server': results['server']['host'],
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error running speed test: {e}")
    
    def get_current_stats(self):
        """
        Get the current network statistics
        
        Returns:
            dict: Current network statistics
        """
        return self.current_stats
    
    def get_stats_history(self, hours=1):
        """
        Get historical network statistics
        
        Args:
            hours (int): Number of hours of history to return
            
        Returns:
            list: Historical network statistics
        """
        if not self.stats_history:
            return []
        
        # Calculate cutoff time
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # Filter stats by timestamp
        filtered_stats = []
        for stat in self.stats_history:
            try:
                stat_time = datetime.fromisoformat(stat['timestamp'])
                if stat_time >= cutoff_time:
                    filtered_stats.append(stat)
            except (ValueError, KeyError):
                continue
        
        return filtered_stats
