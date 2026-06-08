// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function formatAmount(amount) {
    return '₹' + Math.round(amount).toLocaleString('en-IN');
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    const options = { day: 'numeric', month: 'long', year: 'numeric' };
    return date.toLocaleDateString('en-IN', options);
}

function showElement(selector) {
    document.querySelector(selector)?.classList.remove('hidden');
}

function hideElement(selector) {
    document.querySelector(selector)?.classList.add('hidden');
}

function showError(message) {
    const box = document.getElementById('error-box');
    if (box) {
        box.textContent = '❌ ' + message;
        showElement('#error-box');
    } else {
        alert('Error: ' + message);
    }
}

function hideError() {
    hideElement('#error-box');
}

// ============================================================================
// LOGIN MODAL FUNCTIONS
// ============================================================================

function showLoginModal() {
    const modal = document.getElementById('login-modal');
    if (modal) {
        modal.classList.add('active');
    }
}

function hideLoginModal() {
    const modal = document.getElementById('login-modal');
    if (modal) {
        modal.classList.remove('active');
    }
}

async function handleModalLogin(e) {
    e.preventDefault();
    const name = document.getElementById('modal-name').value;
    const email = document.getElementById('modal-email').value;
    const msgBox = document.getElementById('modal-login-msg');
    
    try {
        const resp = await fetch('/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, email })
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || 'Login failed');
        
        // Hide modal and reload page to show dashboard
        hideLoginModal();
        // Small delay to let modal animation finish
        setTimeout(() => {
            window.location.reload();
        }, 300);
    } catch (err) {
        msgBox.classList.remove('hidden');
        msgBox.className = 'result-box error';
        msgBox.textContent = '❌ ' + err.message;
    }
}

// ============================================================================
// CHART INSTANCES (global to allow updates)
// ============================================================================

let categoryChart = null;
let predictionChart = null;
let compareChart = null;

// ============================================================================
// FETCH DATA FROM API
// ============================================================================

async function fetchExpenses() {
    try {
        const response = await fetch('/expenses');
        if (!response.ok) throw new Error('Failed to fetch expenses');
        return await response.json();
    } catch (error) {
        console.error('Error fetching expenses:', error);
        return [];
    }
}

async function addExpense(expense) {
    try {
        const response = await fetch('/expenses', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(expense)
        });
        if (!response.ok) throw new Error('Failed to add expense');
        return await response.json();
    } catch (error) {
        console.error('Error adding expense:', error);
        throw error;
    }
}

async function deleteExpense(id) {
    try {
        const response = await fetch(`/expenses/${id}`, { method: 'DELETE' });
        if (!response.ok) throw new Error('Failed to delete expense');
        return true;
    } catch (error) {
        console.error('Error deleting expense:', error);
        throw error;
    }
}

async function classifyExpense(description) {
    try {
        const response = await fetch('/classify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ description })
        });
        if (!response.ok) throw new Error('Failed to classify');
        return await response.json();
    } catch (error) {
        console.error('Error classifying expense:', error);
        throw error;
    }
}

async function predictNextMonth(budget, email) {
    try {
        const response = await fetch('/predict', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ budget, email })
        });
        if (!response.ok) throw new Error('Failed to predict');
        return await response.json();
    } catch (error) {
        console.error('Error predicting:', error);
        throw error;
    }
}

// ============================================================================
// DASHBOARD TAB
// ============================================================================

function getMonthKey(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    return `${year}-${month}`;
}

async function loadDashboard() {
    const expenses = await fetchExpenses();
    
    // Calculate metrics
    const today = new Date();
    const currentMonth = getMonthKey(today);
    const lastMonth = getMonthKey(new Date(today.getFullYear(), today.getMonth() - 1, 1));
    
    const thisMonthExpenses = expenses.filter(e => e.date.startsWith(currentMonth));
    const lastMonthExpenses = expenses.filter(e => e.date.startsWith(lastMonth));
    
    const thisMonthTotal = thisMonthExpenses.reduce((sum, e) => sum + e.amount, 0);
    const lastMonthTotal = lastMonthExpenses.reduce((sum, e) => sum + e.amount, 0);
    const momChange = thisMonthTotal - lastMonthTotal;
    const momPercent = lastMonthTotal ? (momChange / lastMonthTotal * 100) : 0;
    
    // Update metric cards
    document.getElementById('this-month').textContent = formatAmount(thisMonthTotal);
    document.getElementById('last-month').textContent = formatAmount(lastMonthTotal);
    
    const momCard = document.getElementById('mom-change').parentElement;
    document.getElementById('mom-change').textContent = formatAmount(momChange);
    document.getElementById('mom-percent').textContent = `(${momPercent.toFixed(1)}%)`;
    momCard.classList.toggle('negative', momChange < 0);
    momCard.classList.toggle('positive', momChange > 0);
    
    document.getElementById('expense-count').textContent = expenses.length;
    
    // Update expenses list
    updateExpensesList(expenses);
    
    // Update category chart
    updateCategoryChart(expenses);
}

