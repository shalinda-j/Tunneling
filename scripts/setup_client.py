#!/usr/bin/env python3
"""
Local PC Client Setup Script for WireGuard VPN Tunnel

This script guides the user through installing and configuring WireGuard
on their local PC and applies the client configuration generated by the
configure_wireguard.py script.

The script provides instructions for:
- Ubuntu/Linux: Using apt to install WireGuard and wg-quick
- Windows: Downloading and installing the WireGuard client
- MacOS: Using brew to install WireGuard and applying the configuration
"""

import os
import sys
import platform
import shutil
import logging
import subprocess
import webbrowser
from pathlib import Path
from datetime import datetime
import time
import tempfile

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ClientSetup:
    """
    Handles the setup of WireGuard on the local PC client.
    """
    def __init__(self, config_dir='./config'):
        """
        Initialize the client setup.
        
        Args:
            config_dir: Directory containing client configurations
        """
        self.config_dir = Path(config_dir)
        self.client_conf_path = self.config_dir / 'client.conf'
        self.client_split_conf_path = self.config_dir / 'client_split_tunnel.conf'
        self.client_aws_conf_path = self.config_dir / 'client_aws_only.conf'
        
        # Check if client configuration exists
        if not self.client_conf_path.exists():
            logger.error(f"Client configuration not found at {self.client_conf_path}")
            logger.error("Please run configure_wireguard.py first to generate client configuration")
            sys.exit(1)
            
        # Detect OS
        self.os_name = platform.system().lower()
        
    def check_wireguard_installed(self):
        """
        Check if WireGuard is installed on the system.
        
        Returns:
            bool: True if WireGuard is installed, False otherwise
        """
        try:
            if self.os_name == 'linux':
                # Check for wg command
                result = subprocess.run(['which', 'wg'], capture_output=True, text=True)
                return result.returncode == 0
                
            elif self.os_name == 'windows':
                # Check for WireGuard installation directory
                program_files = os.environ.get('ProgramFiles', 'C:\\Program Files')
                wireguard_path = os.path.join(program_files, 'WireGuard')
                return os.path.exists(wireguard_path)
                
            elif self.os_name == 'darwin':  # MacOS
                # Check for wg command
                result = subprocess.run(['which', 'wg'], capture_output=True, text=True)
                return result.returncode == 0
                
            else:
                logger.error(f"Unsupported OS: {self.os_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error checking WireGuard installation: {e}")
            return False
            
    def install_wireguard(self):
        """
        Install WireGuard on the local PC.
        
        Returns:
            bool: True if installation succeeded or already installed, False otherwise
        """
        if self.check_wireguard_installed():
            logger.info("WireGuard is already installed")
            return True
            
        logger.info(f"Installing WireGuard on {self.os_name}...")
        
        try:
            if self.os_name == 'linux':
                # Check which Linux distribution
                if os.path.exists('/etc/debian_version'):
                    # Debian/Ubuntu
                    commands = [
                        ['sudo', 'apt', 'update'],
                        ['sudo', 'apt', 'install', '-y', 'wireguard', 'wireguard-tools']
                    ]
                elif os.path.exists('/etc/fedora-release'):
                    # Fedora
                    commands = [
                        ['sudo', 'dnf', 'install', '-y', 'wireguard-tools']
                    ]
                elif os.path.exists('/etc/arch-release'):
                    # Arch Linux
                    commands = [
                        ['sudo', 'pacman', '-S', '--noconfirm', 'wireguard-tools']
                    ]
                else:
                    logger.error("Unsupported Linux distribution")
                    print("\nManual installation instructions:")
                    print("1. Install WireGuard for your distribution: https://www.wireguard.com/install/")
                    print("2. Once installed, return to this script to configure WireGuard")
                    return False
                    
                # Run commands
                for cmd in commands:
                    logger.info(f"Running: {' '.join(cmd)}")
                    result = subprocess.run(cmd)
                    if result.returncode != 0:
                        logger.error(f"Command failed: {' '.join(cmd)}")
                        return False
                        
            elif self.os_name == 'windows':
                # Download WireGuard installer
                print("\nWireGuard installation for Windows:")
                print("1. The WireGuard website will be opened in your browser.")
                print("2. Download and run the Windows installer.")
                print("3. Follow the installation instructions.")
                print("4. After installation, return to this script.")
                
                input("Press Enter to open the WireGuard website...")
                
                # Open WireGuard website
                webbrowser.open('https://www.wireguard.com/install/')
                
                # Wait for user to complete installation
                print("\nPlease complete the installation and then press Enter to continue...")
                input()
                
                # Check if installation was successful
                if not self.check_wireguard_installed():
                    logger.error("WireGuard installation not detected")
                    return False
                    
            elif self.os_name == 'darwin':  # MacOS
                # Check if Homebrew is installed
                result = subprocess.run(['which', 'brew'], capture_output=True, text=True)
                
                if result.returncode != 0:
                    logger.error("Homebrew not found, which is required to install WireGuard")
                    print("\nPlease install Homebrew first:")
                    print("/bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
                    print("After installing Homebrew, run this script again.")
                    return False
                    
                # Install WireGuard using Homebrew
                commands = [
                    ['brew', 'update'],
                    ['brew', 'install', 'wireguard-tools']
                ]
                
                for cmd in commands:
                    logger.info(f"Running: {' '.join(cmd)}")
                    result = subprocess.run(cmd)
                    if result.returncode != 0:
                        logger.error(f"Command failed: {' '.join(cmd)}")
                        return False
                        
            else:
                logger.error(f"Unsupported OS: {self.os_name}")
                return False
                
            logger.info("WireGuard installed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error installing WireGuard: {e}")
            return False
            
    def install_client_config(self, tunnel_mode='full'):
        """
        Install the client configuration.
        
        Args:
            tunnel_mode: Tunnel mode to install ('full', 'split', or 'aws')
            
        Returns:
            bool: True if configuration was installed successfully, False otherwise
        """
        logger.info(f"Installing {tunnel_mode} tunnel client configuration...")
        
        # Select the appropriate configuration file
        if tunnel_mode == 'split':
            conf_path = self.client_split_conf_path
            tunnel_desc = "split tunnel (only tunnel subnet traffic)"
        elif tunnel_mode == 'aws':
            conf_path = self.client_aws_conf_path
            tunnel_desc = "AWS-only tunnel (only AWS traffic)"
        else:
            conf_path = self.client_conf_path
            tunnel_desc = "full tunnel (all traffic)"
            
        if not conf_path.exists():
            logger.error(f"Configuration file not found: {conf_path}")
            return False
            
        try:
            if self.os_name == 'linux':
                # Check if running as root
                if os.geteuid() != 0:
                    logger.error("This operation requires root privileges")
                    print("\nPlease run this script with sudo:")
                    print(f"sudo python {sys.argv[0]}")
                    return False
                    
                # Create WireGuard configuration directory
                wireguard_dir = Path('/etc/wireguard')
                wireguard_dir.mkdir(exist_ok=True)
                
                # Copy configuration file
                dest_path = wireguard_dir / 'wg0.conf'
                shutil.copy(conf_path, dest_path)
                
                # Set permissions
                os.chmod(dest_path, 0o600)
                
                logger.info(f"Installed {tunnel_desc} configuration to {dest_path}")
                
                # Enable and start WireGuard
                commands = [
                    ['systemctl', 'enable', 'wg-quick@wg0'],
                    ['systemctl', 'start', 'wg-quick@wg0']
                ]
                
                for cmd in commands:
                    logger.info(f"Running: {' '.join(cmd)}")
                    result = subprocess.run(cmd)
                    if result.returncode != 0:
                        logger.error(f"Command failed: {' '.join(cmd)}")
                        logger.error("Failed to start WireGuard tunnel")
                        return False
                        
                logger.info("WireGuard tunnel started successfully")
                
            elif self.os_name == 'windows':
                # Create a temporary directory for the configuration
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_conf = os.path.join(temp_dir, 'wg0.conf')
                    
                    # Copy configuration file
                    shutil.copy(conf_path, temp_conf)
                    
                    # Import configuration using WireGuard UI
                    print("\nImporting WireGuard configuration:")
                    print("1. The WireGuard UI will be opened.")
                    print(f"2. Click 'Import tunnel(s) from file' and select the configuration at: {temp_conf}")
                    print("3. After importing, click 'Activate' to start the tunnel.")
                    
                    input("Press Enter to continue...")
                    
                    # Open WireGuard UI
                    program_files = os.environ.get('ProgramFiles', 'C:\\Program Files')
                    wireguard_exe = os.path.join(program_files, 'WireGuard', 'wireguard.exe')
                    
                    if os.path.exists(wireguard_exe):
                        subprocess.Popen([wireguard_exe])
                        
                        # Give user time to import configuration
                        print("\nPlease follow the steps to import the configuration.")
                        input("Press Enter when you have completed the import and activated the tunnel...")
                        
                        logger.info(f"Installed {tunnel_desc} configuration using WireGuard UI")
                    else:
                        logger.error(f"WireGuard executable not found at {wireguard_exe}")
                        print(f"\nPlease manually import the configuration file at {conf_path} into the WireGuard UI.")
                        return False
                        
            elif self.os_name == 'darwin':  # MacOS
                # Check if running as root
                if os.geteuid() != 0:
                    logger.error("This operation requires root privileges")
                    print("\nPlease run this script with sudo:")
                    print(f"sudo python {sys.argv[0]}")
                    return False
                    
                # Create WireGuard configuration directory
                wireguard_dir = Path('/usr/local/etc/wireguard')
                wireguard_dir.mkdir(exist_ok=True, parents=True)
                
                # Copy configuration file
                dest_path = wireguard_dir / 'wg0.conf'
                shutil.copy(conf_path, dest_path)
                
                # Set permissions
                os.chmod(dest_path, 0o600)
                
                logger.info(f"Installed {tunnel_desc} configuration to {dest_path}")
                
                # Start WireGuard
                commands = [
                    ['wg-quick', 'up', 'wg0']
                ]
                
                for cmd in commands:
                    logger.info(f"Running: {' '.join(cmd)}")
                    result = subprocess.run(cmd)
                    if result.returncode != 0:
                        logger.error(f"Command failed: {' '.join(cmd)}")
                        logger.error("Failed to start WireGuard tunnel")
                        return False
                        
                logger.info("WireGuard tunnel started successfully")
                
            else:
                logger.error(f"Unsupported OS: {self.os_name}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error installing client configuration: {e}")
            return False
            
    def verify_tunnel(self):
        """
        Verify that the tunnel is working.
        
        Returns:
            bool: True if tunnel is working, False otherwise
        """
        logger.info("Verifying tunnel connectivity...")
        
        try:
            # Check if we can ping the server endpoint (10.0.0.1)
            ping_cmd = ['ping', '-c', '3', '10.0.0.1']
            if self.os_name == 'windows':
                ping_cmd = ['ping', '-n', '3', '10.0.0.1']
                
            logger.info(f"Running: {' '.join(ping_cmd)}")
            ping_result = subprocess.run(ping_cmd, capture_output=True, text=True)
            
            if ping_result.returncode != 0:
                logger.error("Failed to ping tunnel endpoint")
                logger.error(f"Ping output: {ping_result.stdout}")
                logger.error(f"Ping error: {ping_result.stderr}")
                return False
                
            logger.info("Tunnel endpoint ping successful")
            
            # Get public IP to verify traffic routing
            print("\nChecking your public IP address...")
            
            # Try multiple IP checking services
            ip_services = [
                "https://api.ipify.org",
                "https://ifconfig.me",
                "https://icanhazip.com"
            ]
            
            public_ip = None
            for service in ip_services:
                try:
                    curl_cmd = ['curl', '-s', service]
                    curl_result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=10)
                    
                    if curl_result.returncode == 0 and curl_result.stdout.strip():
                        public_ip = curl_result.stdout.strip()
                        break
                        
                except Exception:
                    continue
                    
            if public_ip:
                print(f"Your current public IP address is: {public_ip}")
                print("Please verify this matches your AWS EC2 instance's IP address")
                print("if you're using full tunnel mode.")
            else:
                logger.warning("Could not determine your public IP address")
                
            # Try to connect to an AWS service
            print("\nTesting connection to AWS services...")
            
            aws_test_cmd = ['ping', '-c', '3', 's3.amazonaws.com']
            if self.os_name == 'windows':
                aws_test_cmd = ['ping', '-n', '3', 's3.amazonaws.com']
                
            aws_result = subprocess.run(aws_test_cmd, capture_output=True, text=True)
            
            if aws_result.returncode == 0:
                logger.info("AWS connectivity test successful")
                print("Successfully connected to AWS services through the tunnel")
            else:
                logger.warning("AWS connectivity test failed")
                print("Could not connect to AWS services. This might be expected if you're using split tunnel mode.")
                
            return True
            
        except Exception as e:
            logger.error(f"Error verifying tunnel: {e}")
            return False
            
    def print_usage_guide(self):
        """
        Print a usage guide for the tunnel.
        """
        print("\n========================================================")
        print("            WireGuard VPN Tunnel Usage Guide             ")
        print("========================================================")
        
        print("\nTunnel Management Commands:")
        
        if self.os_name == 'linux':
            print("- Start tunnel:  sudo wg-quick up wg0")
            print("- Stop tunnel:   sudo wg-quick down wg0")
            print("- Check status:  sudo wg show")
            
        elif self.os_name == 'windows':
            print("- Use the WireGuard UI to manage the tunnel")
            print("- The UI can be found in the system tray or start menu")
            
        elif self.os_name == 'darwin':  # MacOS
            print("- Start tunnel:  sudo wg-quick up wg0")
            print("- Stop tunnel:   sudo wg-quick down wg0")
            print("- Check status:  sudo wg show")
            
        print("\nAvailable Client Configurations:")
        print("- Full tunnel (all traffic):            ./config/client.conf")
        print("- Split tunnel (subnet only):           ./config/client_split_tunnel.conf")
        print("- AWS-only tunnel (AWS traffic only):   ./config/client_aws_only.conf")
        
        print("\nTo switch between tunnel modes, stop the current tunnel and install the desired configuration.")
        
        print("\nTroubleshooting:")
        print("- If the tunnel is not working, check your AWS EC2 instance is running")
        print("- Ensure the security group allows UDP traffic on port 51820")
        print("- Verify that your AWS endpoint address is correct in the configuration")
        
        print("\nFor more information, see the documentation at:")
        print("https://github.com/wee-technology-solutions/wireguard-vpn-tunnel-manager")
        
        print("\n========================================================\n")


