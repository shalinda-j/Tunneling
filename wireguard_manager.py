import os
import json
import logging
import subprocess
import time
from pathlib import Path
import socket
import ipaddress
import re
from datetime import datetime

# Third-party imports that would need to be installed
try:
    import wgconfig
    from wgconfig.wgexec import WGExec
except ImportError:
    # Mock implementation for development/testing purposes
    class wgconfig:
        class WGConfig:
            def __init__(self, file):
                self.file = file
                self._peers = {}
                self._interface = {}
                
            def add_peer(self, public_key, **kwargs):
                self._peers[public_key] = kwargs
                
            def add_attr(self, peer_public_key, key, value):
                if peer_public_key not in self._peers:
                    self._peers[peer_public_key] = {}
                self._peers[peer_public_key][key] = value
                
            def read_file(self):
                pass
                
            def write_file(self):
                pass
    
    class WGExec:
        @staticmethod
        def up(interface):
            return True
            
        @staticmethod
        def down(interface):
            return True

logger = logging.getLogger(__name__)

class WireGuardManager:
    """
    Manages WireGuard VPN tunnel configuration and operations
    """
    def __init__(self, config_dir=None, interface_name='wg0'):
        """
        Initialize the WireGuard manager
        
        Args:
            config_dir (str): Directory to store WireGuard configuration
            interface_name (str): Name of the WireGuard interface
        """
        self.interface_name = interface_name
        
        # Default to user's home directory if not specified
        if config_dir is None:
            config_dir = os.path.join(os.path.expanduser('~'), '.vpn_tunnel')
        
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        
        self.wg_config_path = self.config_dir / f"{interface_name}.conf"
        self.settings_path = self.config_dir / "settings.json"
        
        # Load or create settings
        self._load_settings()
        
        # Check if WireGuard is installed
        self.wg_available = self._check_wireguard_available()
        if not self.wg_available:
            logger.warning("WireGuard does not appear to be installed or accessible")
    
    def _check_wireguard_available(self):
        """Check if WireGuard is installed and accessible"""
        try:
            result = subprocess.run(['which', 'wg'], 
                                   capture_output=True, 
                                   text=True)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Error checking WireGuard availability: {e}")
            return False
    
    def _load_settings(self):
        """Load settings from JSON file or create defaults"""
        if self.settings_path.exists():
            try:
                with open(self.settings_path, 'r') as f:
                    self.settings = json.load(f)
            except json.JSONDecodeError:
                logger.error("Settings file is corrupted, creating defaults")
                self._create_default_settings()
        else:
            self._create_default_settings()
    
    def _create_default_settings(self):
        """Create default settings"""
        self.settings = {
            "aws_endpoint": "",
            "aws_public_key": "",
            "local_private_key": "",
            "local_ip": "10.0.0.2/24",
            "dns": "1.1.1.1, 8.8.8.8",
            "last_connection": None,
            "connection_count": 0,
            "auto_reconnect": True,
            "keep_alive": 25,
            "direct_tunnel": True  # Default to full tunnel mode for direct AWS connection
        }
        self._save_settings()
    
    def _save_settings(self):
        """Save settings to JSON file"""
        with open(self.settings_path, 'w') as f:
            json.dump(self.settings, f, indent=2)
    
    def get_config(self):
        """Get the current configuration"""
        return self.settings
    
    def update_config(self, config_data):
        """
        Update WireGuard configuration
        
        Args:
            config_data (dict): New configuration parameters
            
        Returns:
            dict: Result of the operation
        """
        try:
            # Update settings with new values
            for key, value in config_data.items():
                if key in self.settings:
                    self.settings[key] = value
            
            # Save settings
            self._save_settings()
            
            # Generate new WireGuard config file
            self._generate_wg_config()
            
            return {"success": True}
        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            return {"success": False, "error": str(e)}
    
    def _generate_wg_config(self):
        """Generate WireGuard configuration file from settings"""
        try:
            # Create a new WireGuard config
            wg_conf = wgconfig.WGConfig(str(self.wg_config_path))
            
            # Set interface section
            interface_attrs = {
                "PrivateKey": self.settings["local_private_key"],
                "Address": self.settings["local_ip"],
                "DNS": self.settings["dns"]
            }
            
            for key, value in interface_attrs.items():
                if value:  # Only set if value is not empty
                    wg_conf._interface[key] = value
            
            # Add peer (AWS server)
            if self.settings["aws_public_key"] and self.settings["aws_endpoint"]:
                wg_conf.add_peer(self.settings["aws_public_key"])
                
                # Configure AllowedIPs based on direct_tunnel setting
                # When direct_tunnel is True, route ALL traffic through the tunnel (0.0.0.0/0)
                # When direct_tunnel is False, only route tunnel subnet traffic (10.0.0.0/24)
                if self.settings.get("direct_tunnel", True):
                    # Full tunnel mode - route everything through AWS
                    wg_conf.add_attr(self.settings["aws_public_key"], "AllowedIPs", "0.0.0.0/0")
                    logger.info("Configuring for full tunnel mode (direct AWS connection)")
                else:
                    # Split tunnel mode - only route tunnel subnet traffic
                    tunnel_network = '.'.join(self.settings["local_ip"].split('.')[:3]) + '.0/24'
                    wg_conf.add_attr(self.settings["aws_public_key"], "AllowedIPs", tunnel_network)
                    logger.info(f"Configuring for split tunnel mode (subnet only: {tunnel_network})")
                
                wg_conf.add_attr(self.settings["aws_public_key"], "Endpoint", self.settings["aws_endpoint"])
                wg_conf.add_attr(self.settings["aws_public_key"], "PersistentKeepalive", str(self.settings["keep_alive"]))
            
            # Write config to file
            wg_conf.write_file()
            logger.debug(f"WireGuard configuration written to {self.wg_config_path}")
            
            return True
        except Exception as e:
            logger.error(f"Error generating WireGuard config: {e}")
            return False
    
    def start_tunnel(self):
        """
        Start the WireGuard tunnel
        
        Returns:
            dict: Result of the operation
        """
        if not self.wg_available:
            return {"success": False, "error": "WireGuard is not installed or accessible"}
        
        try:
            # Generate config file if it doesn't exist
            if not self.wg_config_path.exists():
                if not self._generate_wg_config():
                    return {"success": False, "error": "Failed to generate WireGuard configuration"}
            
            # Start the WireGuard interface
            result = WGExec.up(self.interface_name)
            
            if result:
                # Update connection stats
                self.settings["last_connection"] = datetime.now().isoformat()
                self.settings["connection_count"] += 1
                self._save_settings()
                logger.info(f"WireGuard tunnel started for interface {self.interface_name}")
                return {"success": True}
            else:
                logger.error(f"Failed to start WireGuard tunnel for interface {self.interface_name}")
                return {"success": False, "error": "Failed to start WireGuard tunnel"}
                
        except Exception as e:
            logger.error(f"Error starting WireGuard tunnel: {e}")
            return {"success": False, "error": str(e)}
    
    def stop_tunnel(self):
        """
        Stop the WireGuard tunnel
        
        Returns:
            dict: Result of the operation
        """
        if not self.wg_available:
            return {"success": False, "error": "WireGuard is not installed or accessible"}
        
        try:
            # Stop the WireGuard interface
            result = WGExec.down(self.interface_name)
            
            if result:
                logger.info(f"WireGuard tunnel stopped for interface {self.interface_name}")
                return {"success": True}
            else:
                logger.error(f"Failed to stop WireGuard tunnel for interface {self.interface_name}")
                return {"success": False, "error": "Failed to stop WireGuard tunnel"}
                
        except Exception as e:
            logger.error(f"Error stopping WireGuard tunnel: {e}")
            return {"success": False, "error": str(e)}
    
    def get_tunnel_status(self):
        """
        Get the current status of the WireGuard tunnel
        
        Returns:
            dict: Tunnel status information
        """
        status = {
            "running": False,
            "uptime": None,
            "last_handshake": None,
            "transfer_rx": 0,
            "transfer_tx": 0,
            "endpoint": None,
            "aws_public_key": self.settings.get("aws_public_key", ""),
            "local_ip": self.settings.get("local_ip", ""),
            "available": self.wg_available
        }
        
        if not self.wg_available:
            return status
        
        try:
            # Run wg show command to get interface status
            result = subprocess.run(['wg', 'show', self.interface_name], 
                                   capture_output=True, 
                                   text=True)
            
            if result.returncode == 0:
                # Parse the output
                output = result.stdout
                status["running"] = True
                
                # Extract peer info
                if "peer:" in output.lower():
                    lines = output.split('\n')
                    for i, line in enumerate(lines):
                        if "transfer:" in line.lower():
                            transfer_match = re.search(r"transfer: (\d+\.?\d*) ([KMG]iB) received, (\d+\.?\d*) ([KMG]iB) sent", line)
                            if transfer_match:
                                rx_val, rx_unit, tx_val, tx_unit = transfer_match.groups()
                                # Convert to bytes
                                status["transfer_rx"] = self._convert_to_bytes(float(rx_val), rx_unit)
                                status["transfer_tx"] = self._convert_to_bytes(float(tx_val), tx_unit)
                        
                        if "endpoint:" in line.lower():
                            endpoint_match = re.search(r"endpoint: ([\d\.]+:\d+)", line)
                            if endpoint_match:
                                status["endpoint"] = endpoint_match.group(1)
                        
                        if "latest handshake:" in line.lower():
                            handshake_match = re.search(r"latest handshake: (.*)", line)
                            if handshake_match:
                                status["last_handshake"] = handshake_match.group(1)
                
                # Calculate uptime based on last_connection setting
                if self.settings.get("last_connection"):
                    try:
                        last_conn = datetime.fromisoformat(self.settings["last_connection"])
                        uptime_seconds = (datetime.now() - last_conn).total_seconds()
                        
                        # Format uptime nicely
                        days, remainder = divmod(int(uptime_seconds), 86400)
                        hours, remainder = divmod(remainder, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        
                        parts = []
                        if days > 0:
                            parts.append(f"{days}d")
                        if hours > 0:
                            parts.append(f"{hours}h")
                        if minutes > 0:
                            parts.append(f"{minutes}m")
                        parts.append(f"{seconds}s")
                        
                        status["uptime"] = " ".join(parts)
                    except Exception as e:
                        logger.error(f"Error parsing last_connection timestamp: {e}")
            
            return status
        except Exception as e:
            logger.error(f"Error getting tunnel status: {e}")
            return status
    
    def _convert_to_bytes(self, value, unit):
        """Convert file size units to bytes"""
        unit_multipliers = {
            'B': 1,
            'KiB': 1024,
            'MiB': 1024 ** 2,
            'GiB': 1024 ** 3
        }
        
        return int(value * unit_multipliers.get(unit, 1))
    
    def generate_keypair(self):
        """
        Generate a new WireGuard keypair
        
        Returns:
            dict: Contains private and public keys
        """
        if not self.wg_available:
            logger.warning("WireGuard not available, using mock key generation")
            # Mock key generation for development/testing
            import base64
            import secrets
            
            # Generate random bytes for "private key"
            private_key_bytes = secrets.token_bytes(32)
            private_key = base64.b64encode(private_key_bytes).decode('utf-8')
            
            # Generate a "public key" (in real usage we'd use curve25519)
            public_key_bytes = secrets.token_bytes(32) 
            public_key = base64.b64encode(public_key_bytes).decode('utf-8')
            
            return {
                "private_key": private_key,
                "public_key": public_key
            }
        
        try:
            # Generate private key
            private_key_result = subprocess.run(['wg', 'genkey'], 
                                              capture_output=True, 
                                              text=True)
            
            if private_key_result.returncode != 0:
                raise Exception("Failed to generate private key")
            
            private_key = private_key_result.stdout.strip()
            
            # Generate public key from private key
            public_key_result = subprocess.run(['wg', 'pubkey'], 
                                             input=private_key,
                                             capture_output=True, 
                                             text=True)
            
            if public_key_result.returncode != 0:
                raise Exception("Failed to generate public key")
            
            public_key = public_key_result.stdout.strip()
            
            return {
                "private_key": private_key,
                "public_key": public_key
            }
        except Exception as e:
            logger.error(f"Error generating WireGuard keypair: {e}")
            return {
                "private_key": "",
                "public_key": ""
            }
