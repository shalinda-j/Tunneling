/**
 * Utility functions for working with charts
 */

/**
 * Format bytes into a human-readable string with appropriate units
 * @param {number} bytes - The number of bytes
 * @param {number} decimals - Number of decimal places (default: 2)
 * @returns {string} Formatted string with units
 */
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
    
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

/**
 * Format a speed value in bits per second to appropriate units
 * @param {number} bps - Bits per second
 * @param {number} decimals - Number of decimal places (default: 2)
 * @returns {string} Formatted string with units
 */
function formatBitrate(bps, decimals = 2) {
    if (bps === 0) return '0 bps';
    
    const k = 1000; // Use 1000 for network speeds (not 1024)
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['bps', 'Kbps', 'Mbps', 'Gbps', 'Tbps'];
    
    const i = Math.floor(Math.log(bps) / Math.log(k));
    
    return parseFloat((bps / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

/**
 * Creates a gradient for chart backgrounds
 * @param {CanvasRenderingContext2D} ctx - Canvas context
 * @param {string} colorStart - Starting color
 * @param {string} colorEnd - Ending color
 * @returns {CanvasGradient} Gradient object
 */
function createGradient(ctx, colorStart, colorEnd) {
    const gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, colorStart);
    gradient.addColorStop(1, colorEnd);
    return gradient;
}

/**
 * Get a color for a chart based on a value and thresholds
 * @param {number} value - The value to evaluate
 * @param {Object} thresholds - Threshold values {warning, danger}
 * @returns {string} CSS color value
 */
function getThresholdColor(value, thresholds) {
    if (value >= thresholds.danger) {
        return 'var(--bs-danger)';
    } else if (value >= thresholds.warning) {
        return 'var(--bs-warning)';
    } else {
        return 'var(--bs-success)';
    }
}

/**
 * Create time labels for a chart at regular intervals
 * @param {number} count - Number of labels to create
 * @param {number} intervalMinutes - Minutes between labels
 * @returns {Array} Array of time strings
 */
function createTimeLabels(count, intervalMinutes = 5) {
    const labels = [];
    const now = new Date();
    
    for (let i = 0; i < count; i++) {
        const time = new Date(now.getTime() - (i * intervalMinutes * 60 * 1000));
        labels.unshift(time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
    }
    
    return labels;
}

/**
 * Format a duration in seconds to a human-readable string
 * @param {number} seconds - Duration in seconds
 * @returns {string} Formatted duration string
 */
function formatDuration(seconds) {
    if (seconds < 60) {
        return `${seconds}s`;
    }
    
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) {
        return `${minutes}m ${seconds % 60}s`;
    }
    
    const hours = Math.floor(minutes / 60);
    if (hours < 24) {
        return `${hours}h ${minutes % 60}m`;
    }
    
    const days = Math.floor(hours / 24);
    return `${days}d ${hours % 24}h`;
}
