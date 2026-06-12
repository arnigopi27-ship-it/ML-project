// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function formatAmount(amount) {
    return '₹' + Math.round(amount).toLocaleString('en-IN');
}

function formatDate(dateStr) {
    // Append T00:00:00 to avoid timezone shifts
    const date = new Date(dateStr + 'T00:00:00');
    return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' });
}

function showElement(id) {
    const el = typeof id === 'string' ? document.getElementById(id.replace('#', '')) : id;
    el?.classList.remove('hidden');
}

function hideElement(id) {
    const el = typeof id === 'string' ? document.getElementById(id.replace('#', '')) : id;
    el?.classList.add('hidden');
}

function showError(message) {
    const box = document.getElementById('error-box');
    if (box) {
        box.textContent = '❌ ' + message;
        box.classList.remove('hidden');
        setTimeout(() => box.classList.add('hidden'), 6000);
    }
}

function hideError() {
    document.getElementById('error-box')?.classList.add('hidden');
}

function getCategoryEmoji(category) {
    const map = {
        'Food': '🍔', 'Travel': '🚗', 'Bills': '📄',
        'Shopping': '🛍️', 'Entertainment': '🎬', 'Other': '❓'
    };
    return map[category] || '❓';
}

function getMonthKey(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
}

// ============================================================================
// CHART INSTANCES (kept global to allow destroy before re-render)
// ============================================================================

let categoryChart = null;
let compareChart = null;
let pieChart = null;
let spendPulseChart = null;

// ============================================================================
// API HELPERS
// ============================================================================

async function fetchExpenses() {
    try {
        const res = await fetch('/expenses');
        if (!res.ok) throw new Error('Server error');
        return await res.json();
    } catch (e) {
        console.error('fetchExpenses failed:', e);
        return [];
    }
}

