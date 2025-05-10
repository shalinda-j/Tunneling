"""
Mathematical model for optimizing network performance in the WireGuard VPN tunnel.

This module implements a combination of network flow theory (to maximize throughput) 
and M/M/1 queueing theory (to minimize latency and packet loss) for optimizing 
the VPN tunnel parameters.

Variables:
- B_local: Local ISP bandwidth (1.5 Mbps = 0.0015 Gbps)
- B_ec2: EC2 instance egress bandwidth (up to 1 Gbps with enhanced networking)
- L_tunnel: Tunnel latency (ms), including propagation and processing delays
- P_loss: Packet loss probability
- Q_queue: Queue length at the EC2 instance for forwarded traffic

Objective: 
- Maximize effective throughput T_eff = B_local * (1 - P_loss)
- Minimize latency L_tunnel + Q_queue * T_service

Constraints:
- B_local <= 0.0015 Gbps (current ISP)
- L_tunnel >= 20 ms (Sri Lanka to Singapore)
- P_loss <= 0.01 (target 1% max loss)
"""

import logging
import numpy as np
import math
from dataclasses import dataclass
from typing import Dict, Tuple, List, Optional

logger = logging.getLogger(__name__)

@dataclass
class NetworkParameters:
    """Parameters describing the network conditions"""
    b_local: float = 0.0015  # Local ISP bandwidth in Gbps (1.5 Mbps)
    b_ec2: float = 1.0       # EC2 egress bandwidth in Gbps
    l_propagation: float = 20.0  # Base propagation latency in ms (Sri Lanka to Singapore)
    mtu: int = 1420          # Maximum Transmission Unit in bytes
    buffer_size: int = 1000  # Buffer size in packets
    packet_size: int = 1400  # Average packet size in bytes
    congestion_level: float = 0.0  # Network congestion level (0.0-1.0)

@dataclass
class NetworkMetrics:
    """Calculated network performance metrics"""
    effective_throughput: float = 0.0  # Effective throughput in Gbps
    total_latency: float = 0.0         # Total latency in ms
    packet_loss: float = 0.0           # Packet loss probability (0.0-1.0)
    queue_length: float = 0.0          # Queue length in packets
    utilization: float = 0.0           # Link utilization (0.0-1.0)
    score: float = 0.0                 # Overall performance score


