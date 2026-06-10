import os
import re
import sqlite3
import pickle
import json
from datetime import datetime, timedelta
import calendar
import threading
import time
from flask import Flask, jsonify, request, render_template, send_from_directory, session
from flask_cors import CORS
import numpy as np
from sklearn.linear_model import LinearRegression
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import requests as http_requests

# Load environment variables
load_dotenv()

app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')
CORS(app)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Absolute path for the database — works correctly on Render and locally
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'finance.db')

# Global variables for ML model
vectorizer = None
classifier = None
ml_active = False

# Database initialization
def init_db():
    """Initialize SQLite database with schema"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create expenses table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL
        )
    ''')
    
    # Create settings table for future use
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Insert seed data if table is empty
    cursor.execute('SELECT COUNT(*) FROM expenses')
    if cursor.fetchone()[0] == 0:
        seed_data = [
            (3500, 'Monthly House Rent Payment', 'Bills', '2026-03-01'),
            (1300, 'BigBasket weekly grocery', 'Food', '2026-03-10'),
            (3500, 'Monthly House Rent Payment', 'Bills', '2026-04-01'),
            (1200, 'Airtel fiber broadband bill', 'Bills', '2026-04-05'),
            (1500, 'Zomato dinner delivery', 'Food', '2026-04-15'),
            (3500, 'Monthly House Rent Payment', 'Bills', '2026-05-01'),
            (1200, 'BESCOM electricity bill payment', 'Bills', '2026-05-05'),
            (2100, 'Flipkart online shopping', 'Shopping', '2026-05-10'),
            (1000, 'Ola Cab ride to airport', 'Travel', '2026-05-15'),
            (6500, 'Emergency hospital bill', 'Bills', '2026-05-19'),
            (500, 'PVR movie tickets', 'Entertainment', '2026-05-19'),
            # June 2026 — current month seed data
            (3500, 'Monthly House Rent Payment', 'Bills', '2026-06-01'),
            (1400, 'BigBasket grocery order', 'Food', '2026-06-03'),
            (950,  'Swiggy lunch delivery', 'Food', '2026-06-05'),
            (1200, 'Airtel broadband bill', 'Bills', '2026-06-07'),
            (2500, 'Myntra clothing purchase', 'Shopping', '2026-06-08'),
            (800,  'Ola cab to office', 'Travel', '2026-06-09'),
        ]
        cursor.executemany(
            'INSERT INTO expenses (amount, description, category, date) VALUES (?, ?, ?, ?)',
            seed_data
        )
        print("✓ Inserted seed data")
    
    conn.commit()
    conn.close()
    print("✓ Database initialized (finance.db)")


def _get_saved_profile():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    def get_key(k, default=None):
        cursor.execute('SELECT value FROM settings WHERE key = ?', (k,))
        r = cursor.fetchone()
        return r[0] if r else default

    profile = {
        'name': get_key('profile_name', os.getenv('PROFILE_NAME', 'Family Finance Manager')),
        'email': get_key('profile_email', DEFAULT_ALERT_EMAIL),
        'member_since': get_key('profile_member_since', os.getenv('PROFILE_MEMBER_SINCE', '2026-03-01'))
    }
    conn.close()
    return profile


def _save_profile(name, email, member_since=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Upsert keys
    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('profile_name', name))
    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('profile_email', email))
    if member_since:
        cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('profile_member_since', member_since))
    conn.commit()
    conn.close()

def load_ml_model():
    """Load trained ML model and vectorizer"""
    global vectorizer, classifier, ml_active
    
    try:
        if os.path.exists('model.pkl') and os.path.exists('vectorizer.pkl'):
            with open('model.pkl', 'rb') as f:
                classifier = pickle.load(f)
            with open('vectorizer.pkl', 'rb') as f:
                vectorizer = pickle.load(f)
            ml_active = True
            print("✓ ML Model loaded (MultinomialNB)")
            return True
    except Exception as e:
        print(f"⚠️  ML Model load failed: {e}")
    
    ml_active = False
    return False

def classify_expense(description):
    """Classify expense using ML model with fallback"""
    # Fallback rules
    fallback_rules = {
        'Food': [
            'swiggy', 'zomato', 'dominos', 'mcdonalds', 'ccd', 'cafe', 'bigbasket', 'dmart', 'blinkit',
            'coffee', 'tea', 'chai', 'juice', 'cola', 'pepsi', 'cold drink', 'drinks', 'soda',
            'breakfast', 'lunch', 'dinner', 'meal', 'snacks', 'pizza', 'burger', 'roll', 'momos',
            'sandwich', 'vada pav', 'pav bhaji', 'biryani', 'briyani', 'bryani', 'bryani', 'thali', 'dosa', 'idli', 'samosa',
            'vegetables', 'vegetarian', 'veg', 'restaurant', 'canteen', 'mess', 'tiffin', 'sweet', 'bread',
            'paratha', 'rice', 'dal', 'sabzi', 'paneer', 'chicken', 'mutton', 'fish', 'seafood', 'egg', 'non veg', 'non-veg',
            'grocery', 'groceries', 'supermarket', 'food delivery', 'meal prep', 'cooking', 'bakery',
            'dessert', 'ice cream', 'chocolate', 'snack', 'fast food', 'takeaway', 'food order', 'food pickup',
            'food truck', 'street food', 'food stall', 'food cart', 'food vendor', 'food market', 'food festival'
        ],
        'Travel': ['uber', 'ola', 'metro', 'rapido', 'indigo', 'spicejet', 'irctc', 'redbus', 'flight', 'train', 'bus', 'cab', 'taxi', 'auto', 'rickshaw', 'parking', 'toll', 'travel', 'transport', 'commute', 'ride', 'fare', 'ticket', 'booking', 'reservation', 'car rental', 'bike rental', 'public transport', 'transportation'],
        'Bills': ['bill', 'electricity', 'rent', 'airtel', 'jio', 'vi', 'broadband', 'insurance', 'water', 'gas', 'phone', 'mobile', 'internet', 'subscription', 'netflix', 'prime', 'hotstar'],
        'Shopping': ['amazon', 'flipkart', 'myntra', 'ajio', 'nykaa', 'croma', 'electronics', 'clothing', 'apparel', 'shoes', 'fashion', 'furniture', 'home decor'],
        'Entertainment': ['netflix', 'amazon prime', 'hotstar', 'bookmyshow', 'pvr', 'inox', 'spotify', 'gaana', 'youtube', 'music', 'movie', 'concert', 'event', 'game', 'gaming']
    }
    
    # Rule-based classification first for strong food/drink keywords
    desc_lower = (description or '').lower()
    for category, keywords in fallback_rules.items():
        for keyword in keywords:
            if keyword and keyword in desc_lower:
                print(f"✓ classify_expense: rule match '{keyword}' -> {category}")
                return category, 0.85

    # Fall back to ML model only if no keyword match was found
    if ml_active and classifier and vectorizer:
        try:
            X = vectorizer.transform([description])
            pred = classifier.predict(X)[0]
            confidence = float(max(classifier.predict_proba(X)[0]))
            print(f"✓ classify_expense: ML -> {pred} ({confidence:.2f})")
            return pred, confidence
        except Exception as e:
            print(f"⚠️  ML prediction failed: {e}")

    print("ℹ️ classify_expense: no match, returning 'Other'")
    return 'Other', 0.5

def send_alert(email, predicted_amount, last_month_actual, difference, percentage):
    """Send budget alert via Gmail SMTP"""
    smtp_user = os.getenv('SMTP_USER')
    smtp_pass = os.getenv('SMTP_PASS')
    
    if not smtp_user or not smtp_pass:
        print("⚠️  SMTP credentials not configured in .env")
        return False
    
    try:
        # Format amounts
        pred_str = f"₹{int(predicted_amount):,}".replace(',', ',')
        actual_str = f"₹{int(last_month_actual):,}".replace(',', ',')
        diff_str = f"₹{int(difference):,}".replace(',', ',')
        
        # Determine trend
        trend = "📈 Increasing" if difference > 0 else "📉 Decreasing"
        
        # Email subject and body
        subject = "⚠️ Monthly Spend Alert - Smart Family Tracker"
        body = f"""
