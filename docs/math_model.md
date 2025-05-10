# Mathematical Model for Network Optimization

This document explains the mathematical foundations of the WireGuard VPN Tunnel Manager's optimization algorithms, which combine network flow theory and queueing theory to maximize performance within the constraints of a limited ISP connection.

## Overview

Our mathematical model addresses the key challenge: maximizing effective throughput for AWS traffic from a low-bandwidth connection in Sri Lanka (1.5 Mbps) through an AWS EC2 instance with enhanced networking support (up to 1 Gbps). The model optimizes parameters like MTU, buffer sizes, and routing priorities to achieve near-theoretical maximum performance.

## Variables and Notation

| Symbol | Description | Unit | Typical Range |
|--------|-------------|------|--------------|
| $B_{local}$ | Local ISP bandwidth | Gbps | 0.0015 (1.5 Mbps) |
| $B_{ec2}$ | EC2 instance egress bandwidth | Gbps | 1.0 |
| $L_{tunnel}$ | Tunnel latency | ms | 20-150 |
| $P_{loss}$ | Packet loss probability | - | 0-0.1 (0-10%) |
| $Q_{queue}$ | Queue length at EC2 instance | packets | 0-100 |
| $MTU$ | Maximum Transmission Unit | bytes | 1280-1500 |
| $T_{service}$ | EC2 processing time per packet | ms | 0.01-0.1 |

## Optimization Objective

Our primary optimization objective combines two goals:

1. Maximize effective throughput: $T_{eff} = B_{local} \cdot (1 - P_{loss})$
2. Minimize total latency: $L_{total} = L_{tunnel} + Q_{queue} \cdot T_{service}$

Therefore, our objective function is:

$$\max_{MTU, buffer} \left[ w_1 \cdot T_{eff} - w_2 \cdot L_{total} - w_3 \cdot P_{loss} \right]$$

Where $w_1, w_2, w_3$ are weights for throughput, latency, and packet loss respectively (typically 0.5, 0.3, 0.2).

## Constraints

The optimization is subject to:

1. $B_{local} \leq 0.0015$ Gbps (current ISP limit)
2. $L_{tunnel} \geq 20$ ms (minimum propagation delay between Sri Lanka and Singapore)
3. $P_{loss} \leq 0.01$ (target 1% maximum packet loss)
4. $1280 \leq MTU \leq 1500$ (practical MTU range for Internet tunnels)
5. $100 \leq buffer\_size \leq 2000$ (practical buffer size range)

## Network Flow Theory Component

Network flow theory provides the foundation for modeling how traffic flows through the tunnel. We consider the tunnel as a directed graph with capacity constraints:

1. Source (local PC) is connected to sink (AWS services) through the tunnel
2. Edge capacities are defined by $B_{local}$ and $B_{ec2}$
3. The max-flow problem identifies the theoretical maximum throughput
4. Ford-Fulkerson or Edmonds-Karp algorithms can compute the maximum flow

For our specific case:
- The flow is bottlenecked by $B_{local}$ (1.5 Mbps)
- The theoretical maximum throughput is $B_{local} \cdot (1 - P_{loss})$
- Packet loss $P_{loss}$ is influenced by MTU and congestion

## Queueing Theory Component

We use an M/M/1 queueing model to account for packet processing at the EC2 instance:

1. Packets arrive at rate $\lambda = B_{local} / (MTU \cdot 8 \cdot 10^{-6})$ packets per second
2. EC2 instance services packets at rate $\mu = B_{ec2} / (MTU \cdot 8 \cdot 10^{-6})$ packets per second
3. The utilization factor $\rho = \lambda / \mu$ must be $< 1$ for stability
4. Queue length follows: $Q_{queue} = \rho / (1 - \rho)$
5. Queueing delay is $Q_{queue} / \mu$ seconds