class NetworkOptimizer:
    """
    Implements the mathematical model combining network flow theory and
    queueing theory for optimal VPN tunnel parameter selection.
    """
    def __init__(self, initial_params: Optional[NetworkParameters] = None):
        """
        Initialize the network optimizer with parameters.
        
        Args:
            initial_params: Initial network parameters
        """
        self.params = initial_params if initial_params else NetworkParameters()
        self.weights = {
            'throughput': 0.5,  # Weight for throughput in the optimization score
            'latency': 0.3,     # Weight for latency in the optimization score
            'loss': 0.2         # Weight for packet loss in the optimization score
        }
        
        # Constraints
        self.constraints = {
            'max_packet_loss': 0.01,  # Maximum acceptable packet loss (1%)
            'min_throughput': 0.0005, # Minimum acceptable throughput in Gbps (0.5 Mbps)
            'max_latency': 150.0      # Maximum acceptable latency in ms
        }
        
        # Record of evaluated configurations
        self.evaluated_configs: List[Tuple[NetworkParameters, NetworkMetrics]] = []

    def calculate_metrics(self, params: NetworkParameters) -> NetworkMetrics:
        """
        Calculate network performance metrics based on the given parameters.
        
        Args:
            params: Network parameters to evaluate
            
        Returns:
            NetworkMetrics: Calculated performance metrics
        """
        # Convert bandwidth from Gbps to packets per second
        packet_size_bits = params.packet_size * 8
        
        # Arrival rate (λ) in packets per second
        arrival_rate = (params.b_local * 1e9) / packet_size_bits
        
        # Service rate (μ) in packets per second
        service_rate = (params.b_ec2 * 1e9) / packet_size_bits
        
        # M/M/1 Queue calculations
        utilization = arrival_rate / service_rate
        
        # Ensure utilization is < 1 for stability
        if utilization >= 1.0:
            utilization = 0.99  # Cap at high value to avoid infinity
            
        # Calculate queue length using M/M/1 formula: ρ / (1 - ρ)
        queue_length = utilization / (1 - utilization)
        
        # Calculate queueing delay (ms)
        service_time_ms = 1000.0 / service_rate  # Convert seconds to ms
        queueing_delay = queue_length * service_time_ms
        
        # Calculate processing delay (network header processing)
        processing_delay = 1.0  # Assume 1ms for processing overhead
        
        # Calculate transmission delay (time to put packet on the link)
        transmission_delay = (params.mtu * 8) / (params.b_local * 1e9) * 1000  # Convert to ms
        
        # Total latency = propagation + queueing + processing + transmission
        total_latency = params.l_propagation + queueing_delay + processing_delay + transmission_delay
        
        # Calculate packet loss probability based on congestion level and buffer size
        # Using a modified form of the buffer overflow probability in M/M/1/K queue
        # P_loss = ρ^K (for a buffer of size K)
        effective_buffer = params.buffer_size * (1 - params.congestion_level)
        
        # Avoid division by zero if buffer is full
        if effective_buffer <= 0:
            packet_loss = 1.0
        else:
            if utilization < 1.0:
                packet_loss = (utilization ** effective_buffer) * (1 - utilization)
            else:
                packet_loss = 0.5  # High congestion, significant packet loss
                
        # Add effect of network congestion to packet loss
        packet_loss = packet_loss + (params.congestion_level ** 2) * 0.1
        packet_loss = min(packet_loss, 1.0)  # Cap at 100%
        
        # Calculate effective throughput (considering packet loss)
        effective_throughput = params.b_local * (1 - packet_loss)
        
        # Calculate overall performance score
        # Higher throughput is better, lower latency and packet loss are better
        throughput_score = min(effective_throughput / 0.0015, 1.0)  # Normalized to 1.5 Mbps
        latency_score = max(0, 1 - (total_latency / 150.0))  # Normalized to 150ms
        loss_score = 1 - (packet_loss / 0.01)  # Normalized to 1% target
        
        # Combined weighted score (0.0-1.0)
        score = (
            self.weights['throughput'] * throughput_score +
            self.weights['latency'] * latency_score +
            self.weights['loss'] * loss_score
        )
        
        # Clip values to valid ranges
        packet_loss = min(max(packet_loss, 0.0), 1.0)
        total_latency = max(total_latency, params.l_propagation)
        effective_throughput = min(max(effective_throughput, 0.0), params.b_local)
        
        return NetworkMetrics(
            effective_throughput=effective_throughput,
            total_latency=total_latency,
            packet_loss=packet_loss,
            queue_length=queue_length,
            utilization=utilization,
            score=score
        )

    def optimize_parameters(self) -> Tuple[NetworkParameters, NetworkMetrics]:
        """
        Find optimal network parameters to maximize performance.
        
        Uses a simple grid search to evaluate different parameter combinations
        and find the best configuration.
        
        Returns:
            Tuple[NetworkParameters, NetworkMetrics]: Optimal parameters and resulting metrics
        """
        # Define parameter ranges to search
        mtu_values = [1280, 1380, 1420, 1480]
        buffer_sizes = [100, 500, 1000, 1500, 2000]
        
        best_score = -1
        best_params = None
        best_metrics = None
        
        # Grid search for optimal parameters
        for mtu in mtu_values:
            for buffer_size in buffer_sizes:
                test_params = NetworkParameters(
                    b_local=self.params.b_local,
                    b_ec2=self.params.b_ec2,
                    l_propagation=self.params.l_propagation,
                    mtu=mtu,
                    buffer_size=buffer_size,
                    packet_size=min(mtu - 20, 1400),  # Adjust packet size based on MTU
                    congestion_level=self.params.congestion_level
                )
                
                metrics = self.calculate_metrics(test_params)
                self.evaluated_configs.append((test_params, metrics))
                
                # Check if this is the best configuration so far
                if metrics.score > best_score:
                    best_score = metrics.score
                    best_params = test_params
                    best_metrics = metrics
                    
                    logger.debug(f"New best configuration: MTU={mtu}, Buffer={buffer_size}, "
                                f"Score={metrics.score:.4f}, Throughput={metrics.effective_throughput*1000:.2f}Mbps, "
                                f"Latency={metrics.total_latency:.2f}ms, Loss={metrics.packet_loss*100:.2f}%")
        
        if best_params is None:
            # Default to current parameters if no better solution found
            best_params = self.params
            best_metrics = self.calculate_metrics(self.params)
        
        return best_params, best_metrics
    
    def recommend_isp_upgrade(self, current_metrics: NetworkMetrics) -> Dict[str, any]:
        """
        Recommend if an ISP upgrade would be beneficial based on current metrics.
        
        Args:
            current_metrics: Current network performance metrics
            
        Returns:
            Dict with upgrade recommendation and justification
        """
        # Simulate performance with different ISP bandwidth options
        upgrade_options = [
            ("50Mbps Fiber", 0.05),  # 50 Mbps
            ("100Mbps Fiber", 0.1),  # 100 Mbps
            ("Starlink", 0.15)       # 150 Mbps
        ]
        
        recommendations = []
        
        for name, bandwidth in upgrade_options:
            # Create parameters with upgraded bandwidth
            upgrade_params = NetworkParameters(
                b_local=bandwidth,
                b_ec2=self.params.b_ec2,
                l_propagation=self.params.l_propagation,
                mtu=self.params.mtu,
                buffer_size=self.params.buffer_size,
                packet_size=self.params.packet_size,
                congestion_level=self.params.congestion_level
            )
            
            # Calculate potential metrics
            upgrade_metrics = self.calculate_metrics(upgrade_params)
            
            # Calculate improvement factor
            throughput_improvement = upgrade_metrics.effective_throughput / current_metrics.effective_throughput
            latency_improvement = current_metrics.total_latency / upgrade_metrics.total_latency
            
            recommendations.append({
                "name": name,
                "bandwidth_gbps": bandwidth,
                "bandwidth_mbps": bandwidth * 1000,
                "effective_throughput_mbps": upgrade_metrics.effective_throughput * 1000,
                "latency_ms": upgrade_metrics.total_latency,
                "packet_loss_percent": upgrade_metrics.packet_loss * 100,
                "throughput_improvement_factor": throughput_improvement,
                "latency_improvement_factor": latency_improvement,
                "score": upgrade_metrics.score
            })
        
        # Sort recommendations by score
        recommendations.sort(key=lambda x: x["score"], reverse=True)
        
        # Generate recommendation text
        current_throughput_mbps = current_metrics.effective_throughput * 1000
        best_option = recommendations[0]
        
        result = {
            "should_upgrade": best_option["throughput_improvement_factor"] > 5,  # Significant improvement
            "current_throughput_mbps": current_throughput_mbps,
            "best_option": best_option,
            "all_options": recommendations,
            "recommendation": f"Current throughput: {current_throughput_mbps:.2f} Mbps. "
                             f"Recommended upgrade: {best_option['name']} with "
                             f"{best_option['bandwidth_mbps']:.0f} Mbps would provide "
                             f"{best_option['throughput_improvement_factor']:.1f}x throughput improvement "
                             f"and {best_option['latency_improvement_factor']:.1f}x latency improvement."
        }
        
        return result

    def adaptive_mtu_adjustment(self, recent_metrics: List[NetworkMetrics]) -> int:
        """
        Dynamically adjust MTU based on recent network performance metrics.
        
        Args:
            recent_metrics: List of recent network performance metrics
            
        Returns:
            Recommended MTU value
        """
        if not recent_metrics:
            return self.params.mtu
        
        # Get average packet loss and latency from recent metrics
        avg_packet_loss = sum(m.packet_loss for m in recent_metrics) / len(recent_metrics)
        avg_latency = sum(m.total_latency for m in recent_metrics) / len(recent_metrics)
        
        current_mtu = self.params.mtu
        
        # Adjust MTU based on performance
        if avg_packet_loss > 0.05:  # More than 5% packet loss
            # Reduce MTU to reduce packet loss from fragmentation
            new_mtu = max(current_mtu - 40, 1280)
            logger.info(f"High packet loss ({avg_packet_loss*100:.2f}%), reducing MTU: {current_mtu} -> {new_mtu}")
            return new_mtu
            
        elif avg_packet_loss < 0.01 and avg_latency < 100:
            # Low packet loss and latency, try slightly larger MTU
            new_mtu = min(current_mtu + 20, 1500)
            logger.info(f"Good network conditions, increasing MTU: {current_mtu} -> {new_mtu}")
            return new_mtu
            
        # Otherwise keep current MTU
        return current_mtu

    def generate_report(self) -> Dict[str, any]:
        """
        Generate a comprehensive report of network optimization results.
        
        Returns:
            Dict containing optimization results and recommendations
        """
        # Calculate metrics for current parameters
        current_metrics = self.calculate_metrics(self.params)
        
        # Find optimal parameters
        optimal_params, optimal_metrics = self.optimize_parameters()
        
        # Generate ISP upgrade recommendation
        upgrade_recommendation = self.recommend_isp_upgrade(current_metrics)
        
        # Put together the complete report
        report = {
            "current_parameters": {
                "local_bandwidth_mbps": self.params.b_local * 1000,
                "ec2_bandwidth_mbps": self.params.b_ec2 * 1000,
                "propagation_latency_ms": self.params.l_propagation,
                "mtu": self.params.mtu,
                "buffer_size": self.params.buffer_size,
                "packet_size": self.params.packet_size,
                "congestion_level": self.params.congestion_level
            },
            "current_metrics": {
                "effective_throughput_mbps": current_metrics.effective_throughput * 1000,
                "total_latency_ms": current_metrics.total_latency,
                "packet_loss_percent": current_metrics.packet_loss * 100,
                "queue_length": current_metrics.queue_length,
                "utilization": current_metrics.utilization,
                "performance_score": current_metrics.score
            },
            "optimal_parameters": {
                "mtu": optimal_params.mtu,
                "buffer_size": optimal_params.buffer_size,
                "packet_size": optimal_params.packet_size
            },
            "optimal_metrics": {
                "effective_throughput_mbps": optimal_metrics.effective_throughput * 1000,
                "total_latency_ms": optimal_metrics.total_latency,
                "packet_loss_percent": optimal_metrics.packet_loss * 100,
                "queue_length": optimal_metrics.queue_length,
                "utilization": optimal_metrics.utilization,
                "performance_score": optimal_metrics.score
            },
            "improvement": {
                "throughput_improvement_percent": 
                    (optimal_metrics.effective_throughput / current_metrics.effective_throughput - 1) * 100,
                "latency_improvement_percent":
                    (1 - optimal_metrics.total_latency / current_metrics.total_latency) * 100,
                "packet_loss_improvement_percent":
                    (1 - optimal_metrics.packet_loss / current_metrics.packet_loss) * 100,
                "score_improvement_percent":
                    (optimal_metrics.score / current_metrics.score - 1) * 100
            },
            "upgrade_recommendation": upgrade_recommendation,
            "conclusion": f"Optimal settings (MTU={optimal_params.mtu}, Buffer={optimal_params.buffer_size}) "
                         f"can improve throughput by "
                         f"{(optimal_metrics.effective_throughput / current_metrics.effective_throughput - 1) * 100:.1f}% "
                         f"and reduce latency by "
                         f"{(1 - optimal_metrics.total_latency / current_metrics.total_latency) * 100:.1f}%."
        }
        
        return report


