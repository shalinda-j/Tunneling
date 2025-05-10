import os
import logging
import re
import json
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from datetime import datetime, timedelta

from wireguard_manager import WireGuardManager
from network_monitor import NetworkMonitor

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key_for_development")

# Initialize WireGuard manager and network monitor
wg_manager = WireGuardManager()
network_monitor = NetworkMonitor()

@app.route('/')
def index():
    """Main dashboard page"""
    tunnel_status = wg_manager.get_tunnel_status()
    return render_template('index.html', 
                           tunnel_status=tunnel_status,
                           stats=network_monitor.get_current_stats())

@app.route('/stats')
def stats():
    """Detailed statistics page"""
    return render_template('stats.html', 
                           stats=network_monitor.get_current_stats(),
                           tunnel_status=wg_manager.get_tunnel_status())

@app.route('/setup')
def setup():
    """Configuration setup page"""
    config = wg_manager.get_config()
    return render_template('setup.html', config=config)

@app.route('/api/tunnel/status')
def tunnel_status():
    """API endpoint to get tunnel status"""
    return jsonify(wg_manager.get_tunnel_status())

@app.route('/api/tunnel/toggle', methods=['POST'])
def toggle_tunnel():
    """API endpoint to start/stop the tunnel"""
    data = request.json
    action = data.get('action') if data else None
    
    if action == 'start':
        result = wg_manager.start_tunnel()
        if result['success']:
            flash('Tunnel started successfully', 'success')
        else:
            flash(f'Failed to start tunnel: {result["error"]}', 'danger')
        return jsonify(result)
    
    elif action == 'stop':
        result = wg_manager.stop_tunnel()
        if result['success']:
            flash('Tunnel stopped successfully', 'success')
        else:
            flash(f'Failed to stop tunnel: {result["error"]}', 'danger')
        return jsonify(result)
    
    return jsonify({'success': False, 'error': 'Invalid action'})

@app.route('/api/config/update', methods=['POST'])
def update_config():
    """API endpoint to update WireGuard configuration"""
    config_data = request.json
    result = wg_manager.update_config(config_data)
    
    if result['success']:
        flash('Configuration updated successfully', 'success')
    else:
        flash(f'Failed to update configuration: {result["error"]}', 'danger')
        
    return jsonify(result)

@app.route('/api/stats/current')
def current_stats():
    """API endpoint to get current network statistics"""
    return jsonify(network_monitor.get_current_stats())

@app.route('/api/stats/history')
def stats_history():
    """API endpoint to get historical network statistics"""
    hours = request.args.get('hours', 1, type=int)
    return jsonify(network_monitor.get_stats_history(hours))

@app.route('/terminal')
def terminal():
    """Terminal page for command line access"""
    return render_template('terminal.html')

@app.route('/api/config')
def get_config():
    """API endpoint to get the current configuration"""
    return jsonify(wg_manager.get_config())

@app.route('/api/config/generate_keypair')
def generate_keypair():
    """API endpoint to generate a new WireGuard keypair"""
    return jsonify(wg_manager.generate_keypair())

@app.route('/api/config/reset', methods=['POST'])
def reset_config():
    """API endpoint to reset configuration to defaults"""
    try:
        wg_manager._create_default_settings()
        wg_manager._save_settings()
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Error resetting configuration: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/network/ping')
def ping_host():
    """API endpoint to ping a host"""
    host = request.args.get('host', '1.1.1.1')
    
    try:
        # Use network monitor's ping implementation
        def ping_host_impl(host, count=10):
            try:
                # Run ping command
                if os.name == 'nt':  # Windows
                    cmd = ['ping', '-n', str(count), host]
                else:  # Linux/Mac
                    cmd = ['ping', '-c', str(count), host]
                
                import subprocess
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    output = result.stdout
                    
                    # Extract packet loss
                    loss_match = None
                    if os.name == 'nt':  # Windows
                        loss_match = re.search(r'(\d+)% loss', output)
                    else:  # Linux/Mac
                        loss_match = re.search(r'(\d+)% packet loss', output)
                    
                    packet_loss = float(loss_match.group(1)) if loss_match else 0
                    
                    # Extract average latency
                    latency_match = None
                    if os.name == 'nt':  # Windows
                        latency_match = re.search(r'Average = (\d+)ms', output)
                    else:  # Linux/Mac
                        latency_match = re.search(r'min/avg/max/.+ = [\d.]+/([\d.]+)/', output)
                    
                    latency = float(latency_match.group(1)) if latency_match else 0
                    
                    # Extract packet counts
                    packets_sent = count
                    packets_received = packets_sent - int(packets_sent * packet_loss / 100)
                    
                    return {
                        'success': True,
                        'latency': latency,
                        'packet_loss': packet_loss,
                        'packets_sent': packets_sent,
                        'packets_received': packets_received
                    }
                
                return {
                    'success': False,
                    'error': f"Ping failed with return code {result.returncode}"
                }
                
            except Exception as e:
                logger.error(f"Error pinging host {host}: {e}")
                return {
                    'success': False,
                    'error': str(e)
                }
        
        return jsonify(ping_host_impl(host))
        
    except Exception as e:
        logger.error(f"Error in ping API: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/network/speed-test')
def api_speed_test():
    """API endpoint to run a speed test"""
    try:
        # Run a speed test using the network monitor
        network_monitor._run_speed_test()
        
        # Check if we have speed test results
        if hasattr(network_monitor, 'speed_test_results'):
            return jsonify({
                'success': True,
                'download': network_monitor.speed_test_results['download'],
                'upload': network_monitor.speed_test_results['upload'],
                'ping': network_monitor.speed_test_results['ping'],
                'server': network_monitor.speed_test_results['server']
            })
        else:
            # Fall back to current stats
            stats = network_monitor.get_current_stats()
            return jsonify({
                'success': True,
                'download': stats['download_speed'],
                'upload': stats['upload_speed'],
                'ping': stats['latency'],
                'server': 'Simulated from current stats'
            })
            
    except Exception as e:
        logger.error(f"Error in speed test API: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/logs')
def get_logs():
    """API endpoint to get recent log entries"""
    try:
        # Create a simple log reader
        log_file = 'application.log'  # Default log file path
        
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                # Get the last 50 lines
                lines = f.readlines()[-50:]
                return jsonify({
                    'success': True,
                    'logs': lines
                })
        
        # If no log file, return console logs
        recent_logs = [
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - wireguard_manager - WARNING - WireGuard does not appear to be installed or accessible",
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - network_monitor - DEBUG - Could not find wg0 interface, using total network stats"
        ]
        
        return jsonify({
            'success': True,
            'logs': recent_logs
        })
        
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
