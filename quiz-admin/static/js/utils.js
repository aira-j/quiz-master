/* ── Shared JS Utilities ── */
const API_BASE = '';

// ── Auth Helpers ──
function getToken() {
    return localStorage.getItem('quiz_token');
}

function setToken(token) {
    localStorage.setItem('quiz_token', token);
}

function clearToken() {
    localStorage.removeItem('quiz_token');
}

function getAuthHeaders() {
    const token = getToken();
    return token ? { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' };
}

async function fetchAPI(url, options = {}) {
    const defaults = { headers: getAuthHeaders() };
    const config = { ...defaults, ...options, headers: { ...defaults.headers, ...options.headers } };
    const response = await fetch(API_BASE + url, config);
    if (response.status === 401) {
        clearToken();
        window.location.href = '/login';
        return;
    }
    return response;
}

async function getCurrentUser() {
    const res = await fetchAPI('/api/auth/me');
    if (res && res.ok) return await res.json();
    return null;
}

async function checkAuthAndRedirect() {
    const user = await getCurrentUser();
    if (!user) {
        window.location.href = '/login';
        return null;
    }
    return user;
}

function logout() {
    clearToken();
    window.location.href = '/login';
}

// ── Toast Notifications ──
function showToast(message, type = 'info') {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

// ── Time Formatting ──
function formatTime(seconds) {
    if (seconds == null) return '--';
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${String(s).padStart(2, '0')}`;
}

function formatDate(dateStr) {
    if (!dateStr) return '--';
    return new Date(dateStr).toLocaleDateString('en-IN', {
        day: 'numeric', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
    });
}

// ── Copy to Clipboard ──
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast('Copied to clipboard!', 'success');
    } catch {
        showToast('Failed to copy', 'error');
    }
}