function updateExpensesList(expenses) {
    const listDiv = document.getElementById('expenses-list');
    listDiv.innerHTML = '';
    
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
    if (confirm('Are you sure you want to delete this expense?')) {
        try {
            await deleteExpense(id);
            loadDashboard();
        } catch (error) {
            showError('Failed to delete expense');
        }
    }
}

function updateCategoryChart(expenses) {
    // Group by category
    const categoryTotals = {};
    expenses.forEach(e => {
        categoryTotals[e.category] = (categoryTotals[e.category] || 0) + e.amount;
    });
    
    const categories = Object.keys(categoryTotals);
    const totals = Object.values(categoryTotals);
    
    const categoryColors = {
        'Food': '#f97316',
        'Travel': '#3b82f6',
        'Bills': '#ef4444',
        'Shopping': '#8b5cf6',
        'Entertainment': '#10b981',
        'Other': '#64748b'
    };
    
    const ctx = document.getElementById('categoryChart');
    if (categoryChart) categoryChart.destroy();
    
    categoryChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: categories,
            datasets: [{
                label: 'Total Spending',
                data: totals,
                backgroundColor: categories.map(c => categoryColors[c] || '#64748b'),
                borderRadius: 8,
                borderSkipped: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return formatAmount(context.parsed.y);
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return '₹' + (value / 1000).toFixed(0) + 'K';
                        },
                        color: '#cbd5e1'
                    },
                    grid: { color: '#334155' }
                },
                x: {
                    ticks: { color: '#cbd5e1' },
                    grid: { display: false }
                }
            }
        }
    });
}

function getCategoryEmoji(category) {
    const emojis = {
        'Food': '🍔',
        'Travel': '🚗',
        'Bills': '📄',
        'Shopping': '🛍️',
        'Entertainment': '🎬',
        'Other': '❓'
    };
    return emojis[category] || '❓';
}

// ============================================================================
// ADD EXPENSE TAB
// ============================================================================

document.getElementById('expense-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    hideError();

    const amountRaw = document.getElementById('amount').value;
    const amount = parseFloat(amountRaw);
    const date = document.getElementById('date').value;
    const description = document.getElementById('description').value;
    let category = document.getElementById('category').value;

    // Validate amount
    if (!amountRaw || isNaN(amount) || amount <= 0) {
        showError('Please enter a valid amount greater than 0');
        return;
    }

    try {
        if (!category || category === 'auto') {
            const result = await classifyExpense(description);
            category = result.category;
        }

        await addExpense({ amount, date, description, category });

        // Reset form
        document.getElementById('expense-form').reset();
        document.getElementById('date').valueAsDate = new Date();

        // Reload dashboard
        loadDashboard();

        alert('✅ Expense added successfully!');
    } catch (error) {
        showError('Failed to add expense: ' + error.message);
    }
});

// Prevent Enter key inside description from submitting the form unintentionally
document.getElementById('description')?.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') ev.preventDefault();
});

// ============================================================================
// AUTO-PREDICT CATEGORY ON DESCRIPTION INPUT
// ============================================================================

let predictionTimeout;
let predictionIndicator;

// Create or get the prediction indicator element
function getPredictionIndicator() {
    let indicator = document.getElementById('prediction-indicator');
    if (!indicator) {
        indicator = document.createElement('div');
        indicator.id = 'prediction-indicator';
        indicator.className = 'prediction-indicator hidden';
        indicator.style.cssText = `
            font-size: 12px;
            margin-top: 4px;
            padding: 6px 8px;
            border-radius: 4px;
            background: #f0f9ff;
            color: #0c4a6e;
            display: none;
        `;
        const descriptionField = document.getElementById('description');
        descriptionField.parentElement.appendChild(indicator);
    }
    return indicator;
}

function showPredictionIndicator(category, confidence) {
    const indicator = getPredictionIndicator();
    const emoji = getCategoryEmoji(category);
    indicator.innerHTML = `🤖 Predicted: ${emoji} <strong>${category}</strong> (${(confidence * 100).toFixed(0)}% confidence)`;
    indicator.style.display = 'block';
}

function hidePredictionIndicator() {
    const indicator = getPredictionIndicator();
    indicator.style.display = 'none';
}