For a 1.5 Mbps connection and 1 Gbps EC2 instance:
- $\lambda \approx 125$ packets/s (with MTU=1500)
- $\mu \approx 83,333$ packets/s (with MTU=1500)
- Resulting in $\rho \approx 0.0015$ and very small queueing delays

## Effect of MTU on Performance

MTU size affects multiple aspects of tunnel performance:

1. **Fragmentation**: Larger MTU can cause fragmentation if it exceeds the path MTU, leading to increased packet loss
2. **Overhead Ratio**: Smaller packets have a higher header-to-payload ratio, decreasing efficiency
3. **Processing Efficiency**: Larger packets reduce per-packet processing overhead

The optimal MTU balances these factors:

$$MTU_{optimal} = \min(path\_MTU, MTU_{efficiency\_optimal})$$

Where $MTU_{efficiency\_optimal}$ is calculated based on throughput and packet loss measurements.

## Packet Loss Model

Packet loss is modeled as a function of:

1. **Network Congestion**: Approximated from latency measurements
2. **Buffer Overflow**: Using M/M/1/K queue model: $P_{loss\_buffer} = \rho^K \cdot (1-\rho)$ for a buffer size $K$
3. **MTU Fragmentation**: Estimated based on effective path MTU

Total packet loss probability:

$$P_{loss} = 1 - (1-P_{loss\_congestion}) \cdot (1-P_{loss\_buffer}) \cdot (1-P_{loss\_fragmentation})$$

## Dynamic Parameter Adjustment

Our system dynamically adjusts parameters based on real-time measurements:

1. **MTU Adjustment**:
   - If $P_{loss} > 0.05$: Decrease MTU by 40 bytes
   - If $P_{loss} < 0.01$ and $L_{tunnel} < 100$: Increase MTU by 20 bytes

2. **Buffer Size Adjustment**:
   - If $L_{tunnel} > 100$: Decrease buffer size
   - If $P_{loss} > 0.01$ and $L_{tunnel} < 50$: Increase buffer size

## Reinforcement Learning Enhancement

The mathematical model is complemented by a reinforcement learning (RL) agent that learns optimal policy through experience:

1. **State**: $[throughput, latency, packet\_loss]$
2. **Actions**: Adjust MTU, toggle split tunneling, prioritize AWS IPs
3. **Reward**: $R = w_1 \cdot T_{eff} - w_2 \cdot L_{tunnel} - w_3 \cdot P_{loss}$

The RL agent can adapt to network conditions beyond what the analytical model can represent, particularly for non-linear relationships and temporal patterns in network behavior.

## ISP Upgrade Analysis

The model is also used to project performance with upgraded infrastructure:

$$T_{eff\_projected} = B_{local\_new} \cdot (1 - P_{loss\_new})$$

Where $P_{loss\_new}$ is recalculated based on the new bandwidth $B_{local\_new}$.

For example, upgrading to 100 Mbps fiber could yield:
- $B_{local\_new} = 0.1$ Gbps
- $P_{loss\_new} \approx 0.001$ (due to reduced congestion)
- $T_{eff\_projected} \approx 0.1 \cdot 0.999 = 0.0999$ Gbps = 99.9 Mbps

This represents a 66x improvement over the 1.5 Mbps connection.

## Implementation Details

The mathematical model is implemented in Python using:

1. NumPy for numerical operations
2. SciPy for optimization algorithms
3. TensorFlow for the reinforcement learning component

Key files:
- `models/network_optimization.py`: Contains the core mathematical model implementation
- `models/reinforcement_learning.py`: Implements the RL enhancement
- `scripts/optimize_routing.py`: Uses the model for dynamic routing optimization

## Limitations and Future Work

The current model has some limitations:

1. Assumes steady-state network conditions
2. Simplified congestion modeling
3. Limited validation with real-world Sri Lanka to Singapore connections

Future work could:
1. Incorporate more complex TCP congestion control models
2. Add time-series forecasting for anticipatory optimization
3. Validate with more extensive real-world measurements
4. Extend the model to multi-path routing strategies