def main():
    """Main function for setting up the local PC client."""
    # Parse command line arguments
    import argparse
    
    parser = argparse.ArgumentParser(description='Set up WireGuard VPN tunnel on local PC')
    parser.add_argument('--mode', choices=['full', 'split', 'aws'], default='full',
                       help='Tunnel mode to install: full (all traffic), split (subnet only), or aws (AWS traffic only)')
    parser.add_argument('--verify-only', action='store_true',
                       help='Only verify tunnel connectivity, skip installation')
    
    args = parser.parse_args()
    
    # Print banner
    print("\n========================================================")
    print("         WireGuard VPN Tunnel Client Setup Tool          ")
    print("========================================================")
    print(f"Setting up {args.mode} tunnel mode")
    print("--------------------------------------------------------\n")
    
    # Initialize client setup
    client_setup = ClientSetup()
    
    # Verify only
    if args.verify_only:
        client_setup.verify_tunnel()
        client_setup.print_usage_guide()
        return 0
        
    # Install WireGuard
    if not client_setup.install_wireguard():
        logger.error("Failed to install WireGuard")
        return 1
        
    # Install client configuration
    if not client_setup.install_client_config(tunnel_mode=args.mode):
        logger.error("Failed to install client configuration")
        return 1
        
    # Verify tunnel
    if not client_setup.verify_tunnel():
        logger.warning("Tunnel verification failed, but configuration was installed")
        
    # Print usage guide
    client_setup.print_usage_guide()
    
    print("WireGuard VPN tunnel setup completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())