Hello,

Your spending this month is higher than last month.

💰 Current Month Spending: {pred_str}
💾 Previous Month Spending: {actual_str}
📊 Difference: {diff_str} ({percentage:.1f}%)
📈 Trend: {trend}

Please review your expenses and reduce unnecessary spending if possible.

Best regards,
Smart Family Finance Tracker Team
"""
        
        # Send email
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        
        print(f"✓ Alert sent to {email}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send alert: {e}")
        return False


# Default hardcoded alert email (per user requirement)
DEFAULT_ALERT_EMAIL = 'familyfinancialtracker@gmail.com'


def run_prediction_and_maybe_alert(email=None, auto=False):
    """Run linear regression prediction and send alert if predicted > last month actual.
    If `email` is None, uses DEFAULT_ALERT_EMAIL. Returns a result dict similar to /predict.
    """
    # Get all expenses from database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT amount, date FROM expenses ORDER BY date ASC')
    rows = cursor.fetchall()
    conn.close()

    if len(rows) < 2:
        return {'error': 'Not enough data to predict'}

    # Group by month
    monthly_totals = {}
    for amount, date_str in rows:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        month_key = date_obj.strftime('%Y-%m')
        monthly_totals[month_key] = monthly_totals.get(month_key, 0) + amount

    # Get last month actual
    sorted_months = sorted(monthly_totals.keys())
    last_month_actual = monthly_totals[sorted_months[-1]] if sorted_months else 0

    # Prepare data for linear regression
    X = np.arange(len(monthly_totals)).reshape(-1, 1)
    y = np.array(list(monthly_totals.values()))

    # Train linear regression
    model = LinearRegression()
    model.fit(X, y)

    # Predict next month
    next_month_idx = len(monthly_totals)
    predicted_amount = float(model.predict([[next_month_idx]])[0])
    predicted_amount = max(0, predicted_amount)

    # Calculate metrics
    difference = predicted_amount - last_month_actual
    percentage = (difference / last_month_actual * 100) if last_month_actual > 0 else 0
    trend = "Increasing" if difference > 0 else "Decreasing"

    # Comparison rule (no manual budget): predicted next month vs current month actual
    over_threshold = predicted_amount > last_month_actual

    # Use provided email or default
    target_email = email if email else DEFAULT_ALERT_EMAIL

    alert_sent = False
    if over_threshold and target_email:
        alert_sent = send_alert(target_email, predicted_amount, last_month_actual, difference, percentage)

    return {
        'predicted_amount': predicted_amount,
        'last_month_actual': last_month_actual,
        'difference': difference,
        'percentage': percentage,
        'trend': trend,
        'over_threshold': over_threshold,
        'alert_sent': alert_sent,
        'alert_message': (
            'Alert email sent successfully.' if alert_sent
            else ('Email failed but alert triggered' if over_threshold else 'No alert needed')
        ),
        'ml_active': ml_active
    }


def run_current_month_alert(email=None):
    """Compare current month spending to previous month and send alert if needed."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT amount, date FROM expenses ORDER BY date ASC')
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return {'error': 'No expense data available to compare'}

    monthly_totals = {}
    for amount, date_str in rows:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        month_key = date_obj.strftime('%Y-%m')
        monthly_totals[month_key] = monthly_totals.get(month_key, 0) + amount

    sorted_months = sorted(monthly_totals.keys())
    current_month_key = sorted_months[-1]
    current_month_actual = monthly_totals[current_month_key]
    previous_month_actual = monthly_totals[sorted_months[-2]] if len(sorted_months) > 1 else 0

    difference = current_month_actual - previous_month_actual
    percentage = (difference / previous_month_actual * 100) if previous_month_actual > 0 else 0
    trend = 'Increasing' if difference > 0 else 'Decreasing'
    over_threshold = False if len(sorted_months) < 2 else current_month_actual > previous_month_actual

    target_email = email if email else DEFAULT_ALERT_EMAIL
    alert_sent = False
    if over_threshold and target_email:
        alert_sent = send_alert(target_email, current_month_actual, previous_month_actual, difference, percentage)

    return {
        'current_month_actual': current_month_actual,
        'last_month_actual': previous_month_actual,
        'difference': difference,
        'percentage': percentage,
        'trend': trend,
        'over_threshold': over_threshold,
        'alert_sent': alert_sent,
        'email': target_email
    }


