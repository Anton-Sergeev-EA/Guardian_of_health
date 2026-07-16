/**
 * FocusGuardian - Dashboard Client Engine (v2.2)
 * Handles Socket.IO connections, smart fallback polling, Chart.js 4 rendering,
 * on-the-fly internationalization (RU/EN), and interactive dashboard controls.
 */

// ==========================================================================
// CONFIGURATION & TRANSLATIONS
// ==========================================================================
const CONFIG = {
    socketURL: window.location.origin,
    maxHistory: 50,
    pollInterval: 1500
};

const TRANSLATIONS = {
    ru: {
        initializing: 'Инициализация...',
        connected: '🟢 Подключено',
        disconnected: '🔴 Отключено',
        btn_pause: 'Пауза',
        btn_resume: 'Продолжить',
        btn_report: 'Отчет',
        listening: 'Слушаю...',
        label_posture: 'Осанка',
        label_blinks: 'Моргания',
        label_slouches: 'Наклоны',
        label_critical: 'Критические',
        chart_title: 'История осанки',
        chart_limit: 'Последние 50',
        voice_commands: 'Голосовые команды',
        cmd_status: 'Статус',
        cmd_pause: 'Пауза',
        cmd_resume: 'Старт',
        cmd_report: 'Отчет',
        cmd_reset: 'Сброс',
        cmd_help: 'Инфо',
        privacy_note: 'Все вычисления производятся локально. Данные не передаются в облако.',
        session_prefix: 'Сессия: ',
        no_face: '👤 Нет лица',
        warning: '🤔 Внимание',
        critical: '⚠️ Сутулость!',
        good: '✅ Отлично'
    },
    en: {
        initializing: 'Initializing...',
        connected: '🟢 Connected',
        disconnected: '🔴 Disconnected',
        btn_pause: 'Pause',
        btn_resume: 'Resume',
        btn_report: 'Report',
        listening: 'Listening...',
        label_posture: 'Posture',
        label_blinks: 'Blinks',
        label_slouches: 'Slouches',
        label_critical: 'Critical',
        chart_title: 'Posture History',
        chart_limit: 'Last 50',
        voice_commands: 'Voice Commands',
        cmd_status: 'Status',
        cmd_pause: 'Pause',
        cmd_resume: 'Resume',
        cmd_report: 'Report',
        cmd_reset: 'Reset',
        cmd_help: 'Help',
        privacy_note: 'All processing is local. No data sent to cloud.',
        session_prefix: 'Session: ',
        no_face: '👤 No face',
        warning: '🤔 Warning',
        critical: '⚠️ Critical!',
        good: '✅ Good'
    }
};

// ==========================================================================
// STATE
// ==========================================================================
let socket = null;
let chart = null;
let currentLang = 'ru';
let pollTimer = null;
let lastUpdateTime = 0;

// ==========================================================================
// DOM HELPER
// ==========================================================================
const $ = id => document.getElementById(id);

// ==========================================================================
// INITIALIZATION
// ==========================================================================
document.addEventListener('DOMContentLoaded', () => {
    console.log('🧘 FocusGuardian Dashboard JS initialized');
    applyLanguage();
    initChart();
    loadHistory();
    initSocket();
    
    // Fallback polling starts immediately to support robust connections
    pollTimer = setInterval(smartPoll, CONFIG.pollInterval);
    
    // Bind global keyboard UI actions
    bindEvents();
});

// ==========================================================================
// UI EVENT BINDINGS
// ==========================================================================
function bindEvents() {
    // Keyboard Hotkeys
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === ' ') {
            e.preventDefault();
            togglePause();
        }
        if (e.ctrlKey && e.key === 'r') {
            e.preventDefault();
            generateReport();
        }
    });

    // Clean resource release on browser close
    window.addEventListener('beforeunload', () => {
        if (socket) socket.disconnect();
        if (pollTimer) clearInterval(pollTimer);
    });
}

// ==========================================================================
// MULTI-LANGUAGE ENGINE
// ==========================================================================
function toggleLanguage() {
    currentLang = currentLang === 'ru' ? 'en' : 'ru';
    const langBtn = $('lang-btn');
    if (langBtn) langBtn.textContent = currentLang.toUpperCase();
    applyLanguage();
}

function applyLanguage() {
    const t = TRANSLATIONS[currentLang];
    document.querySelectorAll('[data-i18n]').forEach(element => {
        const key = element.getAttribute('data-i18n');
        if (t[key]) {
            element.textContent = t[key];
        }
    });
}

