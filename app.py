import os
import logging
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
    action = request.json.get('action')
    
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
