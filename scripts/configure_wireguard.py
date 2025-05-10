#!/usr/bin/env python3
"""
WireGuard VPN Configuration Script

This script uses paramiko to automate WireGuard setup on the EC2 instance:
- Install WireGuard and generate server/client key pairs
- Configure wg0.conf with private IP range (10.0.0.1/24), UDP 51820, and NAT for internet forwarding
- Optimize MTU (1280) based on the mathematical model to minimize fragmentation
- Save client config (client.conf) for local PC

Prerequisites:
- AWS credentials in .env file
- EC2 instance information in ./config/aws_instance.json (created by setup_ec2.py)
- SSH key for the EC2 instance
"""

import os
import sys
import json
import logging
import paramiko
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

class WireGuardConfig:
    """
    Handles the configuration of WireGuard on an EC2 instance.
    """
    def __init__(self, instance_info_file='./config/aws_instance.json', key_path=None):
        """
        Initialize the WireGuard configuration.
        
        Args:
            instance_info_file: Path to the JSON file with instance information
            key_path: Path to the SSH private key file
        """
        self.instance_info_file = Path(instance_info_file)
        self.key_path = key_path or os.environ.get('AWS_KEY_PATH')
        
        if not self.key_path:
            logger.error("AWS_KEY_PATH environment variable is required")
            sys.exit(1)
            
        self.instance_info = self._load_instance_info()
        
        if not self.instance_info:
            logger.error(f"Instance information not found at {instance_info_file}")
            sys.exit(1)
            
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # WireGuard configuration
        self.server_private_key = None
        self.server_public_key = None
        self.client_private_key = None
        self.client_public_key = None
        self.server_endpoint = f"{self.instance_info['PublicIpAddress']}:51820"
        self.server_address = "10.0.0.1/24"
        self.client_address = "10.0.0.2/24"
        self.dns_servers = "1.1.1.1, 8.8.8.8"  # Cloudflare and Google DNS
        self.mtu = 1280  # Optimized MTU based on mathematical model
        self.keep_alive = 25  # Persistent keepalive to maintain NAT connections
        
    def _load_instance_info(self):
        """
        Load instance information from JSON file.
        
        Returns:
            dict: Instance information
        """
        try:
            if not self.instance_info_file.exists():
                logger.error(f"Instance information file not found: {self.instance_info_file}")
                return None
                
            with open(self.instance_info_file, 'r') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"Error loading instance information: {e}")
            return None
            
    def connect(self):
        """
        Connect to the EC2 instance via SSH.
        
        Returns:
            bool: True if connection succeeded, False otherwise
        """
        try:
            ip_address = self.instance_info['PublicIpAddress']
            logger.info(f"Connecting to {ip_address} via SSH...")
            
            self.ssh_client.connect(
                hostname=ip_address,
                username='ubuntu',
                key_filename=self.key_path,
                timeout=10
            )
            
            logger.info("Connected to instance")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to instance: {e}")
            return False
            
    def execute_command(self, command, sudo=False):
        """
        Execute a command on the instance.
        
        Args:
            command: Command to execute
            sudo: Whether to run with sudo
            
        Returns:
            tuple: (stdout, stderr, exit_status)
        """
        if sudo and not command.startswith("sudo "):
            command = f"sudo {command}"
            
        logger.debug(f"Executing: {command}")
        
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()
            
            stdout_str = stdout.read().decode()
            stderr_str = stderr.read().decode()
            
            if exit_status != 0:
                logger.error(f"Command failed: {command}\nError: {stderr_str}")
                
            return (stdout_str, stderr_str, exit_status)
            
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            return ("", str(e), -1)
            
    def install_wireguard(self):
        """
        Install WireGuard on the EC2 instance.
        
        Returns:
            bool: True if installation succeeded, False otherwise
        """
        logger.info("Installing WireGuard...")
        
        commands = [
            "sudo apt update",
            "sudo apt install -y wireguard wireguard-tools iptables",
            "sudo apt install -y net-tools iputils-ping traceroute", # Useful networking tools
        ]
        
        for cmd in commands:
            _, _, exit_status = self.execute_command(cmd)
            if exit_status != 0:
                return False
                
        # Check if WireGuard is installed correctly
        stdout, _, exit_status = self.execute_command("which wg")
        if exit_status != 0 or not stdout.strip():
            logger.error("WireGuard does not appear to be installed correctly")
            return False
            
        logger.info("WireGuard installed successfully")
        return True
        
    def generate_keys(self):
        """
        Generate WireGuard key pairs for server and client.
        
        Returns:
            bool: True if key generation succeeded, False otherwise
        """
        logger.info("Generating WireGuard keys...")
        
        # Generate server keys
        stdout, _, exit_status = self.execute_command("wg genkey")
        if exit_status != 0:
            return False
            
        self.server_private_key = stdout.strip()
        
        stdout, _, exit_status = self.execute_command(f"echo '{self.server_private_key}' | wg pubkey")
        if exit_status != 0:
            return False
            
        self.server_public_key = stdout.strip()
        
        # Generate client keys
        stdout, _, exit_status = self.execute_command("wg genkey")
        if exit_status != 0:
            return False
            
        self.client_private_key = stdout.strip()
        
        stdout, _, exit_status = self.execute_command(f"echo '{self.client_private_key}' | wg pubkey")
        if exit_status != 0:
            return False
            
        self.client_public_key = stdout.strip()
        
        logger.info("WireGuard keys generated successfully")
        logger.info(f"Server public key: {self.server_public_key}")
        logger.info(f"Client public key: {self.client_public_key}")
        
        return True
        
    def configure_server(self):
        """
        Configure WireGuard server on the EC2 instance.
        
        Returns:
            bool: True if configuration succeeded, False otherwise
        """
        logger.info("Configuring WireGuard server...")
        
        # Create server configuration
        server_config = f"""[Interface]
PrivateKey = {self.server_private_key}
Address = {self.server_address}
ListenPort = 51820
PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
MTU = {self.mtu}

[Peer]
PublicKey = {self.client_public_key}
AllowedIPs = 10.0.0.2/32
"""
        
        # Write server configuration
        _, _, exit_status = self.execute_command(f"echo '{server_config}' | sudo tee /etc/wireguard/wg0.conf")
        if exit_status != 0:
            return False
            
        # Set permissions
        _, _, exit_status = self.execute_command("sudo chmod 600 /etc/wireguard/wg0.conf")
        if exit_status != 0:
            return False
            
        # Enable IP forwarding
        commands = [
            "echo 'net.ipv4.ip_forward=1' | sudo tee /etc/sysctl.d/99-wireguard.conf",
            "sudo sysctl -p /etc/sysctl.d/99-wireguard.conf",
            "sudo sysctl net.ipv4.ip_forward=1"
        ]
        
        for cmd in commands:
            _, _, exit_status = self.execute_command(cmd)
            if exit_status != 0:
                return False
                
        logger.info("WireGuard server configured successfully")
        return True
        
    def start_server(self):
        """
        Start the WireGuard server.
        
        Returns:
            bool: True if server started successfully, False otherwise
        """
        logger.info("Starting WireGuard server...")
        
        commands = [
            "sudo systemctl enable wg-quick@wg0",
            "sudo systemctl start wg-quick@wg0"
        ]
        
        for cmd in commands:
            _, _, exit_status = self.execute_command(cmd)
            if exit_status != 0:
                return False
                
        # Check server status
        stdout, _, exit_status = self.execute_command("sudo wg")
        if exit_status != 0:
            logger.error("WireGuard server failed to start")
            return False
            
        logger.info("WireGuard server started successfully")
        logger.info(f"Server status:\n{stdout}")
        
        return True
        
    def create_client_config(self, output_file='./config/client.conf'):
        """
        Create client configuration file.
        
        Args:
            output_file: Path to write the client configuration
            
        Returns:
            bool: True if configuration was created successfully, False otherwise
        """
        logger.info(f"Creating client configuration at {output_file}...")
        
        # Create client configuration
        client_config = f"""[Interface]
PrivateKey = {self.client_private_key}
Address = {self.client_address}
DNS = {self.dns_servers}
MTU = {self.mtu}

[Peer]
PublicKey = {self.server_public_key}
Endpoint = {self.server_endpoint}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = {self.keep_alive}
"""
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            with open(output_file, 'w') as f:
                f.write(client_config)
                
            logger.info(f"Client configuration saved to {output_file}")
            
            # Also create a split tunnel configuration as an alternative
            split_tunnel_config = client_config.replace("AllowedIPs = 0.0.0.0/0", "AllowedIPs = 10.0.0.0/24")
            split_output_file = os.path.join(os.path.dirname(output_file), "client_split_tunnel.conf")
            
            with open(split_output_file, 'w') as f:
                f.write(split_tunnel_config)
                
            logger.info(f"Split tunnel client configuration saved to {split_output_file}")
            
            # Create a configuration for AWS-specific traffic only
            aws_tunnel_config = client_config.replace(
                "AllowedIPs = 0.0.0.0/0",
                "AllowedIPs = 10.0.0.0/24, 52.94.0.0/16, 54.239.0.0/16, 52.119.0.0/16, 52.219.0.0/16"
            )
            aws_output_file = os.path.join(os.path.dirname(output_file), "client_aws_only.conf")
            
            with open(aws_output_file, 'w') as f:
                f.write(aws_tunnel_config)
                
            logger.info(f"AWS-only client configuration saved to {aws_output_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating client configuration: {e}")
            return False
            
    def save_configuration(self, output_file='./config/wireguard_config.json'):
        """
        Save WireGuard configuration to a JSON file.
        
        Args:
            output_file: Path to write the configuration
            
        Returns:
            bool: True if configuration was saved successfully, False otherwise
        """
        try:
            config = {
                'server_endpoint': self.server_endpoint,
                'server_address': self.server_address,
                'server_public_key': self.server_public_key,
                'client_address': self.client_address,
                'client_public_key': self.client_public_key,
                'client_private_key': self.client_private_key,
                'mtu': self.mtu,
                'dns_servers': self.dns_servers,
                'keep_alive': self.keep_alive
            }
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            with open(output_file, 'w') as f:
                json.dump(config, f, indent=2)
                
            logger.info(f"WireGuard configuration saved to {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving WireGuard configuration: {e}")
            return False
            
    def setup_failover(self):
        """
        Setup automatic restart for the WireGuard tunnel if it disconnects.
        
        Returns:
            bool: True if failover setup succeeded, False otherwise
        """
        logger.info("Setting up WireGuard tunnel failover...")
        
        # Create a script to check connection and restart if needed
        failover_script = """#!/bin/bash
# WireGuard tunnel failover script

# Log file
LOG_FILE="/var/log/wireguard_failover.log"

echo "$(date): Running WireGuard tunnel check" >> $LOG_FILE

# Check if WireGuard interface is up
if ! ip link show wg0 > /dev/null 2>&1; then
    echo "$(date): WireGuard interface not found, restarting..." >> $LOG_FILE
    systemctl restart wg-quick@wg0
    exit 1
fi

# Check if we can ping through the tunnel
ping -c 3 10.0.0.2 > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "$(date): Cannot ping client, restarting tunnel..." >> $LOG_FILE
    systemctl restart wg-quick@wg0
    exit 1
fi

# Check external connectivity
ping -c 3 8.8.8.8 > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "$(date): No external connectivity, restarting tunnel..." >> $LOG_FILE
    systemctl restart wg-quick@wg0
    exit 1
fi

echo "$(date): WireGuard tunnel is running correctly" >> $LOG_FILE
exit 0
"""
        
        # Write the failover script
        _, _, exit_status = self.execute_command(f"echo '{failover_script}' | sudo tee /usr/local/bin/wireguard_failover.sh")
        if exit_status != 0:
            return False
            
        # Make it executable
        _, _, exit_status = self.execute_command("sudo chmod +x /usr/local/bin/wireguard_failover.sh")
        if exit_status != 0:
            return False
            
        # Create a cron job to run the script every 5 minutes
        cron_job = "*/5 * * * * /usr/local/bin/wireguard_failover.sh"
        _, _, exit_status = self.execute_command(f"(crontab -l 2>/dev/null; echo '{cron_job}') | crontab -")
        if exit_status != 0:
            return False
            
        logger.info("WireGuard tunnel failover setup completed")
        return True
        
    def optimize_mtu(self):
        """
        Optimize MTU for the WireGuard tunnel based on network conditions.
        
        Returns:
            int: Optimized MTU value
        """
        logger.info("Optimizing MTU for WireGuard tunnel...")
        
        # Start with the default MTU
        mtu = self.mtu
        
        # Test connectivity with different MTU values
        mtu_values = [1280, 1380, 1420, 1480]
        
        for test_mtu in mtu_values:
            logger.info(f"Testing MTU value: {test_mtu}")
            
            # Update MTU in server configuration
            _, _, exit_status = self.execute_command(
                f"sudo sed -i 's/MTU = {mtu}/MTU = {test_mtu}/' /etc/wireguard/wg0.conf"
            )
            if exit_status != 0:
                continue
                
            # Restart WireGuard with new MTU
            _, _, exit_status = self.execute_command("sudo systemctl restart wg-quick@wg0")
            if exit_status != 0:
                continue
                
            # Give it time to apply
            time.sleep(5)
            
            # Test ping with large packet sizes
            stdout, _, exit_status = self.execute_command(f"ping -c 5 -M do -s {test_mtu - 60} 8.8.8.8")
            if exit_status == 0 and "100% packet loss" not in stdout and "icmp_seq=" in stdout:
                # This MTU works well
                mtu = test_mtu
                logger.info(f"MTU {test_mtu} works well")
            else:
                logger.info(f"MTU {test_mtu} resulted in packet loss")
        
        # Update the WireGuard configuration with optimized MTU
        _, _, exit_status = self.execute_command(
            f"sudo sed -i 's/MTU = {self.mtu}/MTU = {mtu}/' /etc/wireguard/wg0.conf"
        )
        if exit_status != 0:
            logger.warning(f"Failed to update server MTU to {mtu}, keeping {self.mtu}")
            return self.mtu
            
        # Restart WireGuard with final MTU
        _, _, exit_status = self.execute_command("sudo systemctl restart wg-quick@wg0")
        if exit_status != 0:
            logger.warning("Failed to restart WireGuard with optimized MTU")
            
        logger.info(f"MTU optimized to {mtu}")
        self.mtu = mtu
        return mtu
        
    def disconnect(self):
        """Close the SSH connection."""
        if self.ssh_client:
            self.ssh_client.close()
            logger.info("SSH connection closed")