async function addExpenseAPI(expense) {
    const res = await fetch('/expenses', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(expense)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Failed to add expense');
    return data;
}

async function deleteExpenseAPI(id) {
    const res = await fetch(`/expenses/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete');
    return true;
}

async function classifyExpenseAPI(description) {
    const res = await fetch('/classify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Classification failed');
    return data;
}

// ============================================================================
// SUCCESS POPUP (5-second animated overlay)
// ============================================================================

function showSuccessPopup(amount, description, category) {
    document.getElementById('success-amount').textContent = formatAmount(amount);
    document.getElementById('success-desc').textContent = description;
    document.getElementById('success-cat').textContent = getCategoryEmoji(category) + ' ' + category;

    const popup = document.getElementById('success-popup');
    popup.classList.remove('hidden', 'popup-hide');
    popup.classList.add('popup-show');

    // Animate progress bar from 0 to 100% over 5s
    const fill = document.getElementById('success-progress-fill');
    fill.style.transition = 'none';
    fill.style.width = '0%';
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            fill.style.transition = 'width 5s linear';
            fill.style.width = '100%';
        });
    });

    setTimeout(() => {
        popup.classList.add('popup-hide');
        setTimeout(() => {
            popup.classList.remove('popup-show', 'popup-hide');
            popup.classList.add('hidden');
            fill.style.transition = 'none';
            fill.style.width = '0%';
            // Switch to dashboard and reload
            switchTab('dashboard');
            loadDashboard();
        }, 350);
    }, 5000);
}

// ============================================================================
// DASHBOARD
// ============================================================================

async function loadDashboard() {
    const expenses = await fetchExpenses();

    const today = new Date();
    const currentMonth = getMonthKey(today);
    const lastMonthDate = new Date(today.getFullYear(), today.getMonth() - 1, 1);
    const lastMonth = getMonthKey(lastMonthDate);

    const thisMonthTotal = expenses
        .filter(e => e.date.startsWith(currentMonth))
        .reduce((s, e) => s + e.amount, 0);
    const lastMonthTotal = expenses
        .filter(e => e.date.startsWith(lastMonth))
        .reduce((s, e) => s + e.amount, 0);
    const momChange = thisMonthTotal - lastMonthTotal;
    const momPercent = lastMonthTotal ? (momChange / lastMonthTotal * 100) : 0;

    document.getElementById('this-month').textContent = formatAmount(thisMonthTotal);
    document.getElementById('last-month').textContent = formatAmount(lastMonthTotal);
    document.getElementById('mom-change').textContent = formatAmount(momChange);
    document.getElementById('mom-percent').textContent = `(${momPercent.toFixed(1)}%)`;
    document.getElementById('expense-count').textContent = expenses.length;

    const momParent = document.getElementById('mom-change').parentElement;
    momParent.classList.toggle('negative', momChange < 0);
    momParent.classList.toggle('positive', momChange > 0);

    updateExpensesList(expenses);
    updateCategoryChart(expenses);
    updatePieChart(expenses);
    loadInsights();
    loadCategoryAlerts();
}

function updateExpensesList(expenses) {
    const listDiv = document.getElementById('expenses-list');
    if (!listDiv) return;
    listDiv.innerHTML = '';

    if (expenses.length === 0) {
        listDiv.innerHTML = '<p style="color:#94a3b8;text-align:center;padding:30px;">No expenses yet. Add your first expense!</p>';
        return;
    }

    expenses.forEach(expense => {
        const item = document.createElement('div');
        item.className = 'expense-item';
        item.innerHTML = `
            <div class="expense-left">
                <div class="expense-date">${formatDate(expense.date)}</div>
                <div class="expense-description">${expense.description}</div>
                <div class="expense-category">
                    <span class="category-badge ${expense.category}">${getCategoryEmoji(expense.category)} ${expense.category}</span>
                </div>
            </div>
            <div class="expense-right">
                <div class="expense-amount">${formatAmount(expense.amount)}</div>
                <button class="btn-delete" onclick="handleDeleteExpense(${expense.id})">Delete</button>
            </div>
        `;
        listDiv.appendChild(item);
    });
}

async function handleDeleteExpense(id) {
    if (confirm('Delete this expense?')) {
        try {
            await deleteExpenseAPI(id);
            loadDashboard();
        } catch {
            showError('Failed to delete expense');
        }
    }
}

function updateCategoryChart(expenses) {
    // Destroy old chart if it existed
    if (categoryChart) { categoryChart.destroy(); categoryChart = null; }

    const totals = {};
    expenses.forEach(e => { totals[e.category] = (totals[e.category] || 0) + e.amount; });

    const categories = Object.keys(totals).sort((a, b) => totals[b] - totals[a]);
    const maxVal = Math.max(...Object.values(totals), 1);
    const totalAll = Object.values(totals).reduce((s, v) => s + v, 0);

    const colors = {
        'Food': '#f97316', 'Travel': '#3b82f6', 'Bills': '#ef4444',
        'Shopping': '#8b5cf6', 'Entertainment': '#10b981', 'Other': '#64748b'
    };
    const icons = {
        'Food': '🍽️', 'Travel': '✈️', 'Bills': '📄',
        'Shopping': '🛍️', 'Entertainment': '🎬', 'Other': '❓'
    };

    const container = document.getElementById('category-cards-list');
    if (!container) return;

    if (categories.length === 0) {
        container.innerHTML = '<p style="color:#64748b;font-size:0.85rem;padding:12px;">No data yet</p>';
        return;
    }

    container.innerHTML = categories.slice(0, 4).map(cat => {
        const pct = totalAll > 0 ? Math.round((totals[cat] / totalAll) * 100) : 0;
        const barPct = Math.round((totals[cat] / maxVal) * 100);
        const color = colors[cat] || '#64748b';
        const icon = icons[cat] || '❓';
        const amtK = totals[cat] >= 1000
            ? '₹' + (totals[cat] / 1000).toFixed(1) + 'K'
            : '₹' + Math.round(totals[cat]);
        return `
            <div class="cat-dash-card">
                <div class="cat-dash-icon" style="background:${color}22;">
                    <span>${icon}</span>
                </div>
                <div class="cat-dash-body">
                    <div class="cat-dash-top">
                        <span class="cat-dash-name">${cat}</span>
                        <span class="cat-dash-pct-badge" style="color:${color};border-color:${color}40;">${pct}%</span>
                    </div>
                    <div class="cat-dash-amount">${amtK} | ${pct}%</div>
                    <div class="cat-dash-bar-bg">
                        <div class="cat-dash-bar-fill" style="width:${barPct}%;background:linear-gradient(90deg,${color},${color}99);"></div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function updatePieChart(expenses) {
    const totals = {};
    expenses.forEach(e => { totals[e.category] = (totals[e.category] || 0) + e.amount; });
    const categories = Object.keys(totals);
    const colors = {
        'Food': '#f97316', 'Travel': '#3b82f6', 'Bills': '#ef4444',
        'Shopping': '#8b5cf6', 'Entertainment': '#10b981', 'Other': '#64748b'
    };

    const ctx = document.getElementById('pieChart');
    if (!ctx) return;
    if (pieChart) pieChart.destroy();

    // Update center transaction count
    const countEl = document.getElementById('ring-count');
    if (countEl) countEl.textContent = expenses.length;

    // Update total spending footer
    const totalVal = Object.values(totals).reduce((s, v) => s + v, 0);
    const totalEl = document.getElementById('ring-total-value');
    if (totalEl) totalEl.textContent = formatAmount(totalVal);

    // Build legend
    const legendEl = document.getElementById('ring-legend');
    if (legendEl) {
        legendEl.innerHTML = categories.map(cat => `
            <div class="ring-legend-item">
                <div class="ring-legend-dot" style="background:${colors[cat] || '#64748b'}"></div>
                <span>${cat}</span>
            </div>
        `).join('');
    }

    if (categories.length === 0) return;

    pieChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: categories,
            datasets: [{
                data: categories.map(c => totals[c]),
                backgroundColor: categories.map(c => colors[c] || '#64748b'),
                borderColor: '#0d1117',
                borderWidth: 3,
                hoverOffset: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '68%',
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: ctx => ' ' + ctx.label + ': ' + formatAmount(ctx.parsed)
                    }
                }
            }
        }
    });
}