def update_network_params(current_stats: Dict[str, any], optimizer: NetworkOptimizer) -> NetworkParameters:
    """
    Update network parameters based on current statistics.
    
    Args:
        current_stats: Current network statistics from monitoring
        optimizer: The network optimizer instance
        
    Returns:
        Updated network parameters
    """
    # Extract relevant metrics from current stats
    download_mbps = current_stats.get('download_speed', 1.5)
    upload_mbps = current_stats.get('upload_speed', 0.75)
    latency_ms = current_stats.get('latency', 100.0)
    packet_loss = current_stats.get('packet_loss', 1.0) / 100.0  # Convert from percentage
    
    # Estimate congestion level based on latency and packet loss
    # Higher latency and packet loss indicate higher congestion
    normalized_latency = min(latency_ms / 200.0, 1.0)  # Normalize to 0-1 range with 200ms as max
    normalized_loss = min(packet_loss / 0.1, 1.0)      # Normalize to 0-1 range with 10% as max
    congestion_level = (normalized_latency + normalized_loss) / 2
    
    # Update network parameters
    params = NetworkParameters(
        b_local=max(download_mbps, 0.1) / 1000.0,  # Convert Mbps to Gbps with minimum
        b_ec2=1.0,  # Assume 1 Gbps EC2 egress
        l_propagation=max(latency_ms * 0.5, 20.0),  # Estimate propagation latency (at least 20ms)
        mtu=optimizer.params.mtu,  # Keep current MTU
        buffer_size=optimizer.params.buffer_size,  # Keep current buffer size
        packet_size=min(optimizer.params.mtu - 20, 1400),  # Adjust packet size based on MTU
        congestion_level=congestion_level
    )
    
    return params