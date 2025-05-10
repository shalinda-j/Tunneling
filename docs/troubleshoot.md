# Troubleshooting Guide for WireGuard VPN Tunnel Manager

This guide provides solutions to common issues you might encounter with the WireGuard VPN Tunnel Manager. Follow these steps to diagnose and resolve problems with your tunnel connection, performance, or reliability.

## Connection Issues

### Tunnel Fails to Start

**Symptoms**: WireGuard interface doesn't appear when running `wg show`, error message when starting the tunnel, or the "Start Tunnel" button in UI doesn't work.

**Solutions**:

1. **Check if WireGuard is installed**:
   ```bash
   which wg
   ```
   If not found, install WireGuard:
   ```bash
   sudo apt install wireguard wireguard-tools
   ```

2. **Check for configuration errors**:
   ```bash
   sudo wg-quick up wg0
   ```
   Look for specific error messages.

3. **Check EC2 instance status**:
   - Ensure your AWS EC2 instance is running
   - Verify the EC2 instance's public IP matches the endpoint in your configuration

4. **Verify security group settings**:
   - Ensure UDP port 51820 is open in the EC2 security group
   - Check that your local firewall isn't blocking outbound UDP 51820

5. **Check for permission issues**:
   ```bash
   sudo chmod 600 /etc/wireguard/wg0.conf
   ```

6. **Verify key configuration**:
   - Ensure the private key in your local config matches the public key on the server
   - Generate new keypairs if necessary using:
   ```bash
   python main.py optimize --mode=train
   ```

### Tunnel Connects but No Internet Access

**Symptoms**: WireGuard shows as connected, but you can't access the internet or AWS services.

**Solutions**:

1. **Check IP forwarding on the EC2 instance**:
   ```bash
   ssh ubuntu@<your-ec2-ip>
   sudo sysctl net.ipv4.ip_forward
   ```
   Should return `net.ipv4.ip_forward = 1`. If not, enable it:
   ```bash
   echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf
   sudo sysctl -p
   ```

2. **Verify NAT configuration on the EC2 instance**:
   ```bash
   sudo iptables -t nat -L
   ```
   Should show a MASQUERADE rule for the WireGuard interface.

3. **Check DNS resolution**:
   ```bash
   nslookup amazon.com
   ```
   If it fails, try updating your DNS settings in the client config:
   ```
   DNS = 1.1.1.1, 8.8.8.8
   ```

4. **Test routing with traceroute**:
   ```bash
   traceroute amazon.com
   ```
   Traffic should route through your VPN tunnel (10.0.0.1).

5. **Check AllowedIPs configuration**:
   - For full tunnel mode, ensure `AllowedIPs = 0.0.0.0/0`
   - For split tunnel mode, ensure AWS IPs are included in AllowedIPs

### Tunnel Connects but Drops Frequently

**Symptoms**: The tunnel connects but disconnects after a short time.

**Solutions**:

1. **Increase PersistentKeepalive**:
   Edit your client config to increase keepalive:
   ```
   PersistentKeepalive = 25
   ```

2. **Check for IP conflicts**:
   Ensure the tunnel IP range (10.0.0.0/24) doesn't conflict with your local network.

3. **Check for unstable internet connection**:
   Run a connection stability test:
   ```bash
   python main.py monitor --analyze
   ```

4. **Update EC2 instance**:
   ```bash
   ssh ubuntu@<your-ec2-ip>
   sudo apt update && sudo apt upgrade
   ```

5. **Review logs for clues**:
   ```bash
   sudo journalctl -u wg-quick@wg0
   ```

## Performance Issues

### Poor Throughput

**Symptoms**: Speed tests show much lower throughput than expected (below 1 Mbps).

**Solutions**:

1. **Run the optimization script**:
   ```bash
   python main.py optimize
   ```
   This uses reinforcement learning to find optimal settings.

2. **Adjust MTU manually**:
   Try different MTU values (typically between 1280-1480):
   ```bash
   python main.py monitor --optimize
   ```