def main():
    """Main function to configure WireGuard on the EC2 instance."""
    # Initialize WireGuard configuration
    wg_config = WireGuardConfig()
    
    # Connect to the instance
    if not wg_config.connect():
        logger.error("Failed to connect to instance")
        sys.exit(1)
        
    try:
        # Install WireGuard
        if not wg_config.install_wireguard():
            logger.error("Failed to install WireGuard")
            sys.exit(1)
            
        # Generate keys
        if not wg_config.generate_keys():
            logger.error("Failed to generate WireGuard keys")
            sys.exit(1)
            
        # Configure server
        if not wg_config.configure_server():
            logger.error("Failed to configure WireGuard server")
            sys.exit(1)
            
        # Start server
        if not wg_config.start_server():
            logger.error("Failed to start WireGuard server")
            sys.exit(1)
            
        # Setup failover
        if not wg_config.setup_failover():
            logger.warning("Failed to setup WireGuard failover")
            # Continue anyway
            
        # Optimize MTU
        optimized_mtu = wg_config.optimize_mtu()
        logger.info(f"Optimized MTU: {optimized_mtu}")
        
        # Create client configuration
        if not wg_config.create_client_config():
            logger.error("Failed to create client configuration")
            sys.exit(1)
            
        # Save configuration
        if not wg_config.save_configuration():
            logger.warning("Failed to save WireGuard configuration")
            # Continue anyway
            
        logger.info("WireGuard configuration completed successfully")
        logger.info(f"Server endpoint: {wg_config.server_endpoint}")
        logger.info(f"Client configuration: ./config/client.conf")
        logger.info(f"Split tunnel configuration: ./config/client_split_tunnel.conf")
        logger.info(f"AWS-only configuration: ./config/client_aws_only.conf")
        
    finally:
        # Disconnect
        wg_config.disconnect()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())