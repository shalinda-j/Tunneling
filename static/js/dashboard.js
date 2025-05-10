/**
 * Dashboard functionality for the VPN Tunnel Manager
 */

// Store references to charts
let throughputChart = null;
let statisticsCharts = {};

// Store current tunnel status
let tunnelStatus = {
    running: false,
    uptime: null,
    endpoint: null,
    transfer_rx: 0,
    transfer_tx: 0
};

// Initialize the dashboard
function initDashboard() {
    // Create charts
    createCharts();
    
    // Start data refresh cycles
    refreshTunnelStatus();
    refreshStats();
    
    // Set up periodic updates
    setInterval(refreshTunnelStatus, 10000); // Update tunnel status every 10 seconds
    setInterval(refreshStats, 5000);         // Update network stats every 5 seconds
    
    // Set up event listeners for buttons
    setupEventListeners();
}

// Create dashboard charts
function createCharts() {
    // Create throughput chart
    const throughputCtx = document.getElementById('throughputChart');
    if (throughputCtx) {
        throughputChart = new Chart(throughputCtx, {
            type: 'line',
            data: {
                labels: createTimeLabels(15, 1), // 15 labels, 1 minute apart
                datasets: [
                    {
                        label: 'Download',
                        data: new Array(15).fill(0),
                        borderColor: 'rgba(54, 162, 235, 1)',
                        backgroundColor: 'rgba(54, 162, 235, 0.2)',
                        fill: true,
                        tension: 0.4
                    },
                    {
                        label: 'Upload',
                        data: new Array(15).fill(0),
                        borderColor: 'rgba(255, 99, 132, 1)',
                        backgroundColor: 'rgba(255, 99, 132, 0.2)',
                        fill: true,
                        tension: 0.4
                    }
                ]
            },
            options: {
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Speed (Mbps)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Time'
                        }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Network Throughput'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                label += context.raw.toFixed(2) + ' Mbps';
                                return label;
                            }
                        }
                    }
                },
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                responsive: true,
                maintainAspectRatio: false
            }
        });
    }
}

// Refresh tunnel status information
function refreshTunnelStatus() {
    fetch('/api/tunnel/status')
        .then(response => response.json())
        .then(data => {
            // Update stored tunnel status
            tunnelStatus = data;
            
            // Update UI elements
            updateTunnelStatusUI();
        })
        .catch(error => {
            console.error('Error fetching tunnel status:', error);
        });
}

// Update the UI with current tunnel status
function updateTunnelStatusUI() {
    // Update status indicators
    const statusIcon = document.getElementById('tunnelStatusIcon');
    const statusText = document.getElementById('tunnelStatusText');
    
    if (statusIcon && statusText) {
        if (tunnelStatus.running) {
            statusIcon.className = 'status-indicator status-connected';
            statusText.textContent = 'Connected';
        } else {
            statusIcon.className = 'status-indicator status-disconnected';
            statusText.textContent = 'Disconnected';
        }
    }
    
    // Update detailed status elements if they exist
    const uptimeElem = document.getElementById('uptime');
    const endpointElem = document.getElementById('endpoint');
    const dataReceivedElem = document.getElementById('dataReceived');
    const dataSentElem = document.getElementById('dataSent');
    
    if (uptimeElem && tunnelStatus.uptime) {
        uptimeElem.textContent = tunnelStatus.uptime;
    }
    
    if (endpointElem && tunnelStatus.endpoint) {
        endpointElem.textContent = tunnelStatus.endpoint;
    }
    
    if (dataReceivedElem && tunnelStatus.transfer_rx) {
        dataReceivedElem.textContent = formatBytes(tunnelStatus.transfer_rx);
    }
    
    if (dataSentElem && tunnelStatus.transfer_tx) {
        dataSentElem.textContent = formatBytes(tunnelStatus.transfer_tx);
    }
    
    // Update buttons based on current status
    const startBtn = document.getElementById('startTunnelBtn');
    const stopBtn = document.getElementById('stopTunnelBtn');
    
    if (startBtn && stopBtn) {
        if (tunnelStatus.running) {
            startBtn.style.display = 'none';
            stopBtn.style.display = 'inline-block';
        } else {
            startBtn.style.display = 'inline-block';
            stopBtn.style.display = 'none';
        }
    }
}

