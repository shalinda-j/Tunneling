/**
 * Terminal functionality for the VPN Tunnel Manager
 */

document.addEventListener('DOMContentLoaded', () => {
    const terminal = document.getElementById('terminal');
    const terminalOutput = document.getElementById('terminal-output');
    const commandInput = document.getElementById('commandInput');
    const runCommandBtn = document.getElementById('runCommandBtn');
    const clearTerminalBtn = document.getElementById('clearTerminalBtn');
    
    // Command history functionality
    let commandHistory = [];
    let historyIndex = -1;
    
    // Terminal prompt
    const prompt = '<span class="text-info">vpn-tunnel</span><span class="text-light">:</span><span class="text-success">~</span><span class="text-light">$</span> ';
    
    // Add event listeners
    commandInput.addEventListener('keydown', handleInputKeypress);
    runCommandBtn.addEventListener('click', executeCommand);
    clearTerminalBtn.addEventListener('click', clearTerminal);
    
    // Focus the input field when the terminal is clicked
    terminal.addEventListener('click', () => {
        commandInput.focus();
    });
    
    // Focus the input field on page load
    commandInput.focus();
    
    /**
     * Handle keypresses in the command input
     */
    function handleInputKeypress(e) {
        // Execute command on Enter
        if (e.key === 'Enter') {
            executeCommand();
        }
        
        // Command history navigation (up arrow)
        if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (commandHistory.length > 0 && historyIndex < commandHistory.length - 1) {
                historyIndex++;
                commandInput.value = commandHistory[commandHistory.length - 1 - historyIndex];
            }
        }
        
        // Command history navigation (down arrow)
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (historyIndex > 0) {
                historyIndex--;
                commandInput.value = commandHistory[commandHistory.length - 1 - historyIndex];
            } else if (historyIndex === 0) {
                historyIndex--;
                commandInput.value = '';
            }
        }
        
        // Tab completion (basic implementation)
        if (e.key === 'Tab') {
            e.preventDefault();
            const input = commandInput.value.trim();
            
            // Simple command completion
            const commands = [
                'wg-keygen', 'wg-status', 'wg-start', 'wg-stop',
                'ping-test', 'speed-test', 'trace-route', 'show-routes',
                'config-get', 'config-set', 'config-reset', 'show-logs',
                'clear', 'help'
            ];
            
            for (const cmd of commands) {
                if (cmd.startsWith(input)) {
                    commandInput.value = cmd + ' ';
                    break;
                }
            }
        }
    }
    
    /**
     * Execute the command in the input field
     */
    function executeCommand() {
        const command = commandInput.value.trim();
        if (!command) return;
        
        // Add command to history
        commandHistory.push(command);
        historyIndex = -1;
        
        // Display command in terminal
        appendToTerminal('<div class="command-line">' + prompt + escapeHTML(command) + '</div>');
        
        // Process command
        processCommand(command);
        
        // Clear input field
        commandInput.value = '';
        
        // Scroll to bottom of terminal
        terminal.scrollTop = terminal.scrollHeight;
    }
    
    /**
     * Process a command and generate output
     */
    function processCommand(command) {
        const commandLower = command.toLowerCase();
        const args = command.split(' ');
        
        // Basic command processing
        switch (args[0]) {
            case 'help':
                showHelp();
                break;
                
            case 'clear':
                clearTerminal();
                break;
                
            case 'wg-keygen':
                generateWireguardKeys();
                break;
                
            case 'wg-status':
                getWireguardStatus();
                break;
                
            case 'wg-start':
                startWireguardTunnel();
                break;
                
            case 'wg-stop':
                stopWireguardTunnel();
                break;
                
            case 'ping-test':
                if (args.length > 1) {
                    pingTest(args[1]);
                } else {
                    appendToTerminal('<div class="text-warning">Error: Missing host parameter. Usage: ping-test &lt;host&gt;</div>');
                }
                break;
                
            case 'speed-test':
                runSpeedTest();
                break;
                
            case 'trace-route':
                if (args.length > 1) {
                    traceRoute(args[1]);
                } else {
                    appendToTerminal('<div class="text-warning">Error: Missing host parameter. Usage: trace-route &lt;host&gt;</div>');
                }
                break;
                
            case 'show-routes':
                showRoutes();
                break;
                
            case 'config-get':
                getConfiguration();
                break;
                
            case 'config-set':
                if (args.length >= 3) {
                    setConfiguration(args[1], args.slice(2).join(' '));
                } else {
                    appendToTerminal('<div class="text-warning">Error: Missing parameters. Usage: config-set &lt;key&gt; &lt;value&gt;</div>');
                }
                break;
                
            case 'config-reset':
                resetConfiguration();
                break;
                
            case 'show-logs':
                showLogs();
                break;
                
            default:
                appendToTerminal('<div class="text-danger">Error: Unknown command "' + escapeHTML(args[0]) + '". Type "help" to see available commands.</div>');
                break;
        }
    }
    
    /**
     * Show help information
     */
    function showHelp() {
        const helpText = `
        <div class="help-text mb-2">
            <div class="text-primary fw-bold">Available Commands:</div>
            
            <div class="mt-2 fw-bold text-light">WireGuard Commands:</div>
            <div class="ps-3">
                <div><span class="text-info">wg-keygen</span> - Generate a new WireGuard key pair</div>
                <div><span class="text-info">wg-status</span> - Check the current status of the WireGuard tunnel</div>
                <div><span class="text-info">wg-start</span> - Start the WireGuard tunnel</div>
                <div><span class="text-info">wg-stop</span> - Stop the WireGuard tunnel</div>
            </div>
            
            <div class="mt-2 fw-bold text-light">Network Diagnostic Commands:</div>
            <div class="ps-3">
                <div><span class="text-info">ping-test &lt;host&gt;</span> - Ping a host to check connectivity and latency</div>
                <div><span class="text-info">speed-test</span> - Run a speed test to measure current connection speeds</div>
                <div><span class="text-info">trace-route &lt;host&gt;</span> - Trace the network route to a destination</div>
                <div><span class="text-info">show-routes</span> - Show current routing table</div>
            </div>
            
            <div class="mt-2 fw-bold text-light">Configuration Commands:</div>
            <div class="ps-3">
                <div><span class="text-info">config-get</span> - Show the current WireGuard configuration</div>
                <div><span class="text-info">config-set &lt;key&gt; &lt;value&gt;</span> - Set a configuration value</div>
                <div><span class="text-info">config-reset</span> - Reset configuration to defaults</div>
                <div><span class="text-info">show-logs</span> - Show recent log entries</div>
            </div>
            
            <div class="mt-2 fw-bold text-light">Terminal Commands:</div>
            <div class="ps-3">
                <div><span class="text-info">clear</span> - Clear the terminal</div>
                <div><span class="text-info">help</span> - Show this help message</div>
            </div>
        </div>
        `;
        
        appendToTerminal(helpText);
    }
    
    /**
     * Clear the terminal output
     */
    function clearTerminal() {
        terminalOutput.innerHTML = '';
    }
    
    /**
     * Append content to the terminal
     */
    function appendToTerminal(content) {
        terminalOutput.innerHTML += content;
    }
    
    /**
     * Escape HTML special characters
     */
    function escapeHTML(text) {
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }
    
    /**
     * API Interaction: Generate WireGuard keys
     */
    function generateWireguardKeys() {
        appendToTerminal('<div class="text-light"><span class="spinner-border spinner-border-sm text-info me-2"></span>Generating WireGuard key pair...</div>');
        
        fetch('/api/config/generate_keypair')
            .then(response => response.json())
            .then(data => {
                if (data.private_key && data.public_key) {
                    const output = `
                    <div class="key-result mt-2 mb-2">
                        <div class="mb-1 text-success">Key pair generated successfully!</div>
                        <div class="mb-1">Private Key: <span class="text-warning">${data.private_key}</span></div>
                        <div>Public Key: <span class="text-warning">${data.public_key}</span></div>
                        <div class="mt-2 text-info">Keep your private key secret. Add your public key to the AWS server configuration.</div>
                    </div>
                    `;
                    appendToTerminal(output);
                } else {
                    appendToTerminal('<div class="text-danger">Error: Failed to generate key pair.</div>');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                appendToTerminal('<div class="text-danger">Error: Failed to communicate with server.</div>');
            });
    }
    
    /**
     * API Interaction: Get WireGuard status
     */
    function getWireguardStatus() {
        appendToTerminal('<div class="text-light"><span class="spinner-border spinner-border-sm text-info me-2"></span>Fetching WireGuard tunnel status...</div>');
        
        fetch('/api/tunnel/status')
            .then(response => response.json())
            .then(data => {
                let statusClass = data.running ? 'text-success' : 'text-danger';
                let statusText = data.running ? 'Running' : 'Stopped';
                
                const output = `
                <div class="status-result mt-2 mb-2">
                    <div class="mb-1">Status: <span class="${statusClass}">${statusText}</span></div>
                    ${data.running ? `
                    <div class="mb-1">Uptime: <span class="text-light">${data.uptime || 'N/A'}</span></div>
                    <div class="mb-1">Endpoint: <span class="text-light">${data.endpoint || 'N/A'}</span></div>
                    <div class="mb-1">Last Handshake: <span class="text-light">${data.last_handshake || 'N/A'}</span></div>
                    <div class="mb-1">Data Received: <span class="text-light">${formatBytes(data.transfer_rx)}</span></div>
                    <div class="mb-1">Data Sent: <span class="text-light">${formatBytes(data.transfer_tx)}</span></div>
                    ` : ''}
                    <div class="mb-1">Local IP: <span class="text-light">${data.local_ip || 'Not configured'}</span></div>
                    <div class="mb-1">AWS Public Key: <span class="text-light">${truncateKey(data.aws_public_key) || 'Not configured'}</span></div>
                    <div class="mt-2 text-info">${data.available ? 'WireGuard is installed and available.' : 'WireGuard is not installed or not accessible.'}</div>
                </div>
                `;
                appendToTerminal(output);
            })
            .catch(error => {
                console.error('Error:', error);
                appendToTerminal('<div class="text-danger">Error: Failed to fetch tunnel status.</div>');
            });
    }
    
    /**
     * API Interaction: Start WireGuard tunnel
     */
    function startWireguardTunnel() {
        appendToTerminal('<div class="text-light"><span class="spinner-border spinner-border-sm text-info me-2"></span>Starting WireGuard tunnel...</div>');
        
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
                    appendToTerminal('<div class="text-success mt-2">Tunnel started successfully.</div>');
                } else {
                    appendToTerminal(`<div class="text-danger mt-2">Failed to start tunnel: ${data.error}</div>`);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                appendToTerminal('<div class="text-danger">Error: Failed to communicate with server.</div>');
            });
    }
    
    /**
     * API Interaction: Stop WireGuard tunnel
     */
    function stopWireguardTunnel() {
        appendToTerminal('<div class="text-light"><span class="spinner-border spinner-border-sm text-info me-2"></span>Stopping WireGuard tunnel...</div>');
        
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
                    appendToTerminal('<div class="text-success mt-2">Tunnel stopped successfully.</div>');
                } else {
                    appendToTerminal(`<div class="text-danger mt-2">Failed to stop tunnel: ${data.error}</div>`);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                appendToTerminal('<div class="text-danger">Error: Failed to communicate with server.</div>');
            });
    }
    
    /**
     * API Interaction: Ping test
     */
    function pingTest(host) {
        appendToTerminal(`<div class="text-light"><span class="spinner-border spinner-border-sm text-info me-2"></span>Pinging ${escapeHTML(host)}...</div>`);
        
        fetch(`/api/network/ping?host=${encodeURIComponent(host)}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const output = `
                    <div class="ping-result mt-2 mb-2">
                        <div class="mb-1 text-success">Ping results for ${escapeHTML(host)}:</div>
                        <div class="mb-1">Average Latency: <span class="text-light">${data.latency.toFixed(2)} ms</span></div>
                        <div class="mb-1">Packet Loss: <span class="text-light">${data.packet_loss.toFixed(1)}%</span></div>
                        <div class="mb-1">Packets Sent: <span class="text-light">${data.packets_sent}</span></div>
                        <div class="mb-1">Packets Received: <span class="text-light">${data.packets_received}</span></div>
                    </div>
                    `;
                    appendToTerminal(output);
                } else {
                    appendToTerminal(`<div class="text-danger mt-2">Ping failed: ${data.error}</div>`);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                appendToTerminal(`<div class="text-danger">Error: Unable to ping ${escapeHTML(host)}. The ping command may not be available in this environment or the host is unreachable.</div>`);
                
                // Fallback to simulated ping response for demonstration
                simulatePingResponse(host);
            });
    }
    
    /**
     * Simulate a ping response (for demonstration in environments without ping command)
     */
    function simulatePingResponse(host) {
        setTimeout(() => {
            const latency = Math.random() * 100 + 20; // 20-120ms
            const packetLoss = Math.random() * 5; // 0-5%
            
            const output = `
            <div class="ping-result mt-2 mb-2">
                <div class="mb-1 text-warning">Simulated ping results for ${escapeHTML(host)}:</div>
                <div class="mb-1">Average Latency: <span class="text-light">${latency.toFixed(2)} ms</span></div>
                <div class="mb-1">Packet Loss: <span class="text-light">${packetLoss.toFixed(1)}%</span></div>
                <div class="mb-1">Packets Sent: <span class="text-light">10</span></div>
                <div class="mb-1">Packets Received: <span class="text-light">${Math.round(10 - (10 * packetLoss / 100))}</span></div>
                <div class="text-info fst-italic">Note: This is a simulated response for demonstration purposes.</div>
            </div>
            `;
            appendToTerminal(output);
        }, 1500);
    }
    
    /**
     * API Interaction: Run speed test
     */
    function runSpeedTest() {
        appendToTerminal('<div class="text-light"><span class="spinner-border spinner-border-sm text-info me-2"></span>Running speed test... (this may take a moment)</div>');
        
        fetch('/api/network/speed-test')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const output = `
                    <div class="speed-result mt-2 mb-2">
                        <div class="mb-1 text-success">Speed test results:</div>
                        <div class="mb-1">Download: <span class="text-light">${data.download.toFixed(2)} Mbps</span></div>
                        <div class="mb-1">Upload: <span class="text-light">${data.upload.toFixed(2)} Mbps</span></div>
                        <div class="mb-1">Ping: <span class="text-light">${data.ping.toFixed(1)} ms</span></div>
                        <div class="mb-1">Server: <span class="text-light">${data.server}</span></div>
                    </div>
                    `;
                    appendToTerminal(output);
                } else {
                    appendToTerminal(`<div class="text-danger mt-2">Speed test failed: ${data.error}</div>`);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                appendToTerminal('<div class="text-danger">Error: Failed to run speed test. Using simulated results.</div>');
                
                // Fallback to current stats
                fetch('/api/stats/current')
                    .then(response => response.json())
                    .then(stats => {
                        const output = `
                        <div class="speed-result mt-2 mb-2">
                            <div class="mb-1 text-warning">Current network statistics:</div>
                            <div class="mb-1">Download: <span class="text-light">${stats.download_speed.toFixed(2)} Mbps</span></div>
                            <div class="mb-1">Upload: <span class="text-light">${stats.upload_speed.toFixed(2)} Mbps</span></div>
                            <div class="mb-1">Latency: <span class="text-light">${stats.latency.toFixed(1)} ms</span></div>
                            <div class="text-info fst-italic">Note: These are current statistics, not a full speed test.</div>
                        </div>
                        `;
                        appendToTerminal(output);
                    })
                    .catch(() => {
                        // Fallback to simulated speed test response
                        simulateSpeedTestResponse();
                    });
            });
    }
    
    /**
     * Simulate a speed test response (for demonstration)
     */
    function simulateSpeedTestResponse() {
        setTimeout(() => {
            const download = 1.5 + Math.random() * 0.5; // 1.5-2.0 Mbps
            const upload = 0.75 + Math.random() * 0.25; // 0.75-1.0 Mbps
            const ping = 80 + Math.random() * 40; // 80-120ms
            
            const output = `
            <div class="speed-result mt-2 mb-2">
                <div class="mb-1 text-warning">Simulated speed test results:</div>
                <div class="mb-1">Download: <span class="text-light">${download.toFixed(2)} Mbps</span></div>
                <div class="mb-1">Upload: <span class="text-light">${upload.toFixed(2)} Mbps</span></div>
                <div class="mb-1">Ping: <span class="text-light">${ping.toFixed(1)} ms</span></div>
                <div class="mb-1">Server: <span class="text-light">test-server.net (simulated)</span></div>
                <div class="text-info fst-italic">Note: This is a simulated response for demonstration purposes.</div>
            </div>
            `;
            appendToTerminal(output);
        }, 2000);
    }
    
    /**
     * API Interaction: Trace route
     */
    function traceRoute(host) {
        appendToTerminal(`<div class="text-light"><span class="spinner-border spinner-border-sm text-info me-2"></span>Tracing route to ${escapeHTML(host)}...</div>`);
        
        // Since we don't have an actual API endpoint for this, we'll simulate it
        setTimeout(() => {
            const hops = Math.floor(Math.random() * 5) + 5; // 5-10 hops
            let output = `
            <div class="trace-result mt-2 mb-2">
                <div class="mb-1 text-success">Trace route to ${escapeHTML(host)}:</div>
            `;
            
            for (let i = 1; i <= hops; i++) {
                const latency = Math.random() * 80 + 10 * i; // Increasing latency with hops
                let ipParts = [];
                for (let j = 0; j < 4; j++) {
                    ipParts.push(Math.floor(Math.random() * 255));
                }
                const ip = ipParts.join('.');
                
                output += `<div class="mb-1">${i}. <span class="text-light">${ip}</span> <span class="text-muted">${latency.toFixed(1)} ms</span></div>`;
            }
            
            output += `
                <div class="text-info fst-italic mt-2">Note: This is a simulated response for demonstration purposes.</div>
            </div>
            `;
            
            appendToTerminal(output);
        }, 2000);
    }
    
    /**
     * API Interaction: Show routing table
     */
    function showRoutes() {
        appendToTerminal('<div class="text-light"><span class="spinner-border spinner-border-sm text-info me-2"></span>Fetching routing table...</div>');
        
        // Since we don't have an actual API endpoint for this, we'll simulate it
        setTimeout(() => {
            const output = `
            <div class="routes-result mt-2 mb-2 fw-light" style="font-family: monospace;">
                <div class="mb-1 text-success">Network Routes:</div>
                <div class="mb-1">Kernel IP routing table</div>
                <div class="mb-1">Destination     Gateway         Genmask         Flags Metric Ref    Use Iface</div>
                <div class="mb-1">0.0.0.0         10.0.0.1        0.0.0.0         UG    0      0        0 wg0</div>
                <div class="mb-1">10.0.0.0        0.0.0.0         255.255.255.0   U     0      0        0 wg0</div>
                <div class="mb-1">192.168.1.0     0.0.0.0         255.255.255.0   U     0      0        0 eth0</div>
                <div class="text-info fst-italic mt-2">Note: This is a simulated response for demonstration purposes.</div>
            </div>
            `;
            
            appendToTerminal(output);
        }, 1500);
    }
    
    /**
     * API Interaction: Get current configuration
     */
    function getConfiguration() {
        appendToTerminal('<div class="text-light"><span class="spinner-border spinner-border-sm text-info me-2"></span>Fetching current configuration...</div>');
        
        fetch('/api/config')
            .then(response => response.json())
            .then(data => {
                let output = `
                <div class="config-result mt-2 mb-2">
                    <div class="mb-1 text-success">Current Configuration:</div>
                `;
                
                for (const [key, value] of Object.entries(data)) {
                    // Hide or truncate sensitive information
                    let displayValue = value;
                    if (key === 'local_private_key' && value) {
                        displayValue = truncateKey(value);
                    }
                    
                    output += `<div class="mb-1">${key}: <span class="text-light">${displayValue}</span></div>`;
                }
                
                output += `</div>`;
                appendToTerminal(output);
            })
            .catch(error => {
                console.error('Error:', error);
                appendToTerminal('<div class="text-danger">Error: Failed to fetch configuration.</div>');
            });
    }
    
    /**
     * API Interaction: Set configuration value
     */
    function setConfiguration(key, value) {
        appendToTerminal(`<div class="text-light"><span class="spinner-border spinner-border-sm text-info me-2"></span>Setting ${escapeHTML(key)} to ${escapeHTML(value)}...</div>`);
        
        const configData = {};
        configData[key] = value;
        
        fetch('/api/config/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(configData)
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    appendToTerminal(`<div class="text-success mt-2">Configuration updated successfully.</div>`);
                } else {
                    appendToTerminal(`<div class="text-danger mt-2">Failed to update configuration: ${data.error}</div>`);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                appendToTerminal('<div class="text-danger">Error: Failed to update configuration.</div>');
            });
    }
    
    /**
     * API Interaction: Reset configuration
     */
    function resetConfiguration() {
        appendToTerminal('<div class="text-light"><span class="spinner-border spinner-border-sm text-info me-2"></span>Resetting configuration to defaults...</div>');
        
        fetch('/api/config/reset', {
            method: 'POST'
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    appendToTerminal('<div class="text-success mt-2">Configuration reset to defaults.</div>');
                } else {
                    appendToTerminal(`<div class="text-danger mt-2">Failed to reset configuration: ${data.error}</div>`);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                appendToTerminal('<div class="text-danger">Error: Failed to reset configuration.</div>');
                appendToTerminal('<div class="text-warning">Using simulated response for demonstration purposes.</div>');
                
                // Simulate success for demonstration
                setTimeout(() => {
                    appendToTerminal('<div class="text-success mt-2">Configuration reset to defaults (simulated).</div>');
                }, 1000);
            });
    }
    
    /**
     * API Interaction: Show logs
     */
    function showLogs() {
        appendToTerminal('<div class="text-light"><span class="spinner-border spinner-border-sm text-info me-2"></span>Fetching recent logs...</div>');
        
        fetch('/api/logs')
            .then(response => response.json())
            .then(data => {
                if (data.success && data.logs) {
                    let output = `
                    <div class="logs-result mt-2 mb-2">
                        <div class="mb-1 text-success">Recent Log Entries:</div>
                        <pre class="log-entries mt-2 p-2 bg-dark text-light" style="max-height: 300px; overflow-y: auto; font-size: 0.85rem;">`;
                    
                    data.logs.forEach(log => {
                        output += `${log}\n`;
                    });
                    
                    output += `</pre>
                    </div>`;
                    appendToTerminal(output);
                } else {
                    appendToTerminal(`<div class="text-danger mt-2">Failed to fetch logs: ${data.error || 'Unknown error'}</div>`);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                appendToTerminal('<div class="text-danger">Error: Failed to fetch logs.</div>');
                
                // Simulate log output for demonstration
                simulateLogOutput();
            });
    }
    
    /**
     * Simulate log output (for demonstration)
     */
    function simulateLogOutput() {
        setTimeout(() => {
            const currentTime = new Date().toISOString();
            const output = `
            <div class="logs-result mt-2 mb-2">
                <div class="mb-1 text-warning">Simulated Log Entries:</div>
                <pre class="log-entries mt-2 p-2 bg-dark text-light" style="max-height: 300px; overflow-y: auto; font-size: 0.85rem;">
${currentTime.split('T')[0]} 10:05:20 - wireguard_manager - WARNING - WireGuard does not appear to be installed or accessible
${currentTime.split('T')[0]} 10:05:20 - network_monitor - DEBUG - Could not find wg0 interface, using total network stats
${currentTime.split('T')[0]} 10:05:25 - network_monitor - DEBUG - Could not find wg0 interface, using total network stats
${currentTime.split('T')[0]} 10:05:30 - network_monitor - DEBUG - Could not find wg0 interface, using total network stats
${currentTime.split('T')[0]} 10:05:35 - network_monitor - DEBUG - Could not find wg0 interface, using total network stats
${currentTime.split('T')[0]} 10:05:40 - network_monitor - DEBUG - Could not find wg0 interface, using total network stats
${currentTime.split('T')[0]} 10:05:45 - network_monitor - DEBUG - Could not find wg0 interface, using total network stats
${currentTime.split('T')[0]} 10:05:50 - network_monitor - DEBUG - Could not find wg0 interface, using total network stats
${currentTime.split('T')[0]} 10:05:55 - network_monitor - DEBUG - Could not find wg0 interface, using total network stats
${currentTime.split('T')[0]} 10:06:00 - network_monitor - DEBUG - Could not find wg0 interface, using total network stats
${currentTime.split('T')[0]} 10:06:05 - network_monitor - DEBUG - Could not find wg0 interface, using total network stats
                </pre>
                <div class="text-info fst-italic mt-2">Note: This is a simulated response for demonstration purposes.</div>
            </div>
            `;
            
            appendToTerminal(output);
        }, 1500);
    }
    
    /**
     * Format bytes into human-readable format
     */
    function formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    /**
     * Truncate a key for display purposes
     */
    function truncateKey(key) {
        if (!key) return 'Not configured';
        if (key.length <= 12) return key;
        return key.substr(0, 6) + '...' + key.substr(-6);
    }
});