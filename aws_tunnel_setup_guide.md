# AWS WireGuard VPN Tunnel Setup Guide

## Overview

This guide explains how to set up your WireGuard VPN tunnel for direct connection between your Sri Lanka-based local PC and AWS EC2 instance to maximize internet speed without relying on third-party ISP configuration.

## How It Works

The system creates a direct, encrypted tunnel between your local PC and AWS:

```
Local PC (Sri Lanka) <----WireGuard Tunnel----> AWS EC2 (Global)
```

### Benefits:

1. **Direct Routing**: All internet traffic from your local PC is routed through AWS, bypassing local ISP routing issues
2. **Better Performance**: AWS has superior global network connectivity
3. **Lower Latency**: Direct connection to AWS global network reduces hops
4. **No Third-Party ISP Configuration**: Once set up, the tunnel operates independently

## Setup Process

### 1. AWS EC2 Configuration (One-time setup)

1. Launch an AWS EC2 instance:
   - Recommended: t3.micro or t3.small in a geographically optimal region (Singapore, Tokyo, etc.)
   - Operating System: Ubuntu Server LTS

2. Install WireGuard on your EC2 instance:
   ```bash
   sudo apt update
   sudo apt install wireguard
   ```

3. Generate WireGuard keys on EC2:
   ```bash
   wg genkey | tee /tmp/server_private_key | wg pubkey > /tmp/server_public_key
   ```

4. Configure WireGuard server with IP forwarding (create `/etc/wireguard/wg0.conf`):
   ```
   [Interface]
   PrivateKey = <contents of /tmp/server_private_key>
   Address = 10.0.0.1/24
   ListenPort = 51820
   PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
   PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE

   [Peer]
   # Your local PC will be configured with this key
   PublicKey = <This will be your local public key>
   AllowedIPs = 10.0.0.2/32
   ```

5. Enable IP forwarding:
   ```bash
   echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf
   sudo sysctl -p
   ```

6. Start WireGuard on your AWS server:
   ```bash
   sudo systemctl enable wg-quick@wg0
   sudo systemctl start wg-quick@wg0
   ```

### 2. Local PC Configuration (Using the VPN Tunnel Manager)

1. Open the VPN Tunnel Manager application

2. Navigate to the **Configuration Setup** page 

3. Enter the required AWS information:
   - **AWS Endpoint Address**: Your EC2 public IP and port (example: `13.250.x.x:51820`)
   - **AWS Public Key**: The public key from your AWS server (`/tmp/server_public_key`)

4. Configure local settings:
   - Generate a new keypair using the "Generate" button (or enter an existing key)
   - **Local Tunnel IP**: `10.0.0.2/24` (matches the AWS configuration)
   - **DNS Servers**: `1.1.1.1, 8.8.8.8` (Cloudflare and Google DNS)
   - **Keepalive**: `25` seconds (helps maintain connection)

5. Save the configuration

6. Return to the Dashboard and click "Start Tunnel"

## Direct Connection Implementation

To ensure your system uses the VPN tunnel exclusively without involving your local ISP for routing decisions:

1. Configure the tunnel for "Full Tunnel" mode:
   - This makes all traffic go through the AWS server
   - Set "AllowedIPs" on the client side to `0.0.0.0/0`

2. Ensure proper DNS configuration:
   - Use global DNS servers (`1.1.1.1`, `8.8.8.8`) rather than ISP DNS

3. Optimize latency:
   - Set appropriate MTU settings (usually 1420 for WireGuard)
   - Adjust keepalive intervals based on your connection stability

## Troubleshooting

1. **Connection Issues**:
   - Ensure AWS security groups allow UDP traffic on port 51820
   - Check that your local firewall isn't blocking WireGuard
   - Verify the public keys match on both sides

2. **Performance Problems**:
   - Test different AWS regions to find optimal latency
   - Check EC2 instance type (larger instances may offer better network performance)
   - Monitor bandwidth use to ensure you're not hitting AWS data transfer limits

3. **Tunnel Drops**:
   - Increase the keepalive interval for unstable connections
   - Check for IP conflicts in the tunnel subnet
   - Review AWS EC2 logs for network issues

## Conclusion

This direct tunnel setup eliminates reliance on third-party ISP configuration after initial setup. All routing decisions are handled by the WireGuard protocol, creating a secure, high-performance tunnel directly to AWS's global network.

The VPN Tunnel Manager provides an easy-to-use interface for managing this connection, monitoring performance, and ensuring you get maximum benefit from routing through AWS instead of your local ISP.