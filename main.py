#!/usr/bin/env python3
"""
WireGuard VPN Tunnel Manager - Main Script

This is the primary entry point for the WireGuard VPN Tunnel Manager application.
It provides a command-line interface to:
1. Start the web interface
2. Run AWS EC2 setup
3. Configure WireGuard on EC2
4. Optimize routing with reinforcement learning
5. Monitor tunnel performance
6. Set up a local client
7. Run tests to verify functionality

Each function delegates to the appropriate specialized script in the /scripts directory.
"""

import os
import sys
import argparse
import logging
import subprocess
import importlib.util
from pathlib import Path

# For web interface
from app import app

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_script(script_path):
    """Dynamically import a Python script."""
    try:
        spec = importlib.util.spec_from_file_location("module.name", script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        logger.error(f"Error loading script {script_path}: {e}")
        return None

def run_web_interface(host="0.0.0.0", port=5000, debug=True):
    """Start the web interface."""
    logger.info(f"Starting web interface on {host}:{port}")
    app.run(host=host, port=port, debug=debug)

def run_ec2_setup(args=None):
    """Run the EC2 setup script."""
    script_path = Path("scripts/setup_ec2.py")
    if not script_path.exists():
        logger.error(f"Script not found: {script_path}")
        return False
    
    logger.info("Running EC2 setup script")
    
    # Check for required environment variables
    required_vars = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_KEY_NAME", "AWS_KEY_PATH"]
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set these variables in .env file or environment")
        return False
    
    # Either run as module or call main function directly
    try:
        ec2_module = load_script(script_path)
        if ec2_module and hasattr(ec2_module, 'main'):
            return ec2_module.main() == 0
        else:
            # Fallback to subprocess
            cmd = [sys.executable, str(script_path)]
            if args:
                cmd.extend(args)
            result = subprocess.run(cmd)
            return result.returncode == 0
    except Exception as e:
        logger.error(f"Error running EC2 setup: {e}")
        return False

def run_wireguard_setup(args=None):
    """Run the WireGuard configuration script."""
    script_path = Path("scripts/configure_wireguard.py")
    if not script_path.exists():
        logger.error(f"Script not found: {script_path}")
        return False
    
    logger.info("Running WireGuard configuration script")
    
    # Check for required environment variables
    required_vars = ["AWS_KEY_PATH"]
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set these variables in .env file or environment")
        return False
    
    # Check for instance configuration
    instance_config = Path("config/aws_instance.json")
    if not instance_config.exists():
        logger.error(f"Instance configuration not found: {instance_config}")
        logger.error("Please run EC2 setup first")
        return False
    
    # Run the script
    try:
        wg_module = load_script(script_path)
        if wg_module and hasattr(wg_module, 'main'):
            return wg_module.main() == 0
        else:
            # Fallback to subprocess
            cmd = [sys.executable, str(script_path)]
            if args:
                cmd.extend(args)
            result = subprocess.run(cmd)
            return result.returncode == 0
    except Exception as e:
        logger.error(f"Error running WireGuard setup: {e}")
        return False

def run_routing_optimization(mode="optimize", steps=10, explore=False, visualize=False):
    """Run the routing optimization script."""
    script_path = Path("scripts/optimize_routing.py")
    if not script_path.exists():
        logger.error(f"Script not found: {script_path}")
        return False
    
    logger.info(f"Running routing optimization in {mode} mode")
    
    # Build command-line arguments
    cmd = [sys.executable, str(script_path), f"--mode={mode}"]
    
    if mode == "train":
        cmd.append(f"--episodes={steps}")
    elif mode == "evaluate":
        cmd.append(f"--steps={steps}")
        if visualize:
            cmd.append("--visualize")
    elif mode == "optimize":
        if explore:
            cmd.append("--explore")
    
    # Run the script
    try:
        result = subprocess.run(cmd)
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Error running routing optimization: {e}")
        return False

def run_tunnel_monitoring(interval=60, email=None, analyze=False, optimize=False):
    """Run the tunnel monitoring script."""
    script_path = Path("scripts/monitor_tunnel.py")
    if not script_path.exists():
        logger.error(f"Script not found: {script_path}")
        return False
    
    logger.info("Running tunnel monitoring script")
    
    # Build command-line arguments
    cmd = [sys.executable, str(script_path)]
    
    if analyze:
        cmd.append("--analyze")
    elif optimize:
        cmd.append("--optimize")
    else:
        cmd.append(f"--interval={interval}")
        if email:
            cmd.append(f"--email={email}")
    
    # Run the script
    try:
        result = subprocess.run(cmd)
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Error running tunnel monitoring: {e}")
        return False

def run_client_setup(mode="full", verify_only=False):
    """Run the client setup script."""
    script_path = Path("scripts/setup_client.py")
    if not script_path.exists():
        logger.error(f"Script not found: {script_path}")
        return False
    
    logger.info(f"Running client setup script with {mode} tunnel mode")
    
    # Check for client configuration
    client_config = Path("config/client.conf")
    if not client_config.exists():
        logger.error(f"Client configuration not found: {client_config}")
        logger.error("Please run WireGuard setup first")
        return False
    
    # Build command-line arguments
    cmd = [sys.executable, str(script_path), f"--mode={mode}"]
    
    if verify_only:
        cmd.append("--verify-only")
    
    # Run the script
    try:
        result = subprocess.run(cmd)
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Error running client setup: {e}")
        return False

def run_tests():
    """Run tests to verify functionality."""
    test_path = Path("scripts/test_tunnel.py")
    if not test_path.exists():
        logger.error(f"Test script not found: {test_path}")
        return False
    
    logger.info("Running tunnel tests")
    
    # Run the test script
    try:
        test_module = load_script(test_path)
        if test_module and hasattr(test_module, 'main'):
            return test_module.main() == 0
        else:
            # Fallback to subprocess
            cmd = [sys.executable, str(test_path)]
            result = subprocess.run(cmd)
            return result.returncode == 0
    except Exception as e:
        logger.error(f"Error running tests: {e}")
        return False

def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="WireGuard VPN Tunnel Manager")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Web interface command
    web_parser = subparsers.add_parser("web", help="Start the web interface")
    web_parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    web_parser.add_argument("--port", type=int, default=5000, help="Port to bind to")
    web_parser.add_argument("--no-debug", action="store_true", help="Disable debug mode")
    
    # EC2 setup command
    subparsers.add_parser("setup-ec2", help="Set up AWS EC2 instance")
    
    # WireGuard setup command
    subparsers.add_parser("setup-wireguard", help="Configure WireGuard on the EC2 instance")
    
    # Routing optimization command
    optimize_parser = subparsers.add_parser("optimize", help="Optimize routing with reinforcement learning")
    optimize_parser.add_argument("--mode", choices=["train", "optimize", "evaluate"], default="optimize",
                                help="Optimization mode")
    optimize_parser.add_argument("--steps", type=int, default=10, help="Number of steps/episodes")
    optimize_parser.add_argument("--explore", action="store_true", help="Enable exploration")
    optimize_parser.add_argument("--visualize", action="store_true", help="Visualize results (evaluate mode only)")
    
    # Tunnel monitoring command
    monitor_parser = subparsers.add_parser("monitor", help="Monitor tunnel performance")
    monitor_parser.add_argument("--interval", type=int, default=60, help="Monitoring interval in seconds")
    monitor_parser.add_argument("--email", help="Email address for alerts")
    monitor_parser.add_argument("--analyze", action="store_true", help="Analyze historical metrics and exit")
    monitor_parser.add_argument("--optimize", action="store_true", help="Optimize tunnel parameters once and exit")
    
    # Client setup command
    client_parser = subparsers.add_parser("setup-client", help="Set up local client")
    client_parser.add_argument("--mode", choices=["full", "split", "aws"], default="full",
                             help="Tunnel mode (full, split, or AWS-only)")
    client_parser.add_argument("--verify-only", action="store_true", help="Only verify tunnel connectivity")
    
    # Test command
    subparsers.add_parser("test", help="Run tests")
    
    # All-in-one setup command
    setup_parser = subparsers.add_parser("setup-all", help="Run complete setup (EC2, WireGuard, optimization)")
    setup_parser.add_argument("--skip-ec2", action="store_true", help="Skip EC2 setup")
    setup_parser.add_argument("--skip-wireguard", action="store_true", help="Skip WireGuard setup")
    setup_parser.add_argument("--skip-optimize", action="store_true", help="Skip routing optimization")
    
    # Parse arguments
    args = parser.parse_args()
    
    # If no command is provided, start the web interface
    if not args.command:
        run_web_interface()
        return 0
    
    # Run the appropriate command
    if args.command == "web":
        run_web_interface(host=args.host, port=args.port, debug=not args.no_debug)
    elif args.command == "setup-ec2":
        if not run_ec2_setup():
            return 1
    elif args.command == "setup-wireguard":
        if not run_wireguard_setup():
            return 1
    elif args.command == "optimize":
        if not run_routing_optimization(mode=args.mode, steps=args.steps,
                                       explore=args.explore, visualize=args.visualize):
            return 1
    elif args.command == "monitor":
        if not run_tunnel_monitoring(interval=args.interval, email=args.email,
                                    analyze=args.analyze, optimize=args.optimize):
            return 1
    elif args.command == "setup-client":
        if not run_client_setup(mode=args.mode, verify_only=args.verify_only):
            return 1
    elif args.command == "test":
        if not run_tests():
            return 1
    elif args.command == "setup-all":
        success = True
        
        if not args.skip_ec2:
            logger.info("Setting up EC2 instance...")
            if not run_ec2_setup():
                success = False
                logger.error("EC2 setup failed")
            else:
                logger.info("EC2 setup completed successfully")
        
        if success and not args.skip_wireguard:
            logger.info("Configuring WireGuard...")
            if not run_wireguard_setup():
                success = False
                logger.error("WireGuard setup failed")
            else:
                logger.info("WireGuard setup completed successfully")
        
        if success and not args.skip_optimize:
            logger.info("Optimizing routing...")
            if not run_routing_optimization(mode="train", steps=100):
                success = False
                logger.error("Routing optimization failed")
            else:
                logger.info("Routing optimization completed successfully")
        
        if success:
            logger.info("All setup steps completed successfully")
            logger.info("Run 'python main.py setup-client' to set up the local client")
            logger.info("Run 'python main.py web' to start the web interface")
            return 0
        else:
            logger.error("Setup failed, please check the logs for details")
            return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
