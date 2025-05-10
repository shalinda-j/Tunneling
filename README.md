# High-Reliability VPN Tunnel Manager with ML Optimization

An advanced Python-based WireGuard VPN tunneling solution for routing traffic from a local PC in Sri Lanka through an AWS EC2 instance to maximize internet speed and reliability. Utilizing mathematical modeling and reinforcement learning to achieve optimal performance.

![WireGuard VPN Tunnel Manager](static/img/logo.png)

## Overview

This project provides a comprehensive solution for optimizing network performance between Sri Lanka and AWS through an intelligently managed WireGuard VPN tunnel. The system combines cutting-edge technologies:

1. **Mathematical optimization** based on network flow and queueing theory
2. **Reinforcement learning** for dynamic routing decisions
3. **AWS EC2 enhanced networking** infrastructure 
4. **WireGuard VPN** for secure, high-performance tunneling

The result is a solution that maximizes effective throughput, minimizes latency, and dramatically improves reliability for AWS-specific traffic, even with a constrained ISP connection (1.5 Mbps).

### Key Features

- **Mathematical optimization model** balancing throughput, latency, and packet loss
- **Reinforcement learning agent** that dynamically adapts routing parameters
- **Easy-to-use web interface** for managing the WireGuard tunnel
- **Comprehensive monitoring** with real-time and historical metrics
- **AWS EC2 setup automation** with boto3
- **WireGuard configuration optimization** for maximum performance
- **Dynamic MTU and buffer size adjustment** based on network conditions
- **Scalable design** that can accommodate future ISP upgrades (e.g., 100Mbps fiber)
- **High reliability** with built-in failover mechanisms

## Technical Foundations

The project is built on advanced technical foundations:

### 1. Mathematical Model

The system implements a sophisticated mathematical model that combines:
- **Network flow theory** to maximize throughput
- **M/M/1 queueing theory** to minimize latency and packet loss
- **Optimization algorithms** to balance competing objectives

See [docs/math_model.md](docs/math_model.md) for detailed mathematical documentation.

### 2. Reinforcement Learning

A TensorFlow-based reinforcement learning agent dynamically optimizes routing:
- **State**: Current throughput, latency, packet loss
- **Actions**: Adjust MTU, enable/disable split tunneling, prioritize AWS IPs
- **Reward**: Weighted combination of throughput, latency, and packet loss factors

### 3. AWS EC2 with Enhanced Networking

The system leverages AWS EC2 instances with enhanced networking capabilities:
- **c5n.large** instance type with up to 25 Gbps intra-AWS networking
- **Jumbo frames** support (MTU 9001) for efficient data transfer
- **Elastic IP** for static addressing

## Installation and Setup

### Prerequisites

- Python 3.8 or higher
- AWS account with API access
- SSH key pair for EC2 access

### Complete Automated Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/advanced-vpn-tunnel-manager/wireguard-vpn-tunnel-manager.git
   cd wireguard-vpn-tunnel-manager
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables for AWS access (in .env file):
   ```
   AWS_ACCESS_KEY_ID=your_access_key
   AWS_SECRET_ACCESS_KEY=your_secret_key
   AWS_KEY_NAME=your_ec2_key_name
   AWS_KEY_PATH=/path/to/your/key.pem
   ```

4. Run the complete setup process:
   ```bash
   python main.py setup-all
   ```
   This will:
   - Launch a suitably configured EC2 instance in ap-southeast-1 (Singapore)
   - Configure WireGuard on the EC2 instance
   - Generate optimal configuration parameters
   - Train the reinforcement learning model

5. Set up the local client:
   ```bash
   sudo python main.py setup-client
   ```

6. Start the web interface:
   ```bash
   python main.py web
   ```

7. Access the dashboard at:
   ```
   http://localhost:5000
   ```

## Command-Line Interface

The application provides a comprehensive CLI for all operations:

```
Usage: python main.py [command] [options]

Commands:
  web                 Start the web interface
  setup-ec2           Set up AWS EC2 instance
  setup-wireguard     Configure WireGuard on the EC2 instance
  optimize            Optimize routing with reinforcement learning
  monitor             Monitor tunnel performance
  setup-client        Set up local client
  test                Run tests
  setup-all           Run complete setup (EC2, WireGuard, optimization)

Examples:
  python main.py web --port=8080
  python main.py optimize --mode=train --steps=200
  python main.py monitor --interval=30
  python main.py setup-client --mode=aws
```

See `python main.py --help` for detailed information on each command.

## Performance Optimization

The system includes several optimization components:

### 1. Automatic Parameter Tuning

The system automatically adjusts key parameters:
- **MTU** optimization to avoid fragmentation (typically 1280-1420 bytes)
- **Buffer sizes** to balance throughput and latency
- **Routing priorities** to ensure AWS traffic takes optimal paths

### 2. Tunnel Monitoring and Alerts

The monitoring system:
- Tracks throughput, latency, and packet loss in real-time
- Logs metrics for historical analysis
- Sends alerts if tunnel uptime drops below 99.9%
- Provides visualizations of performance trends

### 3. Reliability Mechanisms

Built-in reliability features include:
- Automatic reconnection if the tunnel drops
- Persistent keepalives to maintain NAT connections
- Redundancy options including multi-region fallback

## Constraints and Scalability

The system acknowledges and addresses real-world constraints:

1. **ISP Bandwidth Limitation**:
   - Current implementation optimizes for 1.5 Mbps ISP connection
   - Effective throughput is maximized within this constraint

2. **Scalability**:
   - The mathematical model and RL agent automatically adapt to higher bandwidth
   - Configuration is parametrized for easy upgrades
   - Projections for 100 Mbps fiber and Starlink upgrades are included

3. **Cost Considerations**:
   - EC2 cost estimates (c5n.large ~$75/month, data transfer ~$90/TB)
   - Optimization to minimize AWS data transfer costs

## Documentation

- [docs/math_model.md](docs/math_model.md) - Detailed mathematical model documentation
- [docs/troubleshoot.md](docs/troubleshoot.md) - Troubleshooting guide for common issues
- [aws_tunnel_setup_guide.md](aws_tunnel_setup_guide.md) - Manual AWS setup guide

## Testing

The application includes a comprehensive testing suite:

```bash
python main.py test
```

This runs tests for:
- Tunnel connectivity
- AWS service access
- Throughput (target 1-2 Mbps with 1.5 Mbps ISP)
- Reliability (simulate 100 connections with <1% failure rate)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- The WireGuard project team for their excellent VPN protocol
- TensorFlow and the ML community for reinforcement learning tools
- The AWS team for providing enhanced networking infrastructure
- The networking research community for queueing theory and network flow optimization models