// ==========================================================================
// SOCKET.IO (Main stream channel)
// ==========================================================================
function initSocket() {
    socket = io(CONFIG.socketURL, {
        transports: ['websocket', 'polling'],
        reconnection: true,
        timeout: 5000
    });

    socket.on('connect', () => {
        console.log('✅ Socket connected successfully');
        const statusText = $('status-text');
        if (statusText) {
            statusText.textContent = TRANSLATIONS[currentLang].connected;
            statusText.style.color = 'var(--color-good)';
        }
        socket.emit('subscribe', { channels: ['status'] });
    });

    socket.on('disconnect', () => {
        console.warn('❌ Socket disconnected');
        const statusText = $('status-text');
        if (statusText) {
            statusText.textContent = TRANSLATIONS[currentLang].disconnected;
            statusText.style.color = 'var(--color-critical)';
        }
    });

    socket.on('status_update', (data) => {
        lastUpdateTime = Date.now();
        updateDashboard(data);
    });

    socket.on('command_result', (data) => {
        if (data.status) {
            showToast(`Command: ${data.status}`, 'success');
        }
    });
}

// ==========================================================================
// SMART FALLBACK POLLING
// ==========================================================================
function smartPoll() {
    // Poll REST API ONLY if socket is disconnected or hasn't updated state for 2 seconds
    if (!socket || !socket.connected || (Date.now() - lastUpdateTime > 2000)) {
        fetch('/api/status')
            .then(r => r.json())
            .then(data => {
                updateDashboard(data);
            })
            .catch(() => {});
    }
}

// ==========================================================================
// CHART DEFINITION (Chart.js 4.x)
// ==========================================================================
function initChart() {
    const canvas = document.getElementById('posture-chart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Spine (Спина)',
                    data: [],
                    borderColor: '#00ff88',
                    backgroundColor: 'rgba(0,255,136,0.08)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 1.5,
                    borderWidth: 2
                },
                {
                    label: 'Neck (Шея)',
                    data: [],
                    borderColor: '#ffdd00',
                    backgroundColor: 'rgba(255,221,0,0.08)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 1.5,
                    borderWidth: 2,
                    borderDash: [4, 4]
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: {
                        color: '#8888aa',
                        font: { size: 9 },
                        boxWidth: 12,
                        padding: 8
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#555', font: { size: 8 }, maxTicksLimit: 8 },
                    grid: { color: 'rgba(255,255,255,0.03)' }
                },
                y: {
                    min: 0,
                    max: 35,
                    ticks: { color: '#555', font: { size: 8 } },
                    grid: { color: 'rgba(255,255,255,0.03)' }
                }
            },
            interaction: {
                intersect: false,
                mode: 'nearest'
            }
        }
    });
}

// ==========================================================================
// DASHBOARD VIEW UPDATES
// ==========================================================================
function updateDashboard(data) {
    const posture = data.posture || {};
    const eyes = data.eyes || {};
    const session = data.session || {};
    const t = TRANSLATIONS[currentLang];

    // Status Dot dynamic styling
    const statusDot = $('status-dot');
    if (statusDot) {
        if (!data.face_detected) {
            statusDot.className = 'status-dot status-offline';
        } else if (posture.is_slouching && posture.severity === 'critical') {
            statusDot.className = 'status-dot status-critical';
        } else if (posture.is_slouching) {
            statusDot.className = 'status-dot status-warning';
        } else {
            statusDot.className = 'status-dot status-good';
        }
    }

    // Posture status description text
    const postureStatus = $('posture-status');
    if (postureStatus) {
        if (!data.face_detected) {
            postureStatus.textContent = t.no_face;
            postureStatus.style.color = '#666';
        } else if (posture.is_slouching) {
            postureStatus.textContent = posture.severity === 'critical' ? t.critical : t.warning;
            postureStatus.style.color = posture.severity === 'critical' ? 'var(--color-critical)' : 'var(--color-warning)';
        } else {
            postureStatus.textContent = t.good;
            postureStatus.style.color = 'var(--color-good)';
        }
    }

    // Dynamic stats display
    const blinkCount = $('blink-count');
    if (blinkCount) blinkCount.textContent = eyes.blinks || 0;
    
    const slouchCount = $('slouch-count');
    if (slouchCount) slouchCount.textContent = session.slouches || 0;
    
    const criticalCount = $('critical-count');
    if (criticalCount) criticalCount.textContent = session.critical_slouches || 0;

    // Camera FPS display
    const fpsBadge = $('fps-badge');
    if (fpsBadge) fpsBadge.textContent = `📹 ${data.fps || 0} FPS`;

    // FIX: Parse raw Unix Timestamp (seconds) properly using milliseconds conversion (* 1000)
    const uptimeBadge = $('uptime-badge');
    if (uptimeBadge && data.timestamp) {
        const startTimeMs = new Date(data.timestamp * 1000).getTime();
        const uptimeMinutes = Math.max(0, Math.floor((Date.now() - startTimeMs) / 60000));
        uptimeBadge.textContent = `⏱️ ${uptimeMinutes}${currentLang === 'ru' ? 'м' : 'm'}`;
    }

    // Update Session ID
    const sessionInfo = $('session-info');
    if (sessionInfo) {
        sessionInfo.textContent = `${t.session_prefix}${data.session_id || 'active'}`;
    }

    // Push coordinates safely to chart pipeline
    updateChart(data);
}

