/**
 * Hydro Control - Thames Water Dashboard
 * Industrial Aquatic Design System
 */

// API base URL
const API_BASE = '';

// Chart instances
let dailyChart = null;
let hourlyChart = null;
let monthlyChart = null;

// Color palette - Dark theme with water accents
const COLORS = {
    // Water theme
    waterPrimary: '#06B6D4',
    waterLight: '#22D3EE',
    waterDark: '#0891B2',
    waterGlow: 'rgba(6, 182, 212, 0.4)',

    // Status colors
    healthy: '#10B981',
    warning: '#F59E0B',
    danger: '#EF4444',

    // Background colors
    bgDark: '#0F172A',
    bgCard: '#1E293B',
    bgElevated: '#334155',

    // Text colors
    textPrimary: '#F8FAFC',
    textSecondary: '#CBD5E1',
    textMuted: '#64748B',

    // Chart specific
    gridColor: 'rgba(100, 116, 139, 0.2)',
    thresholdLine: 'rgba(245, 158, 11, 0.8)'
};

// Thames Water pricing (from Dec 2025 bill)
const PRICING = {
    ratePerLitre: 0.0040223,
    dailyFixedCharge: 0.532
};

// Gauge configuration
const GAUGE = {
    maxValue: 1000,
    threshold: 800,
    arcLength: 251 // SVG arc length
};

/**
 * Calculate cost from litres
 */
function calculateCost(litres, includeDailyFixed = true) {
    const variableCost = litres * PRICING.ratePerLitre;
    return includeDailyFixed ? variableCost + PRICING.dailyFixedCharge : variableCost;
}

/**
 * Format currency
 */
function formatCurrency(amount) {
    return '£' + amount.toFixed(2);
}

/**
 * Format number with locale
 */
function formatNumber(num) {
    return Math.round(num).toLocaleString();
}

/**
 * Update gauge visualization
 */
function updateGauge(value) {
    const gaugeArc = document.getElementById('gauge-arc');
    if (!gaugeArc) return;

    // Calculate percentage (cap at 100%)
    const percentage = Math.min(value / GAUGE.maxValue, 1);
    const dashOffset = GAUGE.arcLength * (1 - percentage);

    // Animate the gauge fill
    gaugeArc.style.strokeDashoffset = dashOffset;

    // Update color based on threshold
    if (value > GAUGE.threshold) {
        gaugeArc.style.stroke = COLORS.danger;
    } else if (value > GAUGE.threshold * 0.8) {
        gaugeArc.style.stroke = COLORS.warning;
    } else {
        gaugeArc.style.stroke = COLORS.waterPrimary;
    }
}

/**
 * Update LED indicator status
 */
function updateLedStatus(status) {
    const led = document.getElementById('led-status');
    if (!led) return;

    // Remove existing status classes
    led.classList.remove('warning', 'danger');

    switch(status) {
        case 'healthy':
            // Default green, no additional class needed
            break;
        case 'degraded':
            led.classList.add('warning');
            break;
        case 'unhealthy':
        case 'error':
            led.classList.add('danger');
            break;
    }
}

/**
 * Add value update animation
 */
function animateValueUpdate(elementId) {
    const element = document.getElementById(elementId);
    if (!element) return;

    element.classList.add('value-update');
    setTimeout(() => element.classList.remove('value-update'), 500);
}

/**
 * Initialize the dashboard
 */
async function initDashboard() {
    // Set default date for hourly picker (3 days ago due to data delay)
    const hourlyDatePicker = document.getElementById('hourly-date');
    const latestAvailable = new Date();
    latestAvailable.setDate(latestAvailable.getDate() - 3);
    hourlyDatePicker.value = latestAvailable.toISOString().split('T')[0];

    // Add event listeners
    setupEventListeners();

    // Load all data
    await Promise.all([
        checkHealth(),
        loadSummary(),
        loadDailyData(30),
        loadHourlyData(hourlyDatePicker.value),
        loadMonthlyData(),
        loadAlerts()
    ]);

    // Set up auto-refresh (every 5 minutes)
    setInterval(refreshData, 5 * 60 * 1000);
}

/**
 * Set up event listeners
 */