// Listen for description input and auto-predict category
document.getElementById('description')?.addEventListener('input', async (e) => {
    const description = e.target.value.trim();
    
    // Clear previous timeout
    if (predictionTimeout) {
        clearTimeout(predictionTimeout);
    }
    
    // Only predict if description has meaningful content (at least 3 characters)
    if (description.length < 3) {
        hidePredictionIndicator();
        return;
    }
    
    // Debounce the prediction call to avoid too many requests
    predictionTimeout = setTimeout(async () => {
        try {
            const result = await classifyExpense(description);
            
            // Auto-update category dropdown only if it's still on empty or auto selection
            const categorySelect = document.getElementById('category');
            if (!categorySelect.value || categorySelect.value === '') {
                categorySelect.value = result.category;
                // Trigger change event to update any listeners
                categorySelect.dispatchEvent(new Event('change', { bubbles: true }));
            }
            
            // Show prediction indicator
            showPredictionIndicator(result.category, result.confidence);
        } catch (error) {
            console.error('Auto-prediction error:', error);
            hidePredictionIndicator();
        }
    }, 500); // Wait 500ms after user stops typing before predicting
});

// Hide prediction indicator when category is manually selected
document.getElementById('category')?.addEventListener('change', (e) => {
    if (e.target.value && e.target.value !== '') {
        hidePredictionIndicator();
    }
});

function setDefaultDate() {
    const dateInput = document.getElementById('date');
    if (dateInput) {
        dateInput.valueAsDate = new Date();
    }
}

// ============================================================================
// PREDICT & ALERT TAB
// ============================================================================

async function fetchPredictAlert() {
    try {
        const response = await fetch('/predict_alert');
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to fetch alert status');
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching predict alert:', error);
        throw error;
    }
}

document.getElementById('predict-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    await loadPredictAlert();
});

async function loadPredictAlert() {
    try {
        hideError();
        const result = await fetchPredictAlert();

        showElement('#predict-result');
        const statusBox = document.getElementById('predict-status');
        const alertBox = document.getElementById('alert-box');

        document.getElementById('result-last-month').textContent = formatAmount(result.last_month_actual);
        document.getElementById('result-current-month').textContent = formatAmount(result.current_month_actual);
        document.getElementById('result-difference').textContent = formatAmount(result.difference);
        document.getElementById('result-percent').textContent = `(${result.percentage.toFixed(1)}%)`;

        alertBox.classList.add('hidden');
        alertBox.innerHTML = '';

        if (result.over_threshold) {
            statusBox.className = 'result-box error';
            statusBox.textContent = `⚠️ Alert triggered: Current month spending is higher than previous month.`;
            alertBox.className = 'alert-box warning';
            alertBox.innerHTML = result.alert_sent
                ? `📧 Alert email sent to <strong>${result.email}</strong>.`
                : `⚠️ Alert condition met, but email could not be sent. Check SMTP settings.`;
            showElement('#alert-box');
        } else {
            statusBox.className = 'result-box success';
            statusBox.textContent = `✅ No alert: Current month spending is not higher than previous month.`;

            if (result.current_month_actual === 0 && result.last_month_actual === 0) {
                statusBox.textContent = 'ℹ️ Not enough data to compare. Add expenses for the current and previous months.';
            }
        }

    } catch (error) {
        showError('Prediction failed: ' + error.message);
    }
}

async function fetchProfile() {
    try {
        const response = await fetch('/profile');
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to fetch profile');
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching profile:', error);
        throw error;
    }
}

async function loadProfile() {
    try {
        hideError();
        const profile = await fetchProfile();
        showElement('#profile-result');
        document.getElementById('profile-summary').textContent = 'Profile loaded successfully.';
        document.getElementById('profile-name').textContent = profile.name || '-';
        document.getElementById('profile-email').textContent = profile.email || '-';
        document.getElementById('profile-role').textContent = profile.role || '-';
        document.getElementById('profile-member-since').textContent = profile.member_since || '-';
    } catch (error) {
        showError('Profile load failed: ' + error.message);
    }
}

// Logout handler
async function logoutUser() {
    try {
        const resp = await fetch('/logout', { method: 'POST' });
        if (!resp.ok) throw new Error('Logout failed');
        window.location.reload();
    } catch (err) {
        showError('Logout failed: ' + err.message);
    }
}

// Profile edit flow
function openProfileEditor() {
    // populate inputs
    document.getElementById('edit-name').value = document.getElementById('profile-name').textContent || '';
    document.getElementById('edit-email').value = document.getElementById('profile-email').textContent || '';
    const ms = document.getElementById('profile-member-since').textContent || '';
    document.getElementById('edit-member').value = ms;
    showElement('#profile-edit');
    hideElement('#profile-view');
}

