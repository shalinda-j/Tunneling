#!/usr/bin/env python3
"""
AWS EC2 Instance Setup Script for WireGuard VPN Tunnel

This script uses boto3 to launch an EC2 instance in ap-southeast-1 (Singapore) region
with the following configuration:
- c5n.large instance type (with enhanced networking up to 25 Gbps intra-AWS)
- Ubuntu 20.04 LTS AMI
- Security group allowing UDP 51820 (WireGuard), TCP 22 (SSH), and TCP 80/443 (testing)
- Elastic IP for static addressing
- Configuration for jumbo frames (MTU 9001) and IP forwarding

Prerequisites:
- AWS credentials in .env file (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
- An SSH key pair in the ap-southeast-1 region
"""

import os
import sys
import time
import logging
import boto3
import paramiko
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

class EC2Setup:
    """
    Handles the setup of an EC2 instance for the WireGuard VPN tunnel.
    """
    def __init__(self, region_name='ap-southeast-1', key_name=None, instance_type='c5n.large'):
        """
        Initialize the EC2 setup.
        
        Args:
            region_name: AWS region to launch the instance in
            key_name: Name of the SSH key pair to use (must exist in the region)
            instance_type: EC2 instance type to launch
        """
        self.region_name = region_name
        self.key_name = key_name
        self.instance_type = instance_type
        
        # Get AWS credentials from environment
        self.aws_access_key = os.environ.get('AWS_ACCESS_KEY_ID')
        self.aws_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        
        if not self.aws_access_key or not self.aws_secret_key:
            logger.error("AWS credentials not found. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env file.")
            sys.exit(1)
            
        if not self.key_name:
            logger.error("SSH key pair name is required. Please specify a key pair that exists in the region.")
            sys.exit(1)
            
        # Initialize boto3 clients
        self.ec2 = boto3.resource('ec2',
                                 region_name=self.region_name,
                                 aws_access_key_id=self.aws_access_key,
                                 aws_secret_access_key=self.aws_secret_key)
        
        self.ec2_client = boto3.client('ec2',
                                     region_name=self.region_name,
                                     aws_access_key_id=self.aws_access_key,
                                     aws_secret_access_key=self.aws_secret_key)
        
        # Store instance and security group IDs
        self.instance_id = None
        self.security_group_id = None
        self.elastic_ip = None
        
    def create_security_group(self, vpc_id):
        """
        Create a security group for the WireGuard VPN instance.
        
        Args:
            vpc_id: ID of the VPC to create the security group in
            
        Returns:
            str: Security group ID
        """
        logger.info("Creating security group for WireGuard VPN tunnel")
        
        # Create security group
        security_group = self.ec2.create_security_group(
            GroupName='WireGuard-VPN-SG',
            Description='Security group for WireGuard VPN tunnel',
            VpcId=vpc_id
        )
        
        security_group_id = security_group.id
        logger.info(f"Security group created: {security_group_id}")
        
        # Add inbound rules for WireGuard, SSH, and HTTP/HTTPS
        security_group.authorize_ingress(
            GroupId=security_group_id,
            IpPermissions=[
                {
                    'IpProtocol': 'udp',
                    'FromPort': 51820,
                    'ToPort': 51820,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'WireGuard VPN'}]
                },
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 22,
                    'ToPort': 22,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'SSH'}]
                },
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 80,
                    'ToPort': 80,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'HTTP'}]
                },
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 443,
                    'ToPort': 443,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'HTTPS'}]
                }
            ]
        )
        
        self.security_group_id = security_group_id
        return security_group_id
        
    def find_ubuntu_ami(self):
        """
        Find the latest Ubuntu 20.04 LTS AMI ID in the region.
        
        Returns:
            str: AMI ID
        """
        logger.info("Finding latest Ubuntu 20.04 LTS AMI")
        
        response = self.ec2_client.describe_images(
            Owners=['099720109477'],  # Canonical's AWS account ID
            Filters=[
                {'Name': 'name', 'Values': ['ubuntu/images/hvm-ssd/ubuntu-focal-20.04-amd64-server-*']},
                {'Name': 'state', 'Values': ['available']}
            ]
        )
        
        # Sort by creation date (newest first)
        images = sorted(response['Images'], key=lambda x: x['CreationDate'], reverse=True)
        
        if images:
            ami_id = images[0]['ImageId']
            logger.info(f"Found Ubuntu 20.04 LTS AMI: {ami_id}")
            return ami_id
        else:
            logger.error("No Ubuntu 20.04 LTS AMI found")
            return None
            
    def launch_instance(self):
        """
        Launch an EC2 instance for the WireGuard VPN server.
        
        Returns:
            dict: Instance information
        """
        logger.info(f"Launching EC2 instance in {self.region_name}")
        
        # Get default VPC ID
        vpcs = list(self.ec2.vpcs.filter(Filters=[{'Name': 'isDefault', 'Values': ['true']}]))
        
        if not vpcs:
            logger.error("No default VPC found. Please specify a VPC ID.")
            return None
            
        vpc_id = vpcs[0].id
        logger.info(f"Using default VPC: {vpc_id}")
        
        # Create security group
        if not self.security_group_id:
            self.create_security_group(vpc_id)
        
        # Find AMI
        ami_id = self.find_ubuntu_ami()
        if not ami_id:
            return None
            
        # Create instance
        try:
            instances = self.ec2.create_instances(
                ImageId=ami_id,
                InstanceType=self.instance_type,
                KeyName=self.key_name,
                MinCount=1,
                MaxCount=1,
                SecurityGroupIds=[self.security_group_id],
                BlockDeviceMappings=[
                    {
                        'DeviceName': '/dev/sda1',
                        'Ebs': {
                            'VolumeSize': 20,  # 20 GB
                            'VolumeType': 'gp3',
                            'DeleteOnTermination': True
                        }
                    }
                ],
                TagSpecifications=[
                    {
                        'ResourceType': 'instance',
                        'Tags': [
                            {'Key': 'Name', 'Value': 'WireGuard-VPN-Server'},
                            {'Key': 'Project', 'Value': 'VPN-Tunnel-Manager'}
                        ]
                    }
                ],
                EbsOptimized=True,
                NetworkInterfaces=[
                    {
                        'DeviceIndex': 0,
                        'AssociatePublicIpAddress': True,
                        'DeleteOnTermination': True
                    }
                ]
            )
            
            instance = instances[0]
            self.instance_id = instance.id
            
            logger.info(f"Waiting for instance {instance.id} to be running...")
            instance.wait_until_running()
            
            # Reload instance to get updated information
            instance.reload()
            
            logger.info(f"Instance {instance.id} is running with public IP: {instance.public_ip_address}")
            
            return {
                'InstanceId': instance.id,
                'PublicIpAddress': instance.public_ip_address,
                'PrivateIpAddress': instance.private_ip_address,
                'Region': self.region_name,
                'InstanceType': instance.instance_type,
                'State': instance.state['Name']
            }
            
        except Exception as e:
            logger.error(f"Error launching instance: {e}")
            return None
            
    def allocate_elastic_ip(self):
        """
        Allocate and associate an Elastic IP address with the instance.
        
        Returns:
            str: Elastic IP address
        """
        if not self.instance_id:
            logger.error("No instance launched yet")
            return None
            
        try:
            # Allocate Elastic IP
            allocation = self.ec2_client.allocate_address(Domain='vpc')
            self.elastic_ip = allocation['PublicIp']
            allocation_id = allocation['AllocationId']
            
            logger.info(f"Allocated Elastic IP: {self.elastic_ip}")
            
            # Associate with instance
            self.ec2_client.associate_address(
                AllocationId=allocation_id,
                InstanceId=self.instance_id
            )
            
            logger.info(f"Associated Elastic IP {self.elastic_ip} with instance {self.instance_id}")
            
            return self.elastic_ip
            
        except Exception as e:
            logger.error(f"Error allocating Elastic IP: {e}")
            return None
            
    def wait_for_ssh(self, ip_address, username='ubuntu', key_path=None, timeout=300):
        """
        Wait for SSH to be available on the instance.
        
        Args:
            ip_address: Public IP address to connect to
            username: SSH username
            key_path: Path to SSH private key file
            timeout: Maximum time to wait in seconds
            
        Returns:
            bool: True if SSH is available, False otherwise
        """
        if not key_path:
            logger.error("SSH private key path is required")
            return False
            
        logger.info(f"Waiting for SSH to be available on {ip_address}...")
        
        start_time = time.time()
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        while (time.time() - start_time) < timeout:
            try:
                ssh_client.connect(
                    hostname=ip_address,
                    username=username,
                    key_filename=key_path,
                    timeout=10
                )
                
                logger.info("SSH is available")
                ssh_client.close()
                return True
                
            except Exception as e:
                wait_time = time.time() - start_time
                logger.debug(f"Waiting for SSH ({wait_time:.1f}s): {e}")
                time.sleep(5)
                
        logger.error(f"Timeout waiting for SSH after {timeout} seconds")
        return False
        
    def configure_instance_network(self, ip_address, username='ubuntu', key_path=None):
        """
        Configure the instance for jumbo frames and IP forwarding.
        
        Args:
            ip_address: Public IP address to connect to
            username: SSH username
            key_path: Path to SSH private key file
            
        Returns:
            bool: True if configuration succeeded, False otherwise
        """
        if not key_path:
            logger.error("SSH private key path is required")
            return False
            
        logger.info(f"Configuring network on {ip_address}...")
        
        try:
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client.connect(
                hostname=ip_address,
                username=username,
                key_filename=key_path,
                timeout=10
            )
            
            # Commands to execute for network configuration
            commands = [
                # Update package lists
                "sudo apt update",
                
                # Configure jumbo frames (MTU 9001)
                "sudo ip link set dev eth0 mtu 9001",
                
                # Make MTU setting persistent
                "echo 'auto eth0' | sudo tee -a /etc/network/interfaces.d/eth0.cfg",
                "echo 'iface eth0 inet dhcp' | sudo tee -a /etc/network/interfaces.d/eth0.cfg",
                "echo '    mtu 9001' | sudo tee -a /etc/network/interfaces.d/eth0.cfg",
                
                # Enable IP forwarding
                "echo 'net.ipv4.ip_forward=1' | sudo tee -a /etc/sysctl.conf",
                "sudo sysctl -p"
            ]
            
            for cmd in commands:
                logger.debug(f"Executing: {cmd}")
                stdin, stdout, stderr = ssh_client.exec_command(cmd)
                exit_status = stdout.channel.recv_exit_status()
                
                if exit_status != 0:
                    error = stderr.read().decode()
                    logger.error(f"Command failed: {cmd}\nError: {error}")
                
            logger.info("Network configuration completed")
            ssh_client.close()
            return True
            
        except Exception as e:
            logger.error(f"Error configuring instance network: {e}")
            return False
            
    def get_instance_info(self):
        """
        Get information about the launched instance.
        
        Returns:
            dict: Instance information
        """
        if not self.instance_id:
            logger.error("No instance launched yet")
            return None
            
        try:
            instance = self.ec2.Instance(self.instance_id)
            instance.reload()
            
            return {
                'InstanceId': instance.id,
                'PublicIpAddress': self.elastic_ip or instance.public_ip_address,
                'PrivateIpAddress': instance.private_ip_address,
                'Region': self.region_name,
                'InstanceType': instance.instance_type,
                'State': instance.state['Name'],
                'LaunchTime': instance.launch_time.isoformat(),
                'SecurityGroupId': self.security_group_id,
                'VpcId': instance.vpc_id,
                'SubnetId': instance.subnet_id
            }
            
        except Exception as e:
            logger.error(f"Error getting instance info: {e}")
            return None
            
    def save_instance_info(self, info, filename='./config/aws_instance.json'):
        """
        Save instance information to a JSON file.
        
        Args:
            info: Instance information
            filename: Path to save the JSON file
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        import json
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            with open(filename, 'w') as f:
                json.dump(info, f, indent=2)
                
            logger.info(f"Instance information saved to {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving instance information: {e}")
            return False


def main():
    """Main function to set up the EC2 instance."""
    # Get SSH key info
    key_name = os.environ.get('AWS_KEY_NAME')
    key_path = os.environ.get('AWS_KEY_PATH')
    
    if not key_name:
        logger.error("AWS_KEY_NAME environment variable is required")
        sys.exit(1)
        
    if not key_path:
        logger.error("AWS_KEY_PATH environment variable is required")
        sys.exit(1)
    
    # Initialize EC2 setup
    setup = EC2Setup(key_name=key_name)
    
    # Launch instance
    instance_info = setup.launch_instance()
    if not instance_info:
        logger.error("Failed to launch instance")
        sys.exit(1)
    
    # Allocate Elastic IP
    elastic_ip = setup.allocate_elastic_ip()
    if not elastic_ip:
        logger.error("Failed to allocate Elastic IP")
        # Continue anyway since we have a public IP
    
    # Use the Elastic IP if allocated, otherwise use the instance's public IP
    ip_address = elastic_ip or instance_info['PublicIpAddress']
    
    # Wait for SSH to be available
    if not setup.wait_for_ssh(ip_address, key_path=key_path):
        logger.error("Failed to connect to instance via SSH")
        sys.exit(1)
    
    # Configure instance network
    if not setup.configure_instance_network(ip_address, key_path=key_path):
        logger.error("Failed to configure instance network")
        sys.exit(1)
    
    # Get updated instance info
    instance_info = setup.get_instance_info()
    
    # Save instance info
    setup.save_instance_info(instance_info)
    
    logger.info("EC2 instance setup complete")
    logger.info(f"Instance ID: {instance_info['InstanceId']}")
    logger.info(f"Public IP: {instance_info['PublicIpAddress']}")
    logger.info(f"SSH: ssh -i {key_path} ubuntu@{instance_info['PublicIpAddress']}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())