function setupEventListeners() {
    // Range buttons for daily chart (updated selector for new HTML)
    document.querySelectorAll('.chart-controls .control-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            document.querySelectorAll('.chart-controls .control-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            await loadDailyData(parseInt(e.target.dataset.range));
        });
    });

    // Hourly date picker
    document.getElementById('hourly-date').addEventListener('change', async (e) => {
        await loadHourlyData(e.target.value);
    });
}

/**
 * Check service health
 */
async function checkHealth() {
    try {
        const response = await fetch(`${API_BASE}/health`);
        const data = await response.json();

        const statusText = document.getElementById('health-status');
        statusText.textContent = data.status.charAt(0).toUpperCase() + data.status.slice(1);

        // Update LED indicator
        updateLedStatus(data.status);

        // Update last sync time
        if (data.last_sync?.daily) {
            const syncDate = new Date(data.last_sync.daily);
            const timeStr = syncDate.toLocaleTimeString('en-GB', {
                hour: '2-digit',
                minute: '2-digit'
            });
            const dateStr = syncDate.toLocaleDateString('en-GB', {
                day: 'numeric',
                month: 'short'
            });
            document.getElementById('last-sync').textContent = `${dateStr} ${timeStr}`;
        }
    } catch (error) {
        console.error('Health check failed:', error);
        const statusText = document.getElementById('health-status');
        statusText.textContent = 'Error';
        updateLedStatus('error');
    }
}

/**
 * Load usage summary
 */
async function loadSummary() {
    try {
        const response = await fetch(`${API_BASE}/api/usage/summary?days=7`);
        const data = await response.json();

        if (data.success) {
            const summary = data.data;

            // Update 7-day average
            document.getElementById('avg-usage').textContent = formatNumber(summary.average_daily);
            animateValueUpdate('avg-usage');

            // Calculate daily cost from 7-day average
            const dailyCost = calculateCost(summary.average_daily);
            document.getElementById('daily-cost').textContent = formatCurrency(dailyCost);

            // Calculate annual estimate
            const annualCost = dailyCost * 365;
            document.getElementById('annual-cost').textContent = formatCurrency(annualCost);

            // Get latest day's usage
            const dailyResponse = await fetch(`${API_BASE}/api/usage/daily?limit=1`);
            const dailyData = await dailyResponse.json();
            if (dailyData.success && dailyData.data.length > 0) {
                const latestDay = dailyData.data[0];
                const todayUsage = Math.round(latestDay.usage_litres);
                document.getElementById('today-usage').textContent = formatNumber(todayUsage);
                animateValueUpdate('today-usage');

                // Display which date this reading is from
                const latestDate = new Date(latestDay.date);
                const dateStr = latestDate.toLocaleDateString('en-GB', {
                    weekday: 'short',
                    day: 'numeric',
                    month: 'short'
                });
                document.getElementById('latest-date').textContent = dateStr;

                // Update gauge
                updateGauge(todayUsage);
            }

            // Get this month's total and calculate costs
            const monthlyResponse = await fetch(`${API_BASE}/api/usage/monthly`);
            const monthlyData = await monthlyResponse.json();
            if (monthlyData.success && monthlyData.data.length > 0) {
                const currentMonth = monthlyData.data[0];
                const monthLitres = currentMonth.total_litres;
                const daysRecorded = currentMonth.days_recorded;

                // Update monthly usage
                document.getElementById('month-usage').textContent = formatNumber(monthLitres);
                animateValueUpdate('month-usage');

                // Month to date cost
                const monthCost = (monthLitres * PRICING.ratePerLitre) +
                                  (PRICING.dailyFixedCharge * daysRecorded);
                document.getElementById('month-cost').textContent = formatCurrency(monthCost);

                // Projected monthly cost
                const daysInMonth = new Date(
                    new Date().getFullYear(),
                    new Date().getMonth() + 1,
                    0
                ).getDate();
                const projectedLitres = (monthLitres / daysRecorded) * daysInMonth;
                const projectedCost = (projectedLitres * PRICING.ratePerLitre) +
                                      (PRICING.dailyFixedCharge * daysInMonth);
                document.getElementById('projected-cost').textContent = formatCurrency(projectedCost);
            }
        }
    } catch (error) {
        console.error('Failed to load summary:', error);
    }
}