function updateSpendPulse(expenses) {
    const ctx = document.getElementById('spendPulseChart');
    if (!ctx) return;
    if (spendPulseChart) spendPulseChart.destroy();

    // Group by date, take last 14 data points
    const byDate = {};
    expenses.forEach(e => { byDate[e.date] = (byDate[e.date] || 0) + e.amount; });
    const sorted = Object.keys(byDate).sort().slice(-14);
    const vals = sorted.map(d => byDate[d]);

    if (vals.length === 0) return;

    spendPulseChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: sorted,
            datasets: [{
                data: vals,
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59,130,246,0.12)',
                borderWidth: 2,
                fill: true,
                tension: 0.45,
                pointRadius: 0,
                pointHoverRadius: 4,
                pointHoverBackgroundColor: '#3b82f6'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: { enabled: false } },
            scales: { x: { display: false }, y: { display: false } },
            animation: { duration: 1000, easing: 'easeInOutQuart' }
        }
    });
}

// ============================================================================
// SMART INSIGHTS
// ============================================================================

async function loadInsights() {
    try {
        const res = await fetch('/insights');
        const data = await res.json();
        const el = document.getElementById('insights-text');
        if (el) el.textContent = data.message || 'No insights available';

        const banner = document.getElementById('insights-box');
        if (banner && data.change > 0) banner.classList.add('insight-warning');
        else if (banner) banner.classList.remove('insight-warning');
    } catch {
        const el = document.getElementById('insights-text');
        if (el) el.textContent = 'Unable to load insights';
    }
}

// ============================================================================
// CATEGORY ALERTS (with progress bars)
// ============================================================================

async function loadCategoryAlerts() {
    try {
        const res = await fetch('/category-alerts');
        const alerts = await res.json();
        const box = document.getElementById('category-alert-box');
        if (!box || !Array.isArray(alerts)) return;

        box.innerHTML = alerts.map(a => {
            const barColor = a.exceeded ? '#ef4444' : (a.percentage > 75 ? '#f97316' : '#10b981');
            return `
                <div class="cat-alert-card ${a.exceeded ? 'cat-exceeded' : ''}">
                    <div class="cat-alert-top">
                        <span class="cat-alert-name">${getCategoryEmoji(a.category)} ${a.category}</span>
                        <span class="cat-alert-vals">${formatAmount(a.total)} / ${formatAmount(a.limit)}</span>
                        ${a.exceeded ? '<span class="cat-alert-badge">⚠️ Limit Exceeded!</span>' : ''}
                    </div>
                    <div class="cat-bar-bg">
                        <div class="cat-bar-fill" style="width:${a.percentage}%;background:${barColor};"></div>
                    </div>
                    <div class="cat-pct-label">${a.percentage}% of limit used</div>
                </div>
            `;
        }).join('');
    } catch {
        console.log('Category alert load failed');
    }
}