function closeProfileEditor() {
    hideElement('#profile-edit');
    showElement('#profile-view');
}

document.addEventListener('DOMContentLoaded', () => {
    // Bind modal login form
    document.getElementById('modal-login-form')?.addEventListener('submit', handleModalLogin);

    // Check if login modal is active (user not logged in)
    const modal = document.getElementById('login-modal');
    if (modal && modal.classList.contains('active')) {
        // User not logged in, modal is already visible
        console.log('User not logged in, showing login modal');
        return; // Don't load dashboard yet
    }

    // User is logged in, proceed with dashboard
    setDefaultDate();
    hideError();
    loadDashboard();

    // Bind profile edit / logout buttons (may not exist on all pages)
    document.getElementById('logout-btn')?.addEventListener('click', logoutUser);
    document.getElementById('edit-profile-btn')?.addEventListener('click', () => {
        openProfileEditor();
    });
    document.getElementById('cancel-edit')?.addEventListener('click', () => {
        closeProfileEditor();
    });

    document.getElementById('profile-edit-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('edit-name').value;
        const email = document.getElementById('edit-email').value;
        const member_since = document.getElementById('edit-member').value;
        try {
            const resp = await fetch('/profile_update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, email, member_since })
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error || 'Update failed');
            // Refresh profile view
            await loadProfile();
            closeProfileEditor();
            alert('Profile updated successfully');
        } catch (err) {
            showError('Profile update failed: ' + err.message);
        }
    });
});

async function updatePredictionChart(result) {
    const expenses = await fetchExpenses();
    
    // Group by month
    const monthlyTotals = {};
    expenses.forEach(e => {
        const month = e.date.substring(0, 7);
        monthlyTotals[month] = (monthlyTotals[month] || 0) + e.amount;
    });
    
    const months = Object.keys(monthlyTotals).sort();
    const totals = months.map(m => monthlyTotals[m]);
    
    // Add predicted month
    const lastMonth = months[months.length - 1];
    const nextMonth = new Date(lastMonth + '-01');
    nextMonth.setMonth(nextMonth.getMonth() + 1);
    const nextMonthStr = nextMonth.toISOString().substring(0, 7);
    
    const labels = [...months, nextMonthStr];
    const data = [...totals, null];
    const predictionData = new Array(totals.length).fill(null);
    predictionData.push(result.predicted_amount);
    
    const ctx = document.getElementById('predictionChart');
    if (predictionChart) predictionChart.destroy();
    
    predictionChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels.map(m => new Date(m + '-01').toLocaleDateString('en-IN', { month: 'short', year: '2-digit' })),
            datasets: [
                {
                    label: 'Actual Spending',
                    data: data,
                    borderColor: '#8b5cf6',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.4,
                    pointRadius: 5,
                    pointBackgroundColor: '#8b5cf6'
                },
                {
                    label: 'Linear Regression Trend',
                    data: predictionData,
                    borderColor: '#f97316',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0.4,
                    pointRadius: 5,
                    pointBackgroundColor: '#f97316'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#cbd5e1' }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return formatAmount(context.parsed.y);
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return '₹' + (value / 1000).toFixed(0) + 'K';
                        },
                        color: '#cbd5e1'
                    },
                    grid: { color: '#334155' }
                },
                x: {
                    ticks: { color: '#cbd5e1' },
                    grid: { display: false }
                }
            }
        }
    });
}

// ============================================================================
// MONTHLY COMPARE TAB
// ============================================================================

async function loadMonthlySelects() {
    const expenses = await fetchExpenses();
    
    // Get unique months
    const monthSet = new Set(expenses.map(e => e.date.substring(0, 7)));
    const months = Array.from(monthSet).sort().reverse();
    
    const selectA = document.getElementById('month-a');
    const selectB = document.getElementById('month-b');
    
    const options = months.map(month => {
        const date = new Date(month + '-01');
        const label = date.toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });
        return `<option value="${month}">${label}</option>`;
    }).join('');
    
    selectA.innerHTML = options;
    selectB.innerHTML = options;
    
    // Set defaults
    if (months.length >= 2) {
        selectA.value = months[0];
        selectB.value = months[1];
    }
}

document.getElementById('month-a')?.addEventListener('change', loadComparison);
document.getElementById('month-b')?.addEventListener('change', loadComparison);