def _background_month_end_watcher():
    """Background thread that runs the prediction check on the last 5 days of each month."""
    print("🔁 Background scheduler started for month-end checks")
    while True:
        now = datetime.now()
        last_day = calendar.monthrange(now.year, now.month)[1]
        # Last 5 days: day > last_day - 5  (e.g., if last_day=30, days 26-30)
        if now.day > (last_day - 5):
            try:
                print(f"🔍 Running month-end check for {now.date()}")
                res = run_prediction_and_maybe_alert()
                if isinstance(res, dict) and res.get('over_threshold'):
                    print('⚠️ Month-end alert sent' if res.get('alert_sent') else '⚠️ Month-end alert failed')
            except Exception as e:
                print(f"⚠️ Background check error: {e}")

        # Sleep until next day at 09:00 local time
        next_run = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        sleep_seconds = (next_run - datetime.now()).total_seconds()
        if sleep_seconds < 60:
            sleep_seconds = 60
        time.sleep(sleep_seconds)

# ============================================================================
# FLASK ROUTES
# ============================================================================

@app.before_request
def ensure_db():
    """Re-initialize DB if it was wiped (Render ephemeral filesystem)."""
    if not os.path.exists(DB_PATH):
        init_db()

@app.route('/')
def index():
    """Serve index.html"""
    user = session.get('user')
    print(f"DEBUG: user={user}, user is None={user is None}")
    return render_template('index.html', ml_active=ml_active, user=user)