// ============================================================================
// AUTO-PREDICT + AUTO-ADD (MANUAL FORM — NO BUTTONS)
// ============================================================================

let classifyTimer = null;
let autoAddTimer = null;

function setDefaultDate() {
    const input = document.getElementById('date');
    if (input && !input.value) {
        input.valueAsDate = new Date();
    }
}

function updateCategoryDisplay(category, confidence) {
    const badge = document.getElementById('auto-cat-badge');
    const conf = document.getElementById('auto-cat-conf');
    const sel = document.getElementById('category');

    if (badge) {
        if (category) {
            badge.textContent = getCategoryEmoji(category) + ' ' + category;
            badge.className = 'auto-cat-badge cat-color-' + category;
        } else {
            badge.textContent = '';
            badge.className = 'auto-cat-badge';
        }
    }
    if (conf) conf.textContent = confidence ? `${Math.round(confidence * 100)}% confidence` : '';
    if (sel && category) sel.value = category;
}

function allFieldsFilled() {
    const amount = parseFloat(document.getElementById('amount')?.value || '0');
    const date = document.getElementById('date')?.value;
    const desc = document.getElementById('description')?.value?.trim();
    const cat = document.getElementById('category')?.value;
    return amount > 0 && !!date && !!desc && !!cat;
}

function cancelAutoAdd() {
    if (autoAddTimer) { clearTimeout(autoAddTimer); autoAddTimer = null; }
    const statusDiv = document.getElementById('auto-add-status');
    if (statusDiv) statusDiv.classList.add('hidden');
    const fill = document.getElementById('auto-add-fill');
    if (fill) { fill.style.transition = 'none'; fill.style.width = '0%'; }
}

function scheduleAutoAdd() {
    cancelAutoAdd();
    if (!allFieldsFilled()) return;

    const statusDiv = document.getElementById('auto-add-status');
    const fillEl = document.getElementById('auto-add-fill');
    const textEl = document.getElementById('auto-add-text');

    if (statusDiv) statusDiv.classList.remove('hidden');
    if (textEl) textEl.textContent = '⏳ Auto-adding in 2 seconds... (Cancel if needed)';
    if (fillEl) {
        fillEl.style.transition = 'none';
        fillEl.style.width = '0%';
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                fillEl.style.transition = 'width 2s linear';
                fillEl.style.width = '100%';
            });
        });
    }

    autoAddTimer = setTimeout(async () => {
        const amount = parseFloat(document.getElementById('amount').value);
        const date = document.getElementById('date').value;
        const description = document.getElementById('description').value.trim();
        const category = document.getElementById('category').value;
        await submitExpense(amount, description, category, date);
    }, 2000);
}

async function submitExpense(amount, description, category, date) {
    cancelAutoAdd();
    try {
        await addExpenseAPI({ amount, description, category, date });
        // Reset form
        document.getElementById('expense-form')?.reset();
        setDefaultDate();
        updateCategoryDisplay(null, null);
        // Show success popup → switches to dashboard
        showSuccessPopup(amount, description, category);
    } catch (err) {
        showError('Failed to add expense: ' + err.message);
    }
}

// ============================================================================
// OCR BILL UPLOAD
// ============================================================================

