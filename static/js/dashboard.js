/**
 * Thames Water Dashboard JavaScript
 */

// API base URL
const API_BASE = '';

// Chart instances
let dailyChart = null;
let hourlyChart = null;
let monthlyChart = null;

// Color palette
const COLORS = {
    primary: '#0066cc',
    secondary: '#00a6ed',
    success: '#28a745',
    warning: '#ffc107',
    danger: '#dc3545',
    threshold: 'rgba(220, 53, 69, 0.3)'
};

// Thames Water pricing (from Dec 2025 bill)
// Fresh water: £2.4743/m³, Wastewater: £1.5480/m³
// Fixed charges: Fresh £31.37/179 days, Waste £63.86/179 days
const PRICING = {
    ratePerLitre: 0.0040223,  // £4.0223 per m³ = £0.0040223 per litre
    dailyFixedCharge: 0.532   // (£31.37 + £63.86) / 179 days
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
 * Initialize the dashboard
 */
async function initDashboard() {
    // Set default date for hourly picker
    // Thames Water has a ~3 day delay for data availability
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
    // Range buttons for daily chart
    document.querySelectorAll('.chart-controls .btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            document.querySelectorAll('.chart-controls .btn').forEach(b => b.classList.remove('active'));
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

        const statusBadge = document.getElementById('health-status');
        statusBadge.textContent = data.status.charAt(0).toUpperCase() + data.status.slice(1);
        statusBadge.className = `status-badge ${data.status}`;

        // Update last sync
        if (data.last_sync?.daily) {
            const syncDate = new Date(data.last_sync.daily);
            document.getElementById('last-sync').textContent =
                `Last sync: ${syncDate.toLocaleString()}`;
        }
    } catch (error) {
        console.error('Health check failed:', error);
        const statusBadge = document.getElementById('health-status');
        statusBadge.textContent = 'Error';
        statusBadge.className = 'status-badge unhealthy';
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

            // Update usage cards
            document.getElementById('avg-usage').textContent =
                Math.round(summary.average_daily);

            // Calculate daily cost from 7-day average
            const dailyCost = calculateCost(summary.average_daily);
            document.getElementById('daily-cost').textContent = formatCurrency(dailyCost);

            // Calculate annual estimate from 7-day average
            const annualCost = dailyCost * 365;
            document.getElementById('annual-cost').textContent = formatCurrency(annualCost);

            // Get today's usage
            const dailyResponse = await fetch(`${API_BASE}/api/usage/daily?limit=1`);
            const dailyData = await dailyResponse.json();
            if (dailyData.success && dailyData.data.length > 0) {
                document.getElementById('today-usage').textContent =
                    Math.round(dailyData.data[0].usage_litres);
            }

            // Get this month's total and calculate costs
            const monthlyResponse = await fetch(`${API_BASE}/api/usage/monthly`);
            const monthlyData = await monthlyResponse.json();
            if (monthlyData.success && monthlyData.data.length > 0) {
                const currentMonth = monthlyData.data[0];
                const monthLitres = currentMonth.total_litres;
                const daysRecorded = currentMonth.days_recorded;

                // Update usage
                document.getElementById('month-usage').textContent =
                    Math.round(monthLitres).toLocaleString();

                // Month to date cost (variable cost + fixed charge per day recorded)
                const monthCost = (monthLitres * PRICING.ratePerLitre) +
                                  (PRICING.dailyFixedCharge * daysRecorded);
                document.getElementById('month-cost').textContent = formatCurrency(monthCost);

                // Projected monthly cost (extrapolate to full month)
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
 * Render daily usage chart
 */
function renderDailyChart(data) {
    const ctx = document.getElementById('daily-chart').getContext('2d');

    // Sort by date ascending
    const sortedData = [...data].sort((a, b) =>
        new Date(a.date) - new Date(b.date)
    );

    const labels = sortedData.map(d => d.date);
    const values = sortedData.map(d => d.usage_litres);
    const threshold = 800; // Spike threshold

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
                        v > threshold ? COLORS.danger : COLORS.primary
                    ),
                    borderRadius: 4
                },
                {
                    label: 'Threshold',
                    data: labels.map(() => threshold),
                    type: 'line',
                    borderColor: COLORS.danger,
                    borderDash: [5, 5],
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
                    position: 'top'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ${context.raw} L`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    }
                },
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Litres'
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
 * Render hourly usage chart
 */
function renderHourlyChart(data) {
    const ctx = document.getElementById('hourly-chart').getContext('2d');

    const hourlyData = data.hourly || [];
    const labels = hourlyData.map(h => `${h.hour}:00`);
    const values = hourlyData.map(h => h.usage_litres);

    if (hourlyChart) {
        hourlyChart.destroy();
    }

    hourlyChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Hourly Usage (L)',
                data: values,
                borderColor: COLORS.secondary,
                backgroundColor: 'rgba(0, 166, 237, 0.1)',
                fill: true,
                tension: 0.3,
                pointRadius: 4,
                pointBackgroundColor: COLORS.secondary
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
                    callbacks: {
                        title: function(context) {
                            return `${data.date} ${context[0].label}`;
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
                        display: false
                    }
                },
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Litres'
                    }
                }
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
 * Render monthly usage chart
 */
function renderMonthlyChart(data) {
    const ctx = document.getElementById('monthly-chart').getContext('2d');

    // Sort by month
    const sortedData = [...data].sort((a, b) =>
        new Date(a.month + '-01') - new Date(b.month + '-01')
    );

    const labels = sortedData.map(d => d.month);
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
                    backgroundColor: COLORS.primary,
                    borderRadius: 4,
                    yAxisID: 'y'
                },
                {
                    label: 'Daily Average (L)',
                    data: averages,
                    type: 'line',
                    borderColor: COLORS.success,
                    backgroundColor: COLORS.success,
                    pointRadius: 5,
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
                    position: 'top'
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    }
                },
                y: {
                    type: 'linear',
                    position: 'left',
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Total (L)'
                    }
                },
                y1: {
                    type: 'linear',
                    position: 'right',
                    beginAtZero: true,
                    grid: {
                        drawOnChartArea: false
                    },
                    title: {
                        display: true,
                        text: 'Avg Daily (L)'
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

            const alertCard = document.getElementById('alert-card');
            if (unacknowledged === 0) {
                alertCard.classList.add('no-alerts');
            } else {
                alertCard.classList.remove('no-alerts');
            }
        }
    } catch (error) {
        console.error('Failed to load alerts:', error);
        document.getElementById('alerts-list').innerHTML =
            '<p class="loading">Failed to load alerts</p>';
    }
}

/**
 * Render alerts list
 */
function renderAlerts(alerts) {
    const container = document.getElementById('alerts-list');

    if (alerts.length === 0) {
        container.innerHTML = '<p class="no-alerts-message">No alerts to display</p>';
        return;
    }

    container.innerHTML = alerts.map(alert => `
        <div class="alert-item ${alert.acknowledged ? 'acknowledged' : ''}">
            <div class="alert-info">
                <div class="alert-type">
                    ${alert.alert_type === 'spike' ? '⚠️' : '🔔'}
                    ${formatAlertType(alert.alert_type)}
                </div>
                <div class="alert-message">${alert.message}</div>
            </div>
            <div class="alert-date">
                ${new Date(alert.alert_date).toLocaleDateString()}<br>
                <small>${alert.acknowledged ? 'Acknowledged' : 'Active'}</small>
            </div>
        </div>
    `).join('');
}

/**
 * Format alert type for display
 */
function formatAlertType(type) {
    const types = {
        'spike': 'High Usage Alert',
        'verification_mismatch': 'Data Verification Issue',
        'sync_error': 'Sync Error'
    };
    return types[type] || type;
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