// ==========================================================================
// CHART RENDERING ENGINE
// ==========================================================================
let lastChartTimeStr = '';
function updateChart(data) {
    if (!chart) return;
    
    const posture = data.posture || {};
    const timeStr = new Date().toLocaleTimeString();
    
    // Prevent duplicate points being written during the exact same second
    if (timeStr === lastChartTimeStr) return;
    lastChartTimeStr = timeStr;
    
    chart.data.labels.push(timeStr);
    chart.data.datasets[0].data.push(posture.angle || 0);
    chart.data.datasets[1].data.push(posture.neck_angle || 0);
    
    // Maintain maximum display capacity limit
    if (chart.data.labels.length > CONFIG.maxHistory) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
        chart.data.datasets[1].data.shift();
    }
    
    chart.update('none');
}

// ==========================================================================
// HISTORICAL DATA LOADING
// ==========================================================================
function loadHistory() {
    fetch('/api/history?limit=50')
        .then(r => r.json())
        .then(data => {
            if (data.length > 0 && chart) {
                chart.data.labels = [];
                chart.data.datasets[0].data = [];
                chart.data.datasets[1].data = [];

                data.reverse().forEach(item => {
                    const time = new Date(item.timestamp * 1000).toLocaleTimeString();
                    chart.data.labels.push(time);
                    chart.data.datasets[0].data.push(item.spine_angle || 0);
                    chart.data.datasets[1].data.push(item.neck_angle || 0);
                });
                
                if (chart.data.labels.length > CONFIG.maxHistory) {
                    chart.data.labels = chart.data.labels.slice(-CONFIG.maxHistory);
                    chart.data.datasets[0].data = chart.data.datasets[0].data.slice(-CONFIG.maxHistory);
                    chart.data.datasets[1].data = chart.data.datasets[1].data.slice(-CONFIG.maxHistory);
                }
                chart.update();
            }
        })
        .catch(() => {});
}

// ==========================================================================
// ACTION TRIGGERS & COMMAND API HANDLERS
// ==========================================================================
function sendCommand(command) {
    fetch('/api/voice/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: command })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'command_processed') {
            showToast(`🎤 Command: ${command}`, 'success');
            showVoiceOverlay(command);
        } else if (data.error) {
            showToast(`❌ ${data.error}`, 'danger');
        }
    })
    .catch(() => showToast('❌ Command processing failed', 'danger'));
}

function togglePause() {
    const pauseBtn = $('pause-btn');
    if (!pauseBtn) return;

    const isCurrentlyPaused = pauseBtn.innerHTML.includes('Resume') || pauseBtn.innerHTML.includes('Продолжить');
    const cmd = isCurrentlyPaused ? 'resume' : 'pause';
    
    fetch('/api/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: cmd })
    })
    .then(r => r.json())
    .then(data => {
        const t = TRANSLATIONS[currentLang];
        if (data.status === 'paused') {
            pauseBtn.innerHTML = `<i class="fas fa-play"></i> ${t.btn_resume}`;
            showToast('⏸️ Monitor Paused', 'warning');
        } else if (data.status === 'resumed') {
            pauseBtn.innerHTML = `<i class="fas fa-pause"></i> ${t.btn_pause}`;
            showToast('▶️ Monitor Resumed', 'success');
        }
    });
}

function generateReport() {
    fetch('/api/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: 'report' })
    })
    .then(() => showToast('📊 Statistics report compiled', 'info'));
}

function exportData() {
    window.location.href = '/api/export';
    showToast('📥 Downloading sessions csv...', 'info');
}

// ==========================================================================
// NOTIFICATIONS & VOICE OVERLAYS
// ==========================================================================
function showVoiceOverlay(text) {
    const voiceOverlay = $('voice-overlay');
    const voiceText = $('voice-text');
    if (!voiceOverlay || !voiceText) return;

    voiceOverlay.style.display = 'block';
    voiceText.innerHTML = `<i class="fas fa-microphone fa-pulse me-2"></i> Command: ${text}`;
    setTimeout(() => {
        voiceOverlay.style.display = 'none';
    }, 1500);
}

function showToast(message, type = 'info') {
    const colors = {
        success: '#00ff88',
        info: '#00aaff',
        warning: '#ffdd00',
        danger: '#ff0044'
    };
    const color = colors[type] || colors.info;
    
    const toast = document.createElement('div');
    toast.className = 'position-fixed bottom-0 end-0 p-3';
    toast.style.zIndex = '9999';
    toast.innerHTML = `
        <div class="toast-custom" style="border-left-color: ${color};">
            <i class="fas fa-${type === 'success' ? 'check-circle' : 'info-circle'} me-2" 
               style="color: ${color};"></i>
            ${message}
        </div>
    `;
    
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}