async function uploadBillOCR(file) {
    const statusEl = document.getElementById('ocr-status');
    if (statusEl) { statusEl.textContent = '🔍 Reading bill, please wait...'; statusEl.classList.remove('hidden'); }

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch('/upload-bill', { method: 'POST', body: formData });
        const data = await res.json();

        if (data.error) {
            if (statusEl) statusEl.textContent = '❌ ' + data.error;
            return;
        }

        if (statusEl) {
            statusEl.textContent = `✅ Found: ₹${data.amount} — "${data.description}"`;
        }

        // Auto-fill form fields
        document.getElementById('amount').value = data.amount || '';
        document.getElementById('description').value = data.description || '';
        updateCategoryDisplay(data.category, data.confidence);

        // Immediately add (no delay for OCR — fully automatic)
        const date = document.getElementById('date').value || new Date().toISOString().split('T')[0];
        if (!data.amount || data.amount <= 0) {
            if (statusEl) statusEl.textContent = '⚠️ Could not detect amount. Please enter it manually.';
            return;
        }
        await submitExpense(parseFloat(data.amount), data.description, data.category, date);

    } catch (err) {
        if (statusEl) statusEl.textContent = '❌ OCR upload failed. Try again.';
        showError('OCR failed: ' + err.message);
    }
}

// ============================================================================
// VOICE RECOGNITION
// ============================================================================

function startVoiceInput() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const voiceBtn = document.getElementById('voice-btn');
    const statusEl = document.getElementById('voice-status');

    if (!SR) {
        alert('Voice input is not supported. Please use Google Chrome.');
        return;
    }

    const recognition = new SR();
    recognition.lang = 'en-IN';
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onstart = () => {
        if (voiceBtn) { voiceBtn.textContent = '🔴 Listening...'; voiceBtn.disabled = true; }
        if (statusEl) { statusEl.textContent = '🎙️ Speak now...'; statusEl.classList.remove('hidden'); }
    };

    recognition.onresult = async (event) => {
        const text = event.results[0][0].transcript.trim();
        if (statusEl) statusEl.textContent = `📝 Heard: "${text}"`;

        // Fill description
        document.getElementById('description').value = text;

        // Extract first number as amount
        const amountMatch = text.match(/\d+(?:\.\d{1,2})?/);
        const amount = amountMatch ? parseFloat(amountMatch[0]) : 0;
        if (amount > 0) document.getElementById('amount').value = amount;

        try {
            const result = await classifyExpenseAPI(text);
            updateCategoryDisplay(result.category, result.confidence);

            const date = document.getElementById('date').value || new Date().toISOString().split('T')[0];

            if (amount <= 0) {
                if (statusEl) statusEl.textContent = '⚠️ Could not detect amount. Please enter it manually.';
                showError('Amount not detected from voice. Please enter it manually.');
                return;
            }

            if (statusEl) statusEl.textContent = `✅ Adding: ₹${amount} → ${result.category}`;
            await submitExpense(amount, text, result.category, date);
        } catch {
            if (statusEl) statusEl.textContent = '❌ Processing failed. Try again.';
        }
    };

    recognition.onerror = (e) => {
        if (voiceBtn) { voiceBtn.textContent = '🎤 Start Speaking'; voiceBtn.disabled = false; }
        if (statusEl) statusEl.textContent = '❌ Error: ' + e.error;
    };

    recognition.onend = () => {
        if (voiceBtn) { voiceBtn.textContent = '🎤 Start Speaking'; voiceBtn.disabled = false; }
    };

    recognition.start();
}

// ============================================================================
// PREDICT & ALERT TAB
// ============================================================================

async function loadPredictAlert() {
    try {
        hideError();
        const res = await fetch('/predict_alert');
        const result = await res.json();
        if (!res.ok) throw new Error(result.error || 'Failed');

        showElement('predict-result');
        const statusBox = document.getElementById('predict-status');
        const alertBox = document.getElementById('alert-box');

        document.getElementById('result-last-month').textContent = formatAmount(result.last_month_actual || 0);
        document.getElementById('result-current-month').textContent = formatAmount(result.current_month_actual || 0);
        document.getElementById('result-difference').textContent = formatAmount(Math.abs(result.difference || 0));
        document.getElementById('result-percent').textContent = `(${(result.percentage || 0).toFixed(1)}%)`;

        alertBox.classList.add('hidden');
        alertBox.innerHTML = '';

        if (result.over_threshold) {
            statusBox.className = 'result-box error';
            statusBox.textContent = `⚠️ Alert: This month is ${result.percentage.toFixed(1)}% higher than last month!`;
            alertBox.className = 'alert-box warning';
            alertBox.innerHTML = result.alert_sent
                ? `📧 Alert email sent to <strong>${result.email}</strong>.`
                : `⚠️ Alert condition met but email couldn't be sent. Check SMTP settings in .env.`;
            alertBox.classList.remove('hidden');
        } else {
            statusBox.className = 'result-box success';
            statusBox.textContent = `✅ This month spending is not higher than last month. You're doing great!`;
        }
    } catch (err) {
        showError('Alert check failed: ' + err.message);
    }
}

