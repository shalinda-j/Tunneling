#!/usr/bin/env python3
"""
Reinforcement Learning for Dynamic Routing Optimization

This script implements a reinforcement learning agent using TensorFlow
to dynamically adjust routing parameters based on network conditions.

- State: Current throughput, latency, packet loss (measured via iperf3 or ping)
- Actions: Adjust MTU, enable/disable split tunneling, prioritize AWS IPs
- Reward: R = w1 * T_eff - w2 * L_tunnel - w3 * P_loss

The script can operate in three modes:
1. Training: Train the RL agent on simulated network data
2. Inference: Apply the trained model to adjust routing in real-time
3. Testing: Evaluate the performance of different routing strategies
"""

import os
import sys
import json
import logging
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List, Tuple, Optional
from dotenv import load_dotenv

# Import local modules
sys.path.append('.')
from models.network_optimization import NetworkOptimizer, NetworkParameters, NetworkMetrics
from models.reinforcement_learning import RoutingAgent, train_on_simulated_data, state_from_metrics

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

class RoutingOptimizer:
    """
    Dynamic routing optimizer using reinforcement learning.
    """
    def __init__(self, config_dir='./config', wireguard_mgr=None):
        """
        Initialize the routing optimizer.
        
        Args:
            config_dir: Directory containing configuration files
            wireguard_mgr: WireGuard manager instance (optional)
        """
        self.config_dir = Path(config_dir)
        self.wireguard_mgr = wireguard_mgr
        
        # Create or load network optimizer
        self.network_optimizer = NetworkOptimizer()
        
        # Create or load RL agent
        self.agent = RoutingAgent(model_dir='./models/saved_rl')
        
        # Load WireGuard configuration
        self.wg_config = self._load_wireguard_config()
        
        # Keep track of the current state and actions
        self.current_state = None
        self.current_metrics = None
        self.last_action = None
        self.optimization_history = []
        
    def _load_wireguard_config(self):
        """
        Load WireGuard configuration from JSON file.
        
        Returns:
            dict: WireGuard configuration
        """
        config_file = self.config_dir / 'wireguard_config.json'
        
        try:
            if not config_file.exists():
                logger.warning(f"WireGuard configuration file not found: {config_file}")
                return {
                    'mtu': 1420,
                    'direct_tunnel': True,
                    'prioritize_aws': False
                }
                
            with open(config_file, 'r') as f:
                wg_config = json.load(f)
                
            # Add default values for params if missing
            if 'direct_tunnel' not in wg_config:
                wg_config['direct_tunnel'] = True
                
            if 'prioritize_aws' not in wg_config:
                wg_config['prioritize_aws'] = False
                
            return wg_config
            
        except Exception as e:
            logger.error(f"Error loading WireGuard configuration: {e}")
            return {
                'mtu': 1420,
                'direct_tunnel': True,
                'prioritize_aws': False
            }
            
    def _save_wireguard_config(self):
        """
        Save current WireGuard configuration to JSON file.
        
        Returns:
            bool: True if saved successfully, False otherwise
        """
        config_file = self.config_dir / 'wireguard_config.json'
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(config_file), exist_ok=True)
            
            with open(config_file, 'w') as f:
                json.dump(self.wg_config, f, indent=2)
                
            logger.info(f"WireGuard configuration saved to {config_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving WireGuard configuration: {e}")
            return False
            
    def measure_network_performance(self):
        """
        Measure current network performance metrics.
        
        Returns:
            NetworkMetrics: Measured performance metrics
        """
        # If wireguard_mgr is available, use it to get stats
        if self.wireguard_mgr:
            current_stats = self.wireguard_mgr.get_current_stats()
            
            # Update network parameters based on current stats
            params = NetworkParameters(
                b_local=current_stats.get('download_speed', 1.5) / 1000.0,  # Convert Mbps to Gbps
                b_ec2=1.0,  # Assume 1 Gbps EC2 egress
                l_propagation=current_stats.get('latency', 100.0) * 0.5,  # Approximate propagation latency
                mtu=self.wg_config.get('mtu', 1420),
                buffer_size=1000,  # Default buffer size
                packet_size=min(self.wg_config.get('mtu', 1420) - 20, 1400),  # Adjust packet size based on MTU
                congestion_level=min(current_stats.get('packet_loss', 0.0) / 10.0, 1.0)  # Estimate congestion from packet loss
            )
            
            metrics = self.network_optimizer.calculate_metrics(params)
            logger.info(f"Network metrics from manager: throughput={metrics.effective_throughput*1000:.2f}Mbps, "
                        f"latency={metrics.total_latency:.2f}ms, loss={metrics.packet_loss*100:.2f}%")
            
            return metrics
        
        # Otherwise, measure directly
        try:
            logger.info("Measuring network performance directly...")
            
            # Measure latency and packet loss with ping
            latency, packet_loss = self._measure_latency()
            
            # Measure throughput with iperf3 if available, otherwise estimate
            download_mbps, upload_mbps = self._measure_throughput()
            
            # Convert to Gbps for the model
            download_gbps = download_mbps / 1000.0
            upload_gbps = upload_mbps / 1000.0
            
            # Create network parameters
            params = NetworkParameters(
                b_local=download_gbps,
                b_ec2=1.0,  # Assume 1 Gbps EC2 egress
                l_propagation=latency * 0.5,  # Approximate propagation latency
                mtu=self.wg_config.get('mtu', 1420),
                buffer_size=1000,  # Default buffer size
                packet_size=min(self.wg_config.get('mtu', 1420) - 20, 1400),  # Adjust packet size based on MTU
                congestion_level=min(packet_loss / 100.0, 1.0)  # Convert packet loss percentage to 0-1 range
            )
            
            # Calculate metrics
            metrics = self.network_optimizer.calculate_metrics(params)
            
            logger.info(f"Measured network metrics: throughput={metrics.effective_throughput*1000:.2f}Mbps, "
                        f"latency={metrics.total_latency:.2f}ms, loss={metrics.packet_loss*100:.2f}%")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error measuring network performance: {e}")
            
            # Return simulated metrics based on default parameters
            params = NetworkParameters()
            metrics = self.network_optimizer.calculate_metrics(params)
            
            logger.warning(f"Using simulated metrics: throughput={metrics.effective_throughput*1000:.2f}Mbps, "
                          f"latency={metrics.total_latency:.2f}ms, loss={metrics.packet_loss*100:.2f}%")
            
            return metrics
            
    def _measure_latency(self):
        """
        Measure latency and packet loss using ping.
        
        Returns:
            tuple: (latency_ms, packet_loss_percent)
        """
        try:
            # Target to ping (Google DNS)
            target = "8.8.8.8"
            count = 10
            
            # Run ping command
            cmd = ["ping", "-c", str(count), target]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                logger.warning(f"Ping command failed: {result.stderr}")
                return 100.0, 5.0  # Default values
                
            output = result.stdout
            
            # Extract packet loss
            loss_match = None
            if sys.platform == 'win32':  # Windows
                loss_match = re.search(r'(\d+)% loss', output)
            else:  # Linux/Mac
                loss_match = re.search(r'(\d+)% packet loss', output)
                
            packet_loss = float(loss_match.group(1)) if loss_match else 0.0
            
            # Extract average latency
            latency_match = None
            if sys.platform == 'win32':  # Windows
                latency_match = re.search(r'Average = (\d+)ms', output)
            else:  # Linux/Mac
                latency_match = re.search(r'min/avg/max/.+ = [\d.]+/([\d.]+)/', output)
                
            latency = float(latency_match.group(1)) if latency_match else 0.0
            
            logger.debug(f"Measured latency: {latency}ms, packet loss: {packet_loss}%")
            return latency, packet_loss
            
        except Exception as e:
            logger.error(f"Error measuring latency: {e}")
            return 100.0, 5.0  # Default values
            
    def _measure_throughput(self):
        """
        Measure throughput using iperf3 if available.
        
        Returns:
            tuple: (download_mbps, upload_mbps)
        """
        try:
            # Check if iperf3 is available
            result = subprocess.run(["which", "iperf3"], capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.warning("iperf3 not available, using simulated throughput")
                return 1.5, 0.75  # Default values (1.5 Mbps down, 0.75 Mbps up)
                
            # Run iperf3 test to a public server
            # Try multiple servers in case some are down
            servers = [
                "iperf.he.net",
                "bouygues.iperf.fr",
                "ping.online.net"
            ]
            
            download_mbps = 0
            upload_mbps = 0
            success = False
            
            for server in servers:
                try:
                    logger.info(f"Testing throughput with server: {server}")
                    
                    # Download test
                    cmd = ["iperf3", "-c", server, "-t", "5", "-R"]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    
                    if result.returncode == 0 and "receiver" in result.stdout:
                        # Parse output
                        lines = result.stdout.strip().split('\n')
                        for line in lines:
                            if "receiver" in line:
                                # Extract Mbps
                                parts = line.split()
                                for i, part in enumerate(parts):
                                    if part == "Mbits/sec":
                                        download_mbps = float(parts[i-1])
                                        break
                    
                    # Upload test
                    cmd = ["iperf3", "-c", server, "-t", "5"]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    
                    if result.returncode == 0 and "sender" in result.stdout:
                        # Parse output
                        lines = result.stdout.strip().split('\n')
                        for line in lines:
                            if "sender" in line:
                                # Extract Mbps
                                parts = line.split()
                                for i, part in enumerate(parts):
                                    if part == "Mbits/sec":
                                        upload_mbps = float(parts[i-1])
                                        break
                    
                    if download_mbps > 0 and upload_mbps > 0:
                        success = True
                        break
                        
                except Exception as e:
                    logger.warning(f"Error testing with server {server}: {e}")
                    continue
            
            if not success:
                logger.warning("All iperf3 servers failed, using simulated throughput")
                return 1.5, 0.75  # Default values
                
            logger.debug(f"Measured throughput: {download_mbps} Mbps down, {upload_mbps} Mbps up")
            return download_mbps, upload_mbps
            
        except Exception as e:
            logger.error(f"Error measuring throughput: {e}")
            return 1.5, 0.75  # Default values
            
    def optimize_routing(self, explore=True):
        """
        Use reinforcement learning to optimize routing parameters.
        
        Args:
            explore: Whether to explore new actions or exploit known good ones
            
        Returns:
            dict: Applied routing parameters
        """
        logger.info("Optimizing routing parameters...")
        
        # Measure current network performance
        self.current_metrics = self.measure_network_performance()
        
        # Convert to state vector for RL agent
        self.current_state = state_from_metrics(self.current_metrics)
        
        # Choose action using RL agent
        action = self.agent.choose_action(self.current_state, explore=explore)
        self.last_action = action
        
        # Apply the action to the current parameters
        param_dict = {
            'mtu': self.wg_config.get('mtu', 1420),
            'direct_tunnel': self.wg_config.get('direct_tunnel', True),
            'prioritize_aws': self.wg_config.get('prioritize_aws', False)
        }
        
        new_param_dict = self.agent.apply_action(action, param_dict)
        
        # Update the WireGuard configuration
        self.wg_config.update(new_param_dict)
        self._save_wireguard_config()
        
        # Apply changes to the actual WireGuard configuration if manager is available
        if self.wireguard_mgr:
            logger.info("Applying routing changes to WireGuard configuration...")
            
            # Create config update
            config_update = {
                'mtu': new_param_dict['mtu'],
                'direct_tunnel': new_param_dict['direct_tunnel']
            }
            
            # Apply update
            result = self.wireguard_mgr.update_config(config_update)
            
            if not result.get('success', False):
                logger.error(f"Failed to update WireGuard configuration: {result.get('error', 'Unknown error')}")
        else:
            logger.info("WireGuard manager not available, configuration changes not applied")
            
        # Record optimization step
        self.optimization_history.append({
            'timestamp': datetime.now().isoformat(),
            'state': self.current_state,
            'action': action,
            'action_name': self.agent.actions[action]['name'],
            'metrics': {
                'throughput_mbps': self.current_metrics.effective_throughput * 1000,
                'latency_ms': self.current_metrics.total_latency,
                'packet_loss_percent': self.current_metrics.packet_loss * 100
            },
            'parameters': new_param_dict
        })
        
        logger.info(f"Applied action: {self.agent.actions[action]['name']} - {self.agent.actions[action]['description']}")
        logger.info(f"New parameters: MTU={new_param_dict['mtu']}, "
                   f"Direct tunnel={new_param_dict['direct_tunnel']}, "
                   f"Prioritize AWS={new_param_dict['prioritize_aws']}")
        
        return new_param_dict
        
    def train_agent(self, episodes=100):
        """
        Train the RL agent on simulated network data.
        
        Args:
            episodes: Number of episodes to train for
            
        Returns:
            RoutingAgent: Trained agent
        """
        logger.info(f"Training RL agent on {episodes} episodes...")
        
        # Use the train_on_simulated_data function from reinforcement_learning module
        train_on_simulated_data(self.agent, episodes=episodes)
        
        # Save the trained model
        self.agent.save()
        
        return self.agent
        
    def evaluate_agent(self, steps=10):
        """
        Evaluate the RL agent's performance on real network conditions.
        
        Args:
            steps: Number of optimization steps to evaluate
            
        Returns:
            dict: Evaluation results
        """
        logger.info(f"Evaluating RL agent over {steps} steps...")
        
        # Clear previous optimization history
        self.optimization_history = []
        
        # Run optimization steps
        for step in range(steps):
            logger.info(f"Optimization step {step+1}/{steps}")
            
            # Optimize routing
            self.optimize_routing(explore=False)
            
            # Wait for changes to take effect
            time.sleep(10)
        
        # Analyze results
        throughput_values = [step['metrics']['throughput_mbps'] for step in self.optimization_history]
        latency_values = [step['metrics']['latency_ms'] for step in self.optimization_history]
        loss_values = [step['metrics']['packet_loss_percent'] for step in self.optimization_history]
        
        # Calculate improvement
        if len(throughput_values) > 1:
            throughput_improvement = (throughput_values[-1] / throughput_values[0] - 1) * 100
            latency_improvement = (1 - latency_values[-1] / latency_values[0]) * 100
            loss_improvement = (1 - loss_values[-1] / loss_values[0]) * 100
        else:
            throughput_improvement = 0
            latency_improvement = 0
            loss_improvement = 0
        
        results = {
            'initial_metrics': {
                'throughput_mbps': throughput_values[0] if throughput_values else 0,
                'latency_ms': latency_values[0] if latency_values else 0,
                'packet_loss_percent': loss_values[0] if loss_values else 0
            },
            'final_metrics': {
                'throughput_mbps': throughput_values[-1] if throughput_values else 0,
                'latency_ms': latency_values[-1] if latency_values else 0,
                'packet_loss_percent': loss_values[-1] if loss_values else 0
            },
            'improvement': {
                'throughput_percent': throughput_improvement,
                'latency_percent': latency_improvement,
                'packet_loss_percent': loss_improvement
            },
            'optimization_history': self.optimization_history
        }
        
        logger.info(f"Evaluation results:")
        logger.info(f"Initial: {results['initial_metrics']['throughput_mbps']:.2f} Mbps, "
                   f"{results['initial_metrics']['latency_ms']:.2f} ms, "
                   f"{results['initial_metrics']['packet_loss_percent']:.2f}%")
        logger.info(f"Final: {results['final_metrics']['throughput_mbps']:.2f} Mbps, "
                   f"{results['final_metrics']['latency_ms']:.2f} ms, "
                   f"{results['final_metrics']['packet_loss_percent']:.2f}%")
        logger.info(f"Improvement: Throughput +{results['improvement']['throughput_percent']:.2f}%, "
                   f"Latency {results['improvement']['latency_percent']:.2f}%, "
                   f"Packet loss {results['improvement']['packet_loss_percent']:.2f}%")
        
        return results
        
    def visualize_results(self, results=None, output_file='./optimization_results.png'):
        """
        Visualize optimization results.
        
        Args:
            results: Evaluation results (or use self.optimization_history)
            output_file: Path to save the visualization
            
        Returns:
            str: Path to the saved visualization
        """
        import matplotlib.pyplot as plt
        
        if not results and not self.optimization_history:
            logger.error("No optimization results to visualize")
            return None
            
        history = results.get('optimization_history', self.optimization_history) if results else self.optimization_history
        
        # Extract metrics over time
        timestamps = [i for i in range(len(history))]
        throughput = [step['metrics']['throughput_mbps'] for step in history]
        latency = [step['metrics']['latency_ms'] for step in history]
        packet_loss = [step['metrics']['packet_loss_percent'] for step in history]
        actions = [step['action_name'] for step in history]
        
        # Create figure with 3 subplots
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 12), sharex=True)
        
        # Plot throughput
        ax1.plot(timestamps, throughput, 'b-', marker='o', linewidth=2)
        for i, action in enumerate(actions):
            ax1.annotate(action, (timestamps[i], throughput[i]), 
                         textcoords="offset points", 
                         xytext=(0,10), 
                         ha='center',
                         fontsize=8,
                         rotation=45)
        ax1.set_ylabel('Throughput (Mbps)')
        ax1.set_title('Network Performance Optimization')
        ax1.grid(True)
        
        # Plot latency
        ax2.plot(timestamps, latency, 'r-', marker='o', linewidth=2)
        ax2.set_ylabel('Latency (ms)')
        ax2.grid(True)
        
        # Plot packet loss
        ax3.plot(timestamps, packet_loss, 'g-', marker='o', linewidth=2)
        ax3.set_xlabel('Optimization Step')
        ax3.set_ylabel('Packet Loss (%)')
        ax3.grid(True)
        
        plt.tight_layout()
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
        
        # Save figure
        plt.savefig(output_file)
        logger.info(f"Visualization saved to {output_file}")
        
        return output_file
        
    def save_results(self, results, output_file='./optimization_results.json'):
        """
        Save optimization results to a JSON file.
        
        Args:
            results: Evaluation results
            output_file: Path to save the results
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
            
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)
                
            logger.info(f"Results saved to {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving results: {e}")
            return False
            
    def recommend_parameters(self):
        """
        Recommend optimal routing parameters based on mathematical model.
        
        Returns:
            dict: Recommended parameters
        """
        logger.info("Generating routing parameter recommendations...")
        
        # Measure current network performance
        current_metrics = self.measure_network_performance()
        
        # Create parameters object
        params = NetworkParameters(
            b_local=current_metrics.effective_throughput,
            b_ec2=1.0,
            l_propagation=current_metrics.total_latency * 0.5,
            mtu=self.wg_config.get('mtu', 1420),
            buffer_size=1000,
            packet_size=min(self.wg_config.get('mtu', 1420) - 20, 1400),
            congestion_level=current_metrics.packet_loss
        )
        
        # Use network optimizer to find optimal parameters
        optimal_params, optimal_metrics = self.network_optimizer.optimize_parameters()
        
        # Generate report
        report = self.network_optimizer.generate_report()
        
        # Convert to more user-friendly recommendations
        recommendations = {
            'mtu': optimal_params.mtu,
            'buffer_size': optimal_params.buffer_size,
            'direct_tunnel': True,  # Recommend direct tunnel for best performance
            'prioritize_aws': True if report['current_metrics']['packet_loss_percent'] > 5 else False,
            'split_tunnel_recommended': False,  # Default to full tunnel
            'expected_improvement': report['improvement'],
            'isp_upgrade_recommendation': report['upgrade_recommendation']['recommendation']
        }
        
        # Recommend split tunnel if latency is high or packet loss is high
        if report['current_metrics']['total_latency_ms'] > 150 or report['current_metrics']['packet_loss_percent'] > 10:
            recommendations['split_tunnel_recommended'] = True
            
        logger.info(f"Recommended parameters: MTU={recommendations['mtu']}, "
                   f"Buffer size={recommendations['buffer_size']}, "
                   f"Direct tunnel={recommendations['direct_tunnel']}, "
                   f"Prioritize AWS={recommendations['prioritize_aws']}")
        
        if recommendations['split_tunnel_recommended']:
            logger.info("Split tunnel is recommended due to high latency or packet loss")
            
        logger.info(f"ISP upgrade recommendation: {recommendations['isp_upgrade_recommendation']}")
        
        return recommendations


def main():
    """Main function to optimize routing."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Optimize routing with reinforcement learning')
    parser.add_argument('--mode', choices=['train', 'optimize', 'evaluate'], default='optimize',
                       help='Operation mode: train the RL agent, optimize routing, or evaluate performance')
    parser.add_argument('--episodes', type=int, default=100,
                       help='Number of episodes for training (train mode only)')
    parser.add_argument('--steps', type=int, default=10,
                       help='Number of steps for evaluation (evaluate mode only)')
    parser.add_argument('--explore', action='store_true',
                       help='Enable exploration in optimization (optimize mode only)')
    parser.add_argument('--visualize', action='store_true',
                       help='Visualize results (evaluate mode only)')
    
    args = parser.parse_args()
    
    # Initialize routing optimizer
    optimizer = RoutingOptimizer()
    
    if args.mode == 'train':
        # Train the RL agent
        optimizer.train_agent(episodes=args.episodes)
        
    elif args.mode == 'optimize':
        # Optimize routing parameters
        optimizer.optimize_routing(explore=args.explore)
        
    elif args.mode == 'evaluate':
        # Evaluate optimization performance
        results = optimizer.evaluate_agent(steps=args.steps)
        
        # Save results
        optimizer.save_results(results)
        
        # Visualize results if requested
        if args.visualize:
            optimizer.visualize_results(results)
            
    # Recommend parameters based on mathematical model
    recommendations = optimizer.recommend_parameters()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())