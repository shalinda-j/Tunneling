# WireGuard VPN Tunnel Manager

A Python-based WireGuard VPN tunneling solution for routing traffic from a local PC in Sri Lanka through an AWS EC2 instance to maximize internet speed and performance.

![WireGuard VPN Tunnel Manager](static/img/logo.png)

## Overview

This project provides a web-based management interface for setting up and monitoring a WireGuard VPN tunnel between your local PC and an AWS EC2 instance. By routing your internet traffic through AWS's global network, you can achieve better speed, lower latency, and improved reliability compared to standard ISP routing.

### Key Features

- **Easy-to-use web interface** for managing the WireGuard tunnel
- **Direct AWS Tunneling** for optimal internet performance without third-party ISP routing configuration
- **Real-time monitoring** of network statistics (throughput, latency, packet loss)
- **Historical data visualization** to track performance improvements
- **Interactive terminal** for advanced users to run networking commands
- **Automatic tunnel management** with reconnection capabilities

## Installation

### Prerequisites

- Python 3.8 or higher
- WireGuard installed on both local PC and remote AWS server
- An AWS EC2 instance with a public IP address

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/wee-technology-solutions/wireguard-vpn-tunnel-manager.git
   cd wireguard-vpn-tunnel-manager
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python main.py
   ```

4. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

## AWS Server Configuration

See our [AWS Tunnel Setup Guide](aws_tunnel_setup_guide.md) for detailed instructions on setting up your AWS EC2 instance as a WireGuard server.

## Direct Tunneling Configuration

This application supports direct tunneling to AWS without requiring third-party ISP configuration after the initial setup. The implementation:

1. Routes all your traffic through the WireGuard tunnel to AWS
2. Bypasses inefficient local ISP routing decisions
3. Takes advantage of AWS's global network infrastructure
4. Provides significantly improved internet performance

Configure direct tunneling in the application's setup page by enabling "Full Tunnel Mode".

## Upgrading and Contributing

We welcome contributions to improve the WireGuard VPN Tunnel Manager. Here are some potential areas for enhancement:

1. **Multi-server support** - Add ability to manage multiple AWS endpoints and switch between them
2. **Mobile app integration** - Create companion mobile apps for monitoring and control
3. **Automated region selection** - Test and automatically select optimal AWS regions
4. **Network optimization algorithms** - Implement adaptive tuning of WireGuard parameters
5. **Extended monitoring** - Add more detailed network analytics
6. **Bandwidth quotas and alerts** - Track AWS data transfer costs and alert on thresholds
7. **Connection scheduling** - Enable/disable tunnel on specific schedules
8. **Multi-user support** - Allow different configuration profiles for different users
9. **Custom routing rules** - Enhanced control over which traffic goes through the tunnel
10. **Integration with other cloud providers** - Support for Azure, GCP, etc.

Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

- **Shalinda Jayasinghe** - WEE Technology Solutions Ltd.

## Acknowledgments

- The WireGuard project team for their excellent VPN protocol
- The Flask community for the web framework
- All contributors who have helped improve this project