document.getElementById('predict-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    await loadPredictAlert();
});

// ============================================================================
// PROFILE TAB
// ============================================================================

async function loadProfile() {
    try {
        const res = await fetch('/profile');
        const profile = await res.json();
        if (!res.ok) throw new Error(profile.error || 'Failed');

        showElement('profile-result');
        document.getElementById('profile-summary').textContent = `👋 Welcome, ${profile.name || 'User'}!`;
        document.getElementById('profile-name').textContent = profile.name || '-';
        document.getElementById('profile-email').textContent = profile.email || '-';
        document.getElementById('profile-role').textContent = profile.role || 'Primary Account';
        document.getElementById('profile-member-since').textContent = profile.member_since || '-';
    } catch (err) {
        showError('Profile load failed: ' + err.message);
    }
}

function openProfileEditor() {
    document.getElementById('edit-name').value = document.getElementById('profile-name').textContent || '';
    document.getElementById('edit-email').value = document.getElementById('profile-email').textContent || '';
    const ms = document.getElementById('profile-member-since').textContent;
    document.getElementById('edit-member').value = (ms && ms !== '-') ? ms : '';
    hideElement('profile-view');
    showElement('profile-edit');
}

function closeProfileEditor() {
    hideElement('profile-edit');
    showElement('profile-view');
}

// ============================================================================
// MONTHLY COMPARE TAB
// ============================================================================

async function loadMonthlySelects() {
    const expenses = await fetchExpenses();
    const monthSet = new Set(expenses.map(e => e.date.substring(0, 7)));
    const months = Array.from(monthSet).sort().reverse();

    const opts = months.map(m => {
        const label = new Date(m + '-01').toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });
        return `<option value="${m}">${label}</option>`;
    }).join('');

    const selA = document.getElementById('month-a');
    const selB = document.getElementById('month-b');
    if (selA) selA.innerHTML = opts;
    if (selB) selB.innerHTML = opts;

    if (months.length >= 2) {
        if (selA) selA.value = months[0];
        if (selB) selB.value = months[1];
    }
}