3. **Test with different AWS regions**:
   The closest region might not always be the fastest. Try Singapore, Mumbai, or Tokyo.

4. **Check for local bandwidth usage**:
   Other applications might be consuming your bandwidth.

5. **Try AWS-only tunnel mode**:
   Use the AWS-only configuration:
   ```bash
   python main.py setup-client --mode=aws
   ```

### High Latency

**Symptoms**: Ping times to AWS services over 150ms.

**Solutions**:

1. **Run latency optimization**:
   ```bash
   python main.py optimize --mode=evaluate
   ```

2. **Try a different EC2 instance type**:
   c5n.large or c6gn.medium instances offer enhanced networking.

3. **Check for route optimization**:
   ```bash
   sudo ip route
   ```
   Ensure traffic to AWS services is going through the tunnel.

4. **Reduce buffer sizes**:
   Smaller buffers can reduce latency at the cost of throughput.

5. **Investigate local network issues**:
   ```bash
   mtr aws.amazon.com
   ```
   Look for hops with high latency or packet loss.

### High Packet Loss

**Symptoms**: Connections are unstable, downloads fail, or packet loss > 5%.

**Solutions**:

1. **Reduce MTU to avoid fragmentation**:
   ```bash
   python main.py monitor --optimize
   ```
   The optimizer will suggest a better MTU.

2. **Check EC2 instance load**:
   ```bash
   ssh ubuntu@<your-ec2-ip>
   top
   ```
   High CPU usage can lead to dropped packets.

3. **Increase buffer size**:
   Larger buffers can help with bursty connections.

4. **Test with AWS-only services**:
   Check if packet loss is specific to certain destinations.

5. **Check for ISP traffic shaping**:
   Some ISPs may throttle or shape VPN traffic.

## AWS EC2 Instance Issues

### Instance Unreachable

**Symptoms**: Cannot SSH to EC2 instance or tunnel connection fails.

**Solutions**:

1. **Check instance status in AWS console**:
   Ensure the instance is running and healthy.

2. **Verify security groups**:
   Ensure SSH (TCP 22) and WireGuard (UDP 51820) ports are open.

3. **Check if instance has a public IP**:
   Verify the Elastic IP is correctly associated.

4. **Try rebooting the instance**:
   Through AWS console or:
   ```bash
   aws ec2 reboot-instances --instance-ids <your-instance-id>
   ```

5. **Check AWS service status**:
   AWS outages can affect EC2 availability.

### Setup Script Fails

**Symptoms**: `setup-ec2.py` or `configure_wireguard.py` scripts fail.

**Solutions**:

1. **Check AWS credentials**:
   Ensure your `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are valid:
   ```bash
   aws sts get-caller-identity
   ```

2. **Verify required Python packages**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Check SSH key configuration**:
   Ensure `AWS_KEY_NAME` and `AWS_KEY_PATH` environment variables are set.

4. **Run with verbose logging**:
   ```bash
   python -m scripts.setup_ec2 --verbose
   ```

5. **Check for region-specific issues**:
   Some EC2 instance types might not be available in all regions.

## Reinforcement Learning Optimization Issues

### Training Fails

**Symptoms**: RL training crashes or fails to converge.

**Solutions**:

1. **Check TensorFlow installation**:
   ```bash
   python -c "import tensorflow as tf; print(tf.__version__)"
   ```

2. **Clear the model directory**:
   ```bash
   rm -rf models/saved_rl/*
   ```
   Then retry training.

3. **Increase training episodes**:
   ```bash
   python main.py optimize --mode=train --steps=200
   ```

4. **Check for available memory**:
   Training may fail if system memory is low.

5. **Try with smaller network size**:
   Edit `models/reinforcement_learning.py` to reduce network complexity.

### Model Performance Degradation

**Symptoms**: Optimized settings perform worse than default.

**Solutions**:

1. **Reset to pretrained model**:
   ```bash
   cp -r models/saved_rl/backup/* models/saved_rl/
   ```

2. **Evaluate model performance**:
   ```bash
   python main.py optimize --mode=evaluate --visualize
   ```
   Check results chart for insights.

3. **Return to mathematically optimized settings**:
   ```bash
   python main.py monitor --optimize
   ```
   Use mathematical model instead of RL.

4. **Try different exploration parameters**:
   ```bash
   python main.py optimize --explore
   ```

5. **Reset to defaults**:
   ```bash
   python main.py setup-client --mode=full
   ```

## Mathematical Model Issues

### Model Convergence Problems

**Symptoms**: Mathematical optimization always suggests the same values or extreme values.

**Solutions**:

1. **Update network measurements**:
   ```bash
   python main.py monitor --interval=10
   ```
   Let it run for a few minutes to collect data.

2. **Check for numerical stability issues**:
   Look for divide-by-zero or overflow errors in logs.

3. **Reset model parameters**:
   ```bash
   python main.py setup-all --skip-ec2 --skip-wireguard
   ```
   This will reinitialize the optimization models.

### Inaccurate Predictions

**Symptoms**: Model predicts much higher throughput than actually achieved.

**Solutions**:

1. **Update network congestion model**:
   The model may need recalibration based on your specific network.

2. **Run with different latency estimates**:
   Edit `models/network_optimization.py` to adjust baseline latency.

3. **Collect real-world measurements**:
   ```bash
   python main.py test
   ```
   Use test results to tune the model.

## Web Interface Issues

### Web UI Not Loading

**Symptoms**: Cannot access the web interface at `http://localhost:5000`.

**Solutions**:

1. **Check if the server is running**:
   ```bash
   ps aux | grep "python main.py web"
   ```

2. **Start the web server**:
   ```bash
   python main.py web
   ```

3. **Check for port conflicts**:
   ```bash
   sudo netstat -tulpn | grep 5000
   ```
   If port 5000 is in use, try a different port:
   ```bash
   python main.py web --port=5001
   ```

4. **Look for error messages**:
   Check console output for Python errors.

### Statistics Not Updating

**Symptoms**: Dashboard shows static values, graphs don't update.

**Solutions**:

1. **Restart the monitoring service**:
   ```bash
   python main.py monitor
   ```

2. **Check browser console for errors**:
   Open browser developer tools and look at the console tab.

3. **Clear browser cache**:
   Try incognito/private browsing mode or clear your cache.

4. **Verify API endpoints are working**:
   ```bash
   curl http://localhost:5000/api/stats/current
   ```

## Advanced Troubleshooting

### Collect Debug Information

To collect complete debugging information for support:

```bash
# Generate debug report
python main.py test --verbose
python main.py monitor --analyze
```

### Performance Tuning for Different Scenarios

#### Low-Latency Applications (e.g., Video Conferencing)

```bash
# Edit config file
sudo nano /etc/wireguard/wg0.conf

# Add these lines to [Interface] section
MTU = 1280
Table = off
```

#### High-Throughput Applications (e.g., File Transfer)

```bash
# Edit config file
sudo nano /etc/wireguard/wg0.conf

# Add these lines to [Interface] section
MTU = 1420
SaveConfig = true
```

#### ISP Throttling Workaround

If your ISP is throttling VPN traffic:

```bash
# Change ListenPort to common HTTPS port
sudo sed -i 's/ListenPort = 51820/ListenPort = 443/' /etc/wireguard/wg0.conf

# Update EC2 security group to allow UDP 443
aws ec2 authorize-security-group-ingress --group-id <sg-id> --protocol udp --port 443 --cidr 0.0.0.0/0
```

## Contact Support

If you've tried these troubleshooting steps and still face issues:

1. Collect logs and test results:
   ```bash
   zip -r support.zip logs/* test_results.* config/*
   ```

2. Open an issue on GitHub with:
   - Detailed description of the problem
   - Steps to reproduce
   - Output of troubleshooting commands
   - Your support.zip file (redact any sensitive information)

## Emergency Recovery

If everything else fails and you need to reset:

```bash
# Stop tunnel
sudo wg-quick down wg0

# Reset configuration
python main.py setup-all --skip-ec2
```

This will recreate your local configuration while preserving your EC2 instance.