async function loadComparison() {
    const monthA = document.getElementById('month-a').value;
    const monthB = document.getElementById('month-b').value;
    
    if (!monthA || !monthB) return;
    
    const expenses = await fetchExpenses();
    
    // Group by month and category
    const getMonthData = (month) => {
        const monthExpenses = expenses.filter(e => e.date.startsWith(month));
        const byCategory = {};
        monthExpenses.forEach(e => {
            byCategory[e.category] = (byCategory[e.category] || 0) + e.amount;
        });
        return byCategory;
    };
    
    const dataA = getMonthData(monthA);
    const dataB = getMonthData(monthB);
    const totalA = Object.values(dataA).reduce((a, b) => a + b, 0);
    const totalB = Object.values(dataB).reduce((a, b) => a + b, 0);
    
    // Update cards
    showElement('#compare-result');
    
    const dateA = new Date(monthA + '-01').toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });
    const dateB = new Date(monthB + '-01').toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });
    
    document.getElementById('comp-a-label').textContent = dateA;
    document.getElementById('comp-b-label').textContent = dateB;
    document.getElementById('comp-a-value').textContent = formatAmount(totalA);
    document.getElementById('comp-b-value').textContent = formatAmount(totalB);
    
    // Difference summary
    const diff = totalA - totalB;
    const diffPercent = totalB ? (diff / totalB * 100) : 0;
    const summary = document.getElementById('difference-summary');
    summary.textContent = `Difference: ${formatAmount(Math.abs(diff))} (${Math.abs(diffPercent).toFixed(1)}%)`;
    summary.classList.toggle('higher', diff > 0);
    summary.classList.toggle('lower', diff < 0);
    
    // Category comparison
    updateCategoryComparison(dataA, dataB);
    
    // Update chart
    updateCompareChart(dataA, dataB, dateA, dateB);
}

function updateCategoryComparison(dataA, dataB) {
    const categories = new Set([...Object.keys(dataA), ...Object.keys(dataB)]);
    const html = Array.from(categories).map(cat => {
        const valA = dataA[cat] || 0;
        const valB = dataB[cat] || 0;
        const maxVal = Math.max(valA, valB);
        const pctA = maxVal ? (valA / maxVal * 100) : 0;
        const pctB = maxVal ? (valB / maxVal * 100) : 0;
        
        return `
            <div class="comparison-bar-group">
                <div class="comparison-bar-label">${getCategoryEmoji(cat)} ${cat}</div>
                <div class="comparison-bars">
                    <div class="comparison-bar month-a" style="width: ${pctA}%">${formatAmount(valA)}</div>
                    <div class="comparison-bar month-b" style="width: ${pctB}%">${formatAmount(valB)}</div>
                </div>
            </div>
        `;
    }).join('');
    
    document.getElementById('category-comparison').innerHTML = html;
}

function updateCompareChart(dataA, dataB, dateA, dateB) {
    const categories = new Set([...Object.keys(dataA), ...Object.keys(dataB)]);
    const catArray = Array.from(categories).sort();
    
    const ctx = document.getElementById('compareChart');
    if (compareChart) compareChart.destroy();
    
    compareChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: catArray,
            datasets: [
                {
                    label: dateA,
                    data: catArray.map(c => dataA[c] || 0),
                    backgroundColor: '#8b5cf6',
                    borderRadius: 8,
                    borderSkipped: false
                },
                {
                    label: dateB,
                    data: catArray.map(c => dataB[c] || 0),
                    backgroundColor: 'rgba(139, 92, 246, 0.4)',
                    borderRadius: 8,
                    borderSkipped: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#cbd5e1' }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return context.dataset.label + ': ' + formatAmount(context.parsed.y);
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return '₹' + (value / 1000).toFixed(0) + 'K';
                        },
                        color: '#cbd5e1'
                    },
                    grid: { color: '#334155' }
                },
                x: {
                    ticks: { color: '#cbd5e1' },
                    grid: { display: false }
                }
            }
        }
    });
}

// ============================================================================
// TAB SWITCHING
// ============================================================================

document.querySelectorAll('.tab-button').forEach(button => {
    button.addEventListener('click', (e) => {
        // Remove active class from all buttons and contents
        document.querySelectorAll('.tab-button').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        
        // Add active class to clicked button and corresponding content
        e.target.classList.add('active');
        const tabId = e.target.getAttribute('data-tab');
        document.getElementById(tabId).classList.add('active');
        
        // Load data for specific tabs
        if (tabId === 'dashboard') {
            loadDashboard();
        } else if (tabId === 'compare') {
            loadMonthlySelects().then(loadComparison);
        } else if (tabId === 'predict') {
            loadPredictAlert();
        } else if (tabId === 'profile') {
            loadProfile();
        }
    });
});