async function loadComparison() {
    const monthA = document.getElementById('month-a')?.value;
    const monthB = document.getElementById('month-b')?.value;
    if (!monthA || !monthB) return;

    const expenses = await fetchExpenses();

    const getMonthData = (m) => {
        const filtered = expenses.filter(e => e.date.startsWith(m));
        const bycat = {};
        filtered.forEach(e => { bycat[e.category] = (bycat[e.category] || 0) + e.amount; });
        return bycat;
    };

    const dataA = getMonthData(monthA);
    const dataB = getMonthData(monthB);
    const totalA = Object.values(dataA).reduce((s, v) => s + v, 0);
    const totalB = Object.values(dataB).reduce((s, v) => s + v, 0);

    showElement('compare-result');

    const dateA = new Date(monthA + '-01').toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });
    const dateB = new Date(monthB + '-01').toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });

    document.getElementById('comp-a-label').textContent = dateA;
    document.getElementById('comp-b-label').textContent = dateB;
    document.getElementById('comp-a-value').textContent = formatAmount(totalA);
    document.getElementById('comp-b-value').textContent = formatAmount(totalB);

    const diff = totalA - totalB;
    const pct = totalB ? (diff / totalB * 100) : 0;
    const summaryEl = document.getElementById('difference-summary');
    summaryEl.textContent = `Difference: ${formatAmount(Math.abs(diff))} (${Math.abs(pct).toFixed(1)}%)`;
    summaryEl.classList.toggle('higher', diff > 0);
    summaryEl.classList.toggle('lower', diff < 0);

    // Category comparison bars
    const cats = new Set([...Object.keys(dataA), ...Object.keys(dataB)]);
    document.getElementById('category-comparison').innerHTML = Array.from(cats).map(cat => {
        const vA = dataA[cat] || 0;
        const vB = dataB[cat] || 0;
        const mx = Math.max(vA, vB);
        return `
            <div class="comparison-bar-group">
                <div class="comparison-bar-label">${getCategoryEmoji(cat)} ${cat}</div>
                <div class="comparison-bars">
                    <div class="comparison-bar month-a" style="width:${mx ? (vA / mx * 100) : 0}%">${formatAmount(vA)}</div>
                    <div class="comparison-bar month-b" style="width:${mx ? (vB / mx * 100) : 0}%">${formatAmount(vB)}</div>
                </div>
            </div>
        `;
    }).join('');

    // Chart
    const catArr = Array.from(cats).sort();
    const ctx = document.getElementById('compareChart');
    if (!ctx) return;
    if (compareChart) compareChart.destroy();
    compareChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: catArr,
            datasets: [
                { label: dateA, data: catArr.map(c => dataA[c] || 0), backgroundColor: '#8b5cf6', borderRadius: 8 },
                { label: dateB, data: catArr.map(c => dataB[c] || 0), backgroundColor: 'rgba(139,92,246,0.4)', borderRadius: 8 }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: '#cbd5e1' } },
                tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + formatAmount(ctx.parsed.y) } }
            },
            scales: {
                y: { beginAtZero: true, ticks: { callback: v => '₹' + (v / 1000).toFixed(0) + 'K', color: '#cbd5e1' }, grid: { color: '#334155' } },
                x: { ticks: { color: '#cbd5e1' }, grid: { display: false } }
            }
        }
    });
}

document.getElementById('month-a')?.addEventListener('change', loadComparison);
document.getElementById('month-b')?.addEventListener('change', loadComparison);

// ============================================================================
// TAB SWITCHING
// ============================================================================

function switchTab(tabId) {
    document.querySelectorAll('.tab-button').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelector(`.tab-button[data-tab="${tabId}"]`)?.classList.add('active');
    document.getElementById(tabId)?.classList.add('active');
}

document.querySelectorAll('.tab-button').forEach(btn => {
    btn.addEventListener('click', (e) => {
        const tabId = e.target.getAttribute('data-tab');
        switchTab(tabId);
        if (tabId === 'dashboard') loadDashboard();
        else if (tabId === 'compare') loadMonthlySelects().then(loadComparison);
        else if (tabId === 'predict') loadPredictAlert();
        else if (tabId === 'profile') loadProfile();
    });
});

// ============================================================================
// LOGIN MODAL
// ============================================================================

function showLoginModal() {
    document.getElementById('login-modal')?.classList.remove('hidden');
    switchAuthTab('signin');
}

function hideLoginModal() {
    document.getElementById('login-modal')?.classList.add('hidden');
}

function switchAuthTab(tab) {
    document.querySelectorAll('.auth-tab').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.auth-panel').forEach(p => p.classList.remove('active'));
    document.getElementById('tab-' + tab)?.classList.add('active');
    document.querySelector(`.auth-panel[data-panel="${tab}"]`)?.classList.add('active');
}

async function checkLoginAndInit() {
    try {
        const res = await fetch('/api/check-login');
        const data = await res.json();
        if (data.logged_in && data.user) {
            hideLoginModal();
            const nameEl = document.getElementById('header-user-name');
            if (nameEl) nameEl.textContent = 'Hello, ' + data.user.name;
            loadDashboard();
        } else {
            showLoginModal();
        }
    } catch {
        showLoginModal();
    }
}

async function logoutUser() {
    try {
        await fetch('/logout', { method: 'POST' });
        const nameEl = document.getElementById('header-user-name');
        if (nameEl) nameEl.textContent = 'Loading...';
        showLoginModal();
    } catch {
        showError('Logout failed');
    }
}

// ============================================================================
// SINGLE DOMContentLoaded — ALL EVENT BINDINGS HERE
// ============================================================================