/**
 * Load daily usage data
 */
async function loadDailyData(days) {
    try {
        const endDate = new Date();
        const startDate = new Date();
        startDate.setDate(startDate.getDate() - days);

        const response = await fetch(
            `${API_BASE}/api/usage/daily?start_date=${startDate.toISOString().split('T')[0]}&end_date=${endDate.toISOString().split('T')[0]}&limit=${days}`
        );
        const data = await response.json();

        if (data.success) {
            renderDailyChart(data.data);
        }
    } catch (error) {
        console.error('Failed to load daily data:', error);
    }
}

/**
 * Render daily usage chart - Dark theme
 */
function renderDailyChart(data) {
    const ctx = document.getElementById('daily-chart').getContext('2d');

    // Sort by date ascending
    const sortedData = [...data].sort((a, b) =>
        new Date(a.date) - new Date(b.date)
    );

    const labels = sortedData.map(d => {
        const date = new Date(d.date);
        return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
    });
    const values = sortedData.map(d => d.usage_litres);
    const threshold = 800;

    if (dailyChart) {
        dailyChart.destroy();
    }

    dailyChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Daily Usage (L)',
                    data: values,
                    backgroundColor: values.map(v =>
                        v > threshold ? COLORS.danger : COLORS.waterPrimary
                    ),
                    borderRadius: 6,
                    borderSkipped: false
                },
                {
                    label: 'Threshold (800L)',
                    data: labels.map(() => threshold),
                    type: 'line',
                    borderColor: COLORS.thresholdLine,
                    borderDash: [6, 4],
                    borderWidth: 2,
                    pointRadius: 0,
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: COLORS.textSecondary,
                        font: { family: 'Outfit', size: 12 },
                        boxWidth: 12,
                        padding: 16
                    }
                },
                tooltip: {
                    backgroundColor: COLORS.bgCard,
                    titleColor: COLORS.textPrimary,
                    bodyColor: COLORS.textSecondary,
                    borderColor: COLORS.bgElevated,
                    borderWidth: 1,
                    padding: 12,
                    titleFont: { family: 'JetBrains Mono', size: 12 },
                    bodyFont: { family: 'JetBrains Mono', size: 11 },
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ${formatNumber(context.raw)} L`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: COLORS.textMuted,
                        font: { family: 'JetBrains Mono', size: 10 },
                        maxRotation: 45
                    }
                },
                y: {
                    beginAtZero: true,
                    grid: {
                        color: COLORS.gridColor,
                        drawBorder: false
                    },
                    ticks: {
                        color: COLORS.textMuted,
                        font: { family: 'JetBrains Mono', size: 10 }
                    },
                    title: {
                        display: true,
                        text: 'Litres',
                        color: COLORS.textMuted,
                        font: { family: 'Outfit', size: 11 }
                    }
                }
            }
        }
    });
}

/**
 * Load hourly usage data
 */
async function loadHourlyData(date) {
    try {
        const response = await fetch(`${API_BASE}/api/usage/hourly?date=${date}`);
        const data = await response.json();

        if (data.success) {
            renderHourlyChart(data.data);
        }
    } catch (error) {
        console.error('Failed to load hourly data:', error);
    }
}

/**
 * Render hourly usage chart - Dark theme
 */
function renderHourlyChart(data) {
    const ctx = document.getElementById('hourly-chart').getContext('2d');

    const hourlyData = data.hourly || [];
    const labels = hourlyData.map(h => `${String(h.hour).padStart(2, '0')}:00`);
    const values = hourlyData.map(h => h.usage_litres);

    if (hourlyChart) {
        hourlyChart.destroy();
    }

    // Create gradient
    const gradient = ctx.createLinearGradient(0, 0, 0, 280);
    gradient.addColorStop(0, 'rgba(6, 182, 212, 0.3)');
    gradient.addColorStop(1, 'rgba(6, 182, 212, 0.02)');

    hourlyChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Hourly Usage (L)',
                data: values,
                borderColor: COLORS.waterLight,
                backgroundColor: gradient,
                fill: true,
                tension: 0.4,
                pointRadius: 3,
                pointBackgroundColor: COLORS.waterLight,
                pointBorderColor: COLORS.bgCard,
                pointBorderWidth: 2,
                pointHoverRadius: 6,
                pointHoverBackgroundColor: COLORS.waterLight,
                pointHoverBorderColor: COLORS.textPrimary,
                pointHoverBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: COLORS.bgCard,
                    titleColor: COLORS.textPrimary,
                    bodyColor: COLORS.textSecondary,
                    borderColor: COLORS.bgElevated,
                    borderWidth: 1,
                    padding: 12,
                    titleFont: { family: 'JetBrains Mono', size: 12 },
                    bodyFont: { family: 'JetBrains Mono', size: 11 },
                    callbacks: {
                        title: function(context) {
                            return `${data.date} at ${context[0].label}`;
                        },
                        label: function(context) {
                            return `Usage: ${context.raw} L`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: COLORS.gridColor,
                        drawBorder: false
                    },
                    ticks: {
                        color: COLORS.textMuted,
                        font: { family: 'JetBrains Mono', size: 10 },
                        maxTicksLimit: 12
                    }
                },
                y: {
                    beginAtZero: true,
                    grid: {
                        color: COLORS.gridColor,
                        drawBorder: false
                    },
                    ticks: {
                        color: COLORS.textMuted,
                        font: { family: 'JetBrains Mono', size: 10 }
                    },
                    title: {
                        display: true,
                        text: 'Litres',
                        color: COLORS.textMuted,
                        font: { family: 'Outfit', size: 11 }
                    }
                }
            },
            interaction: {
                intersect: false,
                mode: 'index'
            }
        }
    });
}

/**
 * Load monthly usage data
 */
async function loadMonthlyData() {
    try {
        const response = await fetch(`${API_BASE}/api/usage/monthly`);
        const data = await response.json();

        if (data.success) {
            renderMonthlyChart(data.data);
        }
    } catch (error) {
        console.error('Failed to load monthly data:', error);
    }
}

/**
 * Render monthly usage chart - Dark theme
 */
function renderMonthlyChart(data) {
    const ctx = document.getElementById('monthly-chart').getContext('2d');

    // Sort by month
    const sortedData = [...data].sort((a, b) =>
        new Date(a.month + '-01') - new Date(b.month + '-01')
    );

    const labels = sortedData.map(d => {
        const date = new Date(d.month + '-01');
        return date.toLocaleDateString('en-GB', { month: 'short', year: '2-digit' });
    });
    const totals = sortedData.map(d => d.total_litres);
    const averages = sortedData.map(d => d.average_daily);

    if (monthlyChart) {
        monthlyChart.destroy();
    }

    monthlyChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Total Usage (L)',
                    data: totals,
                    backgroundColor: COLORS.waterPrimary,
                    borderRadius: 6,
                    borderSkipped: false,
                    yAxisID: 'y'
                },
                {
                    label: 'Daily Average (L)',
                    data: averages,
                    type: 'line',
                    borderColor: COLORS.healthy,
                    backgroundColor: COLORS.healthy,
                    pointRadius: 5,
                    pointBackgroundColor: COLORS.healthy,
                    pointBorderColor: COLORS.bgCard,
                    pointBorderWidth: 2,
                    pointHoverRadius: 7,
                    tension: 0.3,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: COLORS.textSecondary,
                        font: { family: 'Outfit', size: 12 },
                        boxWidth: 12,
                        padding: 16
                    }
                },
                tooltip: {
                    backgroundColor: COLORS.bgCard,
                    titleColor: COLORS.textPrimary,
                    bodyColor: COLORS.textSecondary,
                    borderColor: COLORS.bgElevated,
                    borderWidth: 1,
                    padding: 12,
                    titleFont: { family: 'JetBrains Mono', size: 12 },
                    bodyFont: { family: 'JetBrains Mono', size: 11 }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: COLORS.textMuted,
                        font: { family: 'JetBrains Mono', size: 10 }
                    }
                },
                y: {
                    type: 'linear',
                    position: 'left',
                    beginAtZero: true,
                    grid: {
                        color: COLORS.gridColor,
                        drawBorder: false
                    },
                    ticks: {
                        color: COLORS.textMuted,
                        font: { family: 'JetBrains Mono', size: 10 }
                    },
                    title: {
                        display: true,
                        text: 'Total (L)',
                        color: COLORS.textMuted,
                        font: { family: 'Outfit', size: 11 }
                    }
                },
                y1: {
                    type: 'linear',
                    position: 'right',
                    beginAtZero: true,
                    grid: {
                        drawOnChartArea: false
                    },
                    ticks: {
                        color: COLORS.textMuted,
                        font: { family: 'JetBrains Mono', size: 10 }
                    },
                    title: {
                        display: true,
                        text: 'Avg Daily (L)',
                        color: COLORS.textMuted,
                        font: { family: 'Outfit', size: 11 }
                    }
                }
            }
        }
    });
}

/**
 * Load alerts
 */
async function loadAlerts() {
    try {
        const response = await fetch(`${API_BASE}/api/alerts?limit=10`);
        const data = await response.json();

        if (data.success) {
            renderAlerts(data.data);

            // Update alert count
            const unacknowledged = data.data.filter(a => !a.acknowledged).length;
            document.getElementById('alert-count').textContent = unacknowledged;

            // Update badge
            const badge = document.getElementById('alerts-badge');
            const badgeCount = document.getElementById('alerts-badge-count');
            if (badge && badgeCount) {
                badgeCount.textContent = unacknowledged;
                if (unacknowledged === 0) {
                    badge.classList.add('no-alerts');
                } else {
                    badge.classList.remove('no-alerts');
                }
            }

            // Update alert card styling
            const alertCard = document.getElementById('alert-card');
            if (alertCard) {
                if (unacknowledged === 0) {
                    alertCard.classList.add('no-alerts');
                } else {
                    alertCard.classList.remove('no-alerts');
                }
            }
        }
    } catch (error) {
        console.error('Failed to load alerts:', error);
        document.getElementById('alerts-list').innerHTML =
            '<div class="loading-state"><span>Failed to load alerts</span></div>';
    }
}

/**
 * Render alerts list
 */
function renderAlerts(alerts) {
    const container = document.getElementById('alerts-list');

    if (alerts.length === 0) {
        container.innerHTML = `
            <div class="no-alerts-message">
                <div class="no-alerts-icon">✓</div>
                <p>All systems operational. No alerts to display.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = alerts.map(alert => `
        <div class="alert-item ${alert.acknowledged ? 'acknowledged' : ''}">
            <div class="alert-info">
                <div class="alert-type">
                    <span class="icon">${getAlertIcon(alert.alert_type)}</span>
                    ${formatAlertType(alert.alert_type)}
                </div>
                <div class="alert-message">${alert.message}</div>
            </div>
            <div class="alert-date">
                ${formatAlertDate(alert.alert_date)}
                <span class="alert-status">${alert.acknowledged ? 'Acknowledged' : 'Active'}</span>
            </div>
        </div>
    `).join('');
}

/**
 * Get alert icon based on type
 */
function getAlertIcon(type) {
    const icons = {
        'spike': '⚡',
        'verification_mismatch': '⚠',
        'sync_error': '⟳',
        'data_unavailable': '○',
        'data_available': '●'
    };
    return icons[type] || '⚠';
}

/**
 * Format alert type for display
 */
function formatAlertType(type) {
    const types = {
        'spike': 'High Usage Spike',
        'verification_mismatch': 'Data Verification Issue',
        'sync_error': 'Sync Error',
        'data_unavailable': 'Data Unavailable',
        'data_available': 'Data Available'
    };
    return types[type] || type;
}

/**
 * Format alert date
 */
function formatAlertDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-GB', {
        day: 'numeric',
        month: 'short',
        year: '2-digit'
    });
}

/**
 * Refresh all data
 */
async function refreshData() {
    console.log('Refreshing data...');
    await Promise.all([
        checkHealth(),
        loadSummary(),
        loadAlerts()
    ]);
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initDashboard);