// Refresh network statistics
function refreshStats() {
    fetch('/api/stats/current')
        .then(response => response.json())
        .then(data => {
            // Update stats UI elements
            updateStatsUI(data);
            
            // Update charts
            updateThroughputChart(data);
        })
        .catch(error => {
            console.error('Error fetching network stats:', error);
        });
}

// Update stats UI elements
function updateStatsUI(stats) {
    // Update the network stats cards
    const downloadSpeedElem = document.getElementById('downloadSpeed');
    const uploadSpeedElem = document.getElementById('uploadSpeed');
    const latencyElem = document.getElementById('latency');
    const packetLossElem = document.getElementById('packetLoss');
    
    if (downloadSpeedElem) {
        downloadSpeedElem.textContent = stats.download_speed.toFixed(2) + ' Mbps';
    }
    
    if (uploadSpeedElem) {
        uploadSpeedElem.textContent = stats.upload_speed.toFixed(2) + ' Mbps';
    }
    
    if (latencyElem) {
        latencyElem.textContent = Math.round(stats.latency) + ' ms';
    }
    
    if (packetLossElem) {
        packetLossElem.textContent = stats.packet_loss.toFixed(1) + '%';
    }
}

// Update the throughput chart with new data
function updateThroughputChart(stats) {
    if (!throughputChart) return;
    
    // Add new data points
    throughputChart.data.datasets[0].data.push(stats.download_speed);
    throughputChart.data.datasets[1].data.push(stats.upload_speed);
    
    // Remove oldest data points if we have more than 15
    if (throughputChart.data.datasets[0].data.length > 15) {
        throughputChart.data.datasets[0].data.shift();
        throughputChart.data.datasets[1].data.shift();
    }
    
    // Update labels
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    throughputChart.data.labels.push(timeStr);
    
    if (throughputChart.data.labels.length > 15) {
        throughputChart.data.labels.shift();
    }
    
    // Update the chart
    throughputChart.update();
}

// Set up event listeners for buttons
function setupEventListeners() {
    // Start tunnel button
    const startBtn = document.getElementById('startTunnelBtn');
    if (startBtn) {
        startBtn.addEventListener('click', () => {
            startBtn.disabled = true;
            startBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Starting...';
            
            fetch('/api/tunnel/toggle', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ action: 'start' })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    refreshTunnelStatus();
                } else {
                    alert('Failed to start tunnel: ' + data.error);
                }
                startBtn.disabled = false;
                startBtn.innerHTML = '<i class="fas fa-play-circle me-2"></i>Start Tunnel';
            })
            .catch(error => {
                console.error('Error starting tunnel:', error);
                startBtn.disabled = false;
                startBtn.innerHTML = '<i class="fas fa-play-circle me-2"></i>Start Tunnel';
            });
        });
    }
    
    // Stop tunnel button
    const stopBtn = document.getElementById('stopTunnelBtn');
    if (stopBtn) {
        stopBtn.addEventListener('click', () => {
            stopBtn.disabled = true;
            stopBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Stopping...';
            
            fetch('/api/tunnel/toggle', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ action: 'stop' })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    refreshTunnelStatus();
                } else {
                    alert('Failed to stop tunnel: ' + data.error);
                }
                stopBtn.disabled = false;
                stopBtn.innerHTML = '<i class="fas fa-stop-circle me-2"></i>Stop Tunnel';
            })
            .catch(error => {
                console.error('Error stopping tunnel:', error);
                stopBtn.disabled = false;
                stopBtn.innerHTML = '<i class="fas fa-stop-circle me-2"></i>Stop Tunnel';
            });
        });
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', initDashboard);