document.addEventListener('DOMContentLoaded', async () => {
    setDefaultDate();
    hideError();

    // ── Check login on page load ──────────────────────────────────────────
    await checkLoginAndInit();

    // ── Sign In form ──────────────────────────────────────────────────────
    document.getElementById('login-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('login-email').value.trim();
        const errEl = document.getElementById('login-error');
        if (!email) {
            if (errEl) { errEl.textContent = '❌ Email is required'; errEl.classList.remove('hidden'); }
            return;
        }
        try {
            const name = email.split('@')[0];
            const res = await fetch('/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, email })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Sign in failed');
            hideLoginModal();
            const nameEl = document.getElementById('header-user-name');
            if (nameEl) nameEl.textContent = 'Hello, ' + (data.profile?.name || name);
            loadDashboard();
        } catch (err) {
            if (errEl) { errEl.textContent = '❌ ' + err.message; errEl.classList.remove('hidden'); }
        }
    });

    // ── Sign Up form ──────────────────────────────────────────────────────
    document.getElementById('signup-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('signup-name').value.trim();
        const email = document.getElementById('signup-email').value.trim();
        const errEl = document.getElementById('signup-error');
        if (!name || !email) {
            if (errEl) { errEl.textContent = '❌ Name and email are required'; errEl.classList.remove('hidden'); }
            return;
        }
        try {
            const res = await fetch('/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, email })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Sign up failed');
            hideLoginModal();
            const nameEl = document.getElementById('header-user-name');
            if (nameEl) nameEl.textContent = 'Hello, ' + name;
            loadDashboard();
        } catch (err) {
            if (errEl) { errEl.textContent = '❌ ' + err.message; errEl.classList.remove('hidden'); }
        }
    });

    // ── Logout buttons ────────────────────────────────────────────────────
    document.getElementById('header-logout-btn')?.addEventListener('click', logoutUser);
    document.getElementById('profile-logout-btn')?.addEventListener('click', logoutUser);

    // ── Profile edit / cancel ─────────────────────────────────────────────
    document.getElementById('edit-profile-btn')?.addEventListener('click', openProfileEditor);
    document.getElementById('cancel-edit')?.addEventListener('click', closeProfileEditor);

    document.getElementById('profile-edit-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('edit-name').value.trim();
        const email = document.getElementById('edit-email').value.trim();
        const member_since = document.getElementById('edit-member').value;
        try {
            const res = await fetch('/profile_update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, email, member_since })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Update failed');
            await loadProfile();
            closeProfileEditor();
            alert('✅ Profile updated!');
        } catch (err) {
            showError('Profile update failed: ' + err.message);
        }
    });

    // ── Description: auto-classify with 600ms debounce ───────────────────
    document.getElementById('description')?.addEventListener('input', () => {
        cancelAutoAdd();
        clearTimeout(classifyTimer);

        const val = document.getElementById('description').value.trim();
        if (val.length < 3) {
            updateCategoryDisplay(null, null);
            document.getElementById('category').value = '';
            return;
        }

        classifyTimer = setTimeout(async () => {
            try {
                const result = await classifyExpenseAPI(val);
                updateCategoryDisplay(result.category, result.confidence);
                // If other fields are already filled, schedule auto-add
                scheduleAutoAdd();
            } catch {
                // silent
            }
        }, 600);
    });

    // ── Amount/Date: re-check auto-add when changed ───────────────────────
    document.getElementById('amount')?.addEventListener('input', () => {
        cancelAutoAdd();
        scheduleAutoAdd();
    });
    document.getElementById('date')?.addEventListener('change', () => {
        cancelAutoAdd();
        scheduleAutoAdd();
    });

    // ── Cancel auto-add button ────────────────────────────────────────────
    document.getElementById('cancel-auto-add')?.addEventListener('click', cancelAutoAdd);

    // ── OCR file upload ───────────────────────────────────────────────────
    document.getElementById('bill-upload')?.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        e.target.value = ''; // reset so same file can re-trigger
        if (file) await uploadBillOCR(file);
    });

    // ── Voice input ───────────────────────────────────────────────────────
    document.getElementById('voice-btn')?.addEventListener('click', startVoiceInput);
});