@app.route('/debug-template')
def debug_template():
    """Debug template rendering"""
    return render_template('index.html', ml_active=ml_active, user=None)

@app.route('/expenses', methods=['POST'])
def add_expense():
    """Add new expense with auto-prediction"""
    try:
        data = request.json
        amount = float(data.get('amount', 0))
        description = data.get('description', '')
        date = data.get('date', datetime.now().strftime('%Y-%m-%d'))
        category = data.get('category', '')
        
        # Auto-predict if category is "auto"
        if category.lower() == 'auto':
            category, _ = classify_expense(description)
        
        if not all([amount, description, category, date]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Insert into database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO expenses (amount, description, category, date) VALUES (?, ?, ?, ?)',
            (amount, description, category, date)
        )
        conn.commit()
        expense_id = cursor.lastrowid
        conn.close()
        
        return jsonify({
            'id': expense_id,
            'amount': amount,
            'description': description,
            'category': category,
            'date': date
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/expenses', methods=['GET'])
def get_expenses():
    """Get all expenses as JSON"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT id, amount, description, category, date FROM expenses ORDER BY date DESC')
        rows = cursor.fetchall()
        conn.close()
        
        expenses = [
            {
                'id': row[0],
                'amount': row[1],
                'description': row[2],
                'category': row[3],
                'date': row[4]
            }
            for row in rows
        ]
        
        return jsonify(expenses), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/expenses/<int:expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    """Delete expense by ID"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM expenses WHERE id = ?', (expense_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/classify', methods=['POST'])
def classify():
    """Classify expense description using ML"""
    try:
        data = request.json
        description = data.get('description', '')
        
        if not description:
            return jsonify({'error': 'Description required'}), 400
        
        category, confidence = classify_expense(description)
        
        return jsonify({
            'category': category,
            'confidence': confidence,
            'ml_active': ml_active
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/predict', methods=['POST'])
def predict():
    """Predict next month spending and compare with budget"""
    try:
        data = request.json or {}
        email = data.get('email') or None

        res = run_prediction_and_maybe_alert(email=email)
        if 'error' in res:
            return jsonify(res), 400

        res['over_budget'] = res.get('over_threshold', False)
        res['buffer'] = res.get('last_month_actual', 0) - res.get('predicted_amount', 0)

        # ── NEW: enhanced prediction fields ──────────────────────────────
        # difference and percentage are already in res from run_prediction_and_maybe_alert
        # Add trend label and simple fallback flag
        if 'trend' not in res:
            res['trend'] = 'Increasing' if res.get('difference', 0) > 0 else 'Decreasing'
        res['trend_direction'] = '📈 Increasing' if res.get('difference', 0) > 0 else '📉 Decreasing'

        return jsonify(res), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/predict_alert', methods=['GET'])
def predict_alert():
    """Compare current month to previous month and send alert if needed."""
    try:
        res = run_current_month_alert()
        if 'error' in res:
            return jsonify(res), 400
        return jsonify(res), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Simple login: POST { name, email } stores user in session and persists profile."""
    if request.method == 'GET':
        return render_template('login.html')

    try:
        data = request.json or request.form or {}
        name = data.get('name') or data.get('username')
        email = data.get('email')
        if not email:
            return jsonify({'error': 'Email required'}), 400

        # Use name fallback to localpart if not provided
        if not name:
            name = email.split('@')[0]

        member_since = _get_saved_profile().get('member_since') or datetime.now().strftime('%Y-%m-%d')
        session['user'] = {'name': name, 'email': email, 'member_since': member_since}
        _save_profile(name, email, member_since)

        return jsonify({'success': True, 'profile': session['user']}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return jsonify({'success': True}), 200


@app.route('/profile', methods=['GET'])
def profile():
    """Return a profile summary for the current session user or saved profile."""
    user = session.get('user')
    if user:
        return jsonify({
            'name': user.get('name'),
            'email': user.get('email'),
            'role': 'Primary Account',
            'member_since': user.get('member_since')
        }), 200

    # fallback to saved profile
    saved = _get_saved_profile()
    return jsonify({
        'name': saved.get('name'),
        'email': saved.get('email'),
        'role': 'Primary Account',
        'member_since': saved.get('member_since')
    }), 200


@app.route('/profile_update', methods=['POST'])
def profile_update():
    """Update saved profile and current session."""
    try:
        data = request.json or {}
        name = data.get('name')
        email = data.get('email')
        member_since = data.get('member_since')

        if not email or not name:
            return jsonify({'error': 'Name and email required'}), 400

        _save_profile(name, email, member_since)
        # update session if logged in
        if session.get('user'):
            session['user'].update({'name': name, 'email': email, 'member_since': member_since})

        return jsonify({'success': True, 'profile': {'name': name, 'email': email, 'member_since': member_since}}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/run_prediction_manual', methods=['POST'])
def run_prediction_manual():
    """Manual trigger for prediction & alert (uses default hardcoded email if alert needed)."""
    try:
        res = run_prediction_and_maybe_alert()
        if 'error' in res:
            return jsonify(res), 400
        res['over_budget'] = res.get('over_threshold', False)
        res['buffer'] = res.get('last_month_actual', 0) - res.get('predicted_amount', 0)
        return jsonify(res), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/status', methods=['GET'])
def api_status():
    """Return app status"""
    return jsonify({
        'ml_active': ml_active,
        'lr_active': True
    }), 200

# ============================================================================
# NEW FEATURE: OCR BILL UPLOAD
# ============================================================================

@app.route('/upload-bill', methods=['POST'])
def upload_bill():
    """Accept an image, send to OCR.space, extract amount, delete image immediately.
    Returns: { "amount": <float> } or { "error": "OCR failed, enter manually" }
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Save temp file — use absolute path so it works on Render
    temp_path = os.path.join(BASE_DIR, 'temp_bill.jpg')
    try:
        file.save(temp_path)

        ocr_api_key = os.getenv('OCR_API_KEY', '').strip()
        if not ocr_api_key:
            # Graceful fallback — don't block the user, just tell them to enter manually
            return jsonify({'error': 'OCR failed, enter manually'}), 200

        # Call OCR.space API
        with open(temp_path, 'rb') as img_file:
            response = http_requests.post(
                'https://api.ocr.space/parse/image',
                files={'filename': img_file},
                data={
                    'apikey': ocr_api_key,
                    'language': 'eng',
                    'isOverlayRequired': False,
                    'detectOrientation': True,
                    'scale': True,
                    'OCREngine': 2
                },
                timeout=30
            )

        result = response.json()
        parsed_text = ''
        if result.get('ParsedResults'):
            parsed_text = result['ParsedResults'][0].get('ParsedText', '')

        # Extract amount using regex — match common bill amount patterns
        # Looks for: Total, Amount, Rs, ₹, INR followed by a number
        amount = 0.0
        patterns = [
            r'(?:total|amount|grand\s*total|net\s*amount|bill\s*amount|payable)[^\d]*(\d[\d,]*\.?\d*)',
            r'(?:rs\.?|₹|inr)\s*(\d[\d,]*\.?\d*)',
            r'(\d[\d,]*\.\d{2})',   # any decimal number like 1,234.56
        ]
        for pattern in patterns:
            match = re.search(pattern, parsed_text, re.IGNORECASE)
            if match:
                raw = match.group(1).replace(',', '')
                try:
                    amount = float(raw)
                    break
                except ValueError:
                    continue

        if amount <= 0:
            return jsonify({'error': 'OCR failed, enter manually'}), 200

        return jsonify({'amount': round(amount, 2)}), 200

    except Exception as e:
        print(f"❌ OCR upload error: {e}")
        return jsonify({'error': 'OCR failed, enter manually'}), 200

    finally:
        # SECURITY: always delete the temp image
        if os.path.exists(temp_path):
            os.remove(temp_path)


# ============================================================================
# NEW FEATURE: SMART INSIGHTS
# ============================================================================

@app.route('/insights', methods=['GET'])
def insights():
    """Compare current month vs previous month and return a human-readable message.
    Returns: { "message": "Spending increased by 40%" } or { "message": "Not enough data" }
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT amount, date FROM expenses ORDER BY date ASC')
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return jsonify({'message': 'Not enough data'}), 200

        # Group by month
        monthly_totals = {}
        for amount, date_str in rows:
            month_key = datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y-%m')
            monthly_totals[month_key] = monthly_totals.get(month_key, 0) + amount

        sorted_months = sorted(monthly_totals.keys())

        if len(sorted_months) < 2:
            return jsonify({'message': 'Not enough data'}), 200

        current = monthly_totals[sorted_months[-1]]
        previous = monthly_totals[sorted_months[-2]]

        if previous == 0:
            return jsonify({'message': 'Not enough data'}), 200

        difference = current - previous
        percentage = abs(difference / previous * 100)
        direction = 'increased' if difference > 0 else 'decreased'

        current_label = datetime.strptime(sorted_months[-1] + '-01', '%Y-%m-%d').strftime('%B %Y')
        previous_label = datetime.strptime(sorted_months[-2] + '-01', '%Y-%m-%d').strftime('%B %Y')

        message = (
            f"Spending {direction} by {percentage:.1f}% "
            f"({current_label}: ₹{int(current):,} vs {previous_label}: ₹{int(previous):,})"
        )

        return jsonify({
            'message': message,
            'current_month': current_label,
            'previous_month': previous_label,
            'current_total': current,
            'previous_total': previous,
            'difference': difference,
            'percentage': round(percentage, 1),
            'direction': direction
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# NEW FEATURE: CATEGORY LIMIT ALERTS
# ============================================================================

# Hardcoded category limits (as per spec)
CATEGORY_LIMITS = {
    'Food': 5000,
    'Travel': 3000,
    'Shopping': 4000
}

@app.route('/category-alerts', methods=['GET'])
def category_alerts():
    """Check current month spending per category vs predefined limits.
    Returns: { "alerts": ["Food limit exceeded", ...], "totals": {...}, "limits": {...} }
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT amount, category, date FROM expenses ORDER BY date ASC')
        rows = cursor.fetchall()
        conn.close()

        # Current month key
        current_month = datetime.now().strftime('%Y-%m')

        # If no current-month data, use the latest available month
        current_month_rows = [(a, c) for a, c, d in rows if d.startswith(current_month)]
        if not current_month_rows:
            # Fall back to most recent month in data
            if rows:
                latest = sorted(set(d[:7] for _, _, d in rows))[-1]
                current_month_rows = [(a, c) for a, c, d in rows if d.startswith(latest)]

        # Sum per category
        category_totals = {}
        for amount, category in current_month_rows:
            category_totals[category] = category_totals.get(category, 0) + amount

        # Build alerts
        alerts = []
        for cat, limit in CATEGORY_LIMITS.items():
            total = category_totals.get(cat, 0)
            if total > limit:
                alerts.append(f"{cat} limit exceeded (₹{int(total):,} / ₹{int(limit):,})")

        return jsonify({
            'alerts': alerts,
            'totals': category_totals,
            'limits': CATEGORY_LIMITS
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("=" * 60)
    print("💰 Smart Family Finance Tracker - Starting...")
    print("=" * 60)
    
    # Initialize database
    init_db()
    
    # Load ML model
    load_ml_model()
    
    # Start background watcher thread for month-end automated alerts
    watcher = threading.Thread(target=_background_month_end_watcher, daemon=True)
    watcher.start()
    
    # Start Flask
    print("\n🚀 Starting Flask server...")
    print("=" * 60)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False, use_reloader=False)