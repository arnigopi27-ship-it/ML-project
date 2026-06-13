import os
import sqlite3
import pickle
import json
from datetime import datetime, timedelta
import calendar
import threading
import time
from flask import Flask, jsonify, request, render_template, session
from flask_cors import CORS
import numpy as np
from sklearn.linear_model import LinearRegression
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import re
import requests
import cv2
import pytesseract

# Configure Tesseract path (Only for local Windows development)
if os.name == 'nt':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Users\Arni\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'

# Load environment variables
load_dotenv()

# Absolute DB path — always resolves to backend/finance.db regardless of where Flask is run from
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'finance.db')

app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')
CORS(app)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-2026')

# Global ML model variables
vectorizer = None
classifier = None
ml_active = False

# Default alert email
DEFAULT_ALERT_EMAIL = 'familyfinancialtracker@gmail.com'


# ============================================================================
# DATABASE
# ============================================================================

def init_db():
    """Initialize SQLite database with schema and seed data"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

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
        ]
        cursor.executemany(
            'INSERT INTO expenses (amount, description, category, date) VALUES (?, ?, ?, ?)',
            seed_data
        )
        print("[OK] Inserted seed data")

    conn.commit()
    conn.close()
    print(f"[OK] Database initialized at: {DB_PATH}")


# ============================================================================
# PROFILE HELPERS
# ============================================================================

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
    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('profile_name', name))
    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('profile_email', email))
    if member_since:
        cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('profile_member_since', member_since))
    conn.commit()
    conn.close()


# ============================================================================
# ML MODEL
# ============================================================================

def load_ml_model():
    """Load trained ML model and vectorizer"""
    global vectorizer, classifier, ml_active
    try:
        base = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(base, 'model.pkl')
        vec_path = os.path.join(base, 'vectorizer.pkl')
        if os.path.exists(model_path) and os.path.exists(vec_path):
            with open(model_path, 'rb') as f:
                classifier = pickle.load(f)
            with open(vec_path, 'rb') as f:
                vectorizer = pickle.load(f)
            ml_active = True
            print("[OK] ML Model loaded")
            return True
    except Exception as e:
        print(f"[WARN] ML Model load failed: {e}")
    ml_active = False
    return False


def classify_expense(description):
    """Classify expense using keyword rules first, then ML fallback"""
    fallback_rules = {
        'Food': [
            'swiggy', 'zomato', 'dominos', 'mcdonalds', 'ccd', 'cafe', 'bigbasket', 'dmart', 'blinkit',
            'coffee', 'tea', 'chai', 'juice', 'cola', 'pepsi', 'cold drink', 'drinks', 'soda',
            'breakfast', 'lunch', 'dinner', 'meal', 'snacks', 'pizza', 'burger', 'roll', 'momos',
            'sandwich', 'vada pav', 'pav bhaji', 'biryani', 'thali', 'dosa', 'idli', 'samosa',
            'vegetables', 'vegetarian', 'veg', 'restaurant', 'canteen', 'mess', 'tiffin', 'sweet', 'bread',
            'paratha', 'rice', 'dal', 'sabzi', 'paneer', 'chicken', 'mutton', 'fish', 'seafood', 'egg',
            'grocery', 'groceries', 'supermarket', 'food delivery', 'bakery', 'dessert', 'ice cream',
            'chocolate', 'snack', 'fast food', 'takeaway', 'food order', 'food truck', 'street food'
        ],
        'Travel': [
            'uber', 'ola', 'metro', 'rapido', 'indigo', 'spicejet', 'irctc', 'redbus', 'flight',
            'train', 'bus', 'cab', 'taxi', 'auto', 'rickshaw', 'parking', 'toll', 'travel',
            'transport', 'commute', 'ride', 'fare', 'ticket', 'booking', 'reservation',
            'car rental', 'bike rental', 'public transport', 'airport'
        ],
        'Bills': [
            'bill', 'electricity', 'rent', 'airtel', 'jio', 'vi', 'broadband', 'insurance',
            'water', 'gas', 'phone', 'mobile', 'internet', 'subscription', 'hospital',
            'medical', 'doctor', 'clinic', 'netflix', 'prime', 'hotstar', 'emi', 'loan',
            'bescom', 'bsnl', 'recharge'
        ],
        'Shopping': [
            'amazon', 'flipkart', 'myntra', 'ajio', 'nykaa', 'croma', 'electronics',
            'clothing', 'apparel', 'shoes', 'fashion', 'furniture', 'home decor', 'shopping',
            'meesho', 'snapdeal', 'tata cliq'
        ],
        'Entertainment': [
            'netflix', 'amazon prime', 'hotstar', 'bookmyshow', 'pvr', 'inox', 'spotify',
            'gaana', 'youtube', 'music', 'movie', 'concert', 'event', 'game', 'gaming',
            'steam', 'playstation', 'xbox', 'cinema', 'theatre'
        ]
    }

    desc_lower = (description or '').lower()
    for category, keywords in fallback_rules.items():
        for keyword in keywords:
            if keyword and keyword in desc_lower:
                return category, 0.92

    if ml_active and classifier and vectorizer:
        try:
            X = vectorizer.transform([description])
            pred = classifier.predict(X)[0]
            confidence = float(max(classifier.predict_proba(X)[0]))
            return pred, confidence
        except Exception as e:
            print(f"⚠️  ML prediction failed: {e}")

    return 'Other', 0.5


# ============================================================================
# EMAIL ALERTS
# ============================================================================

def send_alert(email, current_amount, last_amount, difference, percentage):
    """Send budget alert via Gmail SMTP — reads EMAIL_USER/EMAIL_PASS or SMTP_USER/SMTP_PASS"""
    smtp_user = os.getenv('SMTP_USER') or os.getenv('EMAIL_USER')
    smtp_pass = os.getenv('SMTP_PASS') or os.getenv('EMAIL_PASS')

    if not smtp_user or not smtp_pass:
        print("⚠️  SMTP credentials not configured in .env")
        return False

    try:
        trend = "📈 Increasing" if difference > 0 else "📉 Decreasing"
        subject = "⚠️ Monthly Spend Alert - Smart Family Finance Tracker"
        body = f"""Hello,

Your spending this month is higher than last month.

💰 Current Month Spending: ₹{int(current_amount):,}
💾 Previous Month Spending: ₹{int(last_amount):,}
📊 Difference: ₹{int(difference):,} ({percentage:.1f}%)
📈 Trend: {trend}

Please review your expenses and reduce unnecessary spending if possible.

Best regards,
Smart Family Finance Tracker
"""
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
        print(f"[OK] Alert sent to {email}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send alert: {e}")
        return False


# ============================================================================
# PREDICTION HELPERS
# ============================================================================

def run_prediction_and_maybe_alert(email=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT amount, date FROM expenses ORDER BY date ASC')
    rows = cursor.fetchall()
    conn.close()

    if len(rows) < 2:
        return {'error': 'Not enough data to predict'}

    monthly_totals = {}
    for amount, date_str in rows:
        month_key = datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y-%m')
        monthly_totals[month_key] = monthly_totals.get(month_key, 0) + amount

    sorted_months = sorted(monthly_totals.keys())
    last_month_actual = monthly_totals[sorted_months[-1]]

    X = np.arange(len(monthly_totals)).reshape(-1, 1)
    y = np.array(list(monthly_totals.values()))
    model = LinearRegression()
    model.fit(X, y)

    predicted_amount = max(0, float(model.predict([[len(monthly_totals)]])[0]))
    difference = predicted_amount - last_month_actual
    percentage = (difference / last_month_actual * 100) if last_month_actual > 0 else 0
    over_threshold = predicted_amount > last_month_actual

    target_email = email or DEFAULT_ALERT_EMAIL
    alert_sent = False
    if over_threshold:
        alert_sent = send_alert(target_email, predicted_amount, last_month_actual, difference, percentage)

    return {
        'predicted_amount': predicted_amount,
        'last_month_actual': last_month_actual,
        'difference': difference,
        'percentage': percentage,
        'trend': 'Increasing' if difference > 0 else 'Decreasing',
        'over_threshold': over_threshold,
        'alert_sent': alert_sent,
        'ml_active': ml_active
    }


def run_current_month_alert(email=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT amount, date FROM expenses ORDER BY date ASC')
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return {'error': 'No expense data available to compare'}

    monthly_totals = {}
    for amount, date_str in rows:
        month_key = datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y-%m')
        monthly_totals[month_key] = monthly_totals.get(month_key, 0) + amount

    sorted_months = sorted(monthly_totals.keys())
    current_month_actual = monthly_totals[sorted_months[-1]]
    previous_month_actual = monthly_totals[sorted_months[-2]] if len(sorted_months) > 1 else 0

    difference = current_month_actual - previous_month_actual
    percentage = (difference / previous_month_actual * 100) if previous_month_actual > 0 else 0
    over_threshold = len(sorted_months) >= 2 and current_month_actual > previous_month_actual

    target_email = email or DEFAULT_ALERT_EMAIL
    alert_sent = False
    if over_threshold:
        alert_sent = send_alert(target_email, current_month_actual, previous_month_actual, difference, percentage)

    return {
        'current_month_actual': current_month_actual,
        'last_month_actual': previous_month_actual,
        'difference': difference,
        'percentage': percentage,
        'trend': 'Increasing' if difference > 0 else 'Decreasing',
        'over_threshold': over_threshold,
        'alert_sent': alert_sent,
        'email': target_email
    }


def _background_month_end_watcher():
    print("[INFO] Background scheduler started")
    while True:
        now = datetime.now()
        last_day = calendar.monthrange(now.year, now.month)[1]
        if now.day > (last_day - 5):
            try:
                res = run_prediction_and_maybe_alert()
                if isinstance(res, dict) and res.get('over_threshold'):
                    print('[ALERT] Month-end alert triggered')
            except Exception as e:
                print(f"[ERROR] Background check error: {e}")
        next_run = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        sleep_seconds = max((next_run - datetime.now()).total_seconds(), 60)
        time.sleep(sleep_seconds)


# ============================================================================
# FLASK ROUTES
# ============================================================================

@app.route('/')
def index():
    user = session.get('user')
    return render_template('index.html', ml_active=ml_active, user=user)


@app.route('/api/check-login', methods=['GET'])
def check_login():
    """Check if current session has a logged-in user"""
    user = session.get('user')
    if user:
        return jsonify({'logged_in': True, 'user': user}), 200
    return jsonify({'logged_in': False}), 200


@app.route('/expenses', methods=['GET'])
def get_expenses():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT id, amount, description, category, date FROM expenses ORDER BY date DESC')
        rows = cursor.fetchall()
        conn.close()
        expenses = [
            {'id': r[0], 'amount': r[1], 'description': r[2], 'category': r[3], 'date': r[4]}
            for r in rows
        ]
        return jsonify(expenses), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/expenses', methods=['POST'])
def add_expense():
    try:
        data = request.json
        amount = float(data.get('amount', 0))
        description = data.get('description', '').strip()
        date = data.get('date', datetime.now().strftime('%Y-%m-%d'))
        category = data.get('category', '').strip()

        # Auto-classify if category missing or set to 'auto'
        if not category or category.lower() == 'auto':
            category, _ = classify_expense(description)

        if not all([amount > 0, description, category, date]):
            return jsonify({'error': 'Missing or invalid required fields'}), 400

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


@app.route('/expenses/<int:expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
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
    try:
        data = request.json
        description = data.get('description', '')
        if not description:
            return jsonify({'error': 'Description required'}), 400
        category, confidence = classify_expense(description)
        return jsonify({'category': category, 'confidence': confidence, 'ml_active': ml_active}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/upload-bill', methods=['POST'])
def upload_bill():
    """Tesseract OCR to extract amount and description from bill image"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']
        if not file or file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        file_bytes = file.read()
        np_arr = np.frombuffer(file_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if img is None:
            return jsonify({'error': 'Invalid image file'}), 400

        # Preprocess image
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

        # Extract text using Tesseract
        text = pytesseract.image_to_string(thresh)
        
        # Parse Amount and Description
        amount = 0.0
        description = "Expense"
        
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # 1. Amount Extraction Logic (Template Based)
        amount = 0.0
        
        # TEMPLATE 1: Look for explicit "Total" row (handles Tesseract splitting wide lines)
        for i, line in enumerate(lines):
            line_clean = line.replace(',', '')
            line_lower = line_clean.lower()
            
            # If the line contains "total" but not "subtotal"
            if re.search(r'\btotal\b', line_lower) and not re.search(r'subtotal|sub total', line_lower):
                # Grab all numbers on this line
                nums = re.findall(r'\b\d+(?:\.\d+)?\b', line_clean)
                if nums:
                    amount = float(nums[-1])
                    break
                else:
                    # Sometimes Tesseract puts the number on the next line if there's a big gap
                    for next_line in lines[i+1:i+3]:
                        nums_next = re.findall(r'\b\d+(?:\.\d+)?\b', next_line.replace(',', ''))
                        if nums_next:
                            amount = float(nums_next[-1])
                            break
                    if amount != 0.0:
                        break
                        
        # TEMPLATE 2: If no "Total" row exists, look for explicit Currency Symbols
        if amount == 0.0:
            explicit_amounts = []
            for line in lines:
                line_clean = line.replace(',', '')
                curr_matches = re.findall(r'(?:₹|Rs\.?|INR)\s*(\d+(?:\.\d+)?)', line_clean, re.IGNORECASE)
                for m in curr_matches:
                    val = float(m)
                    if val > 0:
                        explicit_amounts.append(val)
            
            if explicit_amounts:
                amount = float(max(explicit_amounts))
                
        # TEMPLATE 3: Ultimate Fallback -> Largest Decimal Number
        # If the currency symbol was misread by OCR (very common), 
        # we safely pick the largest number that has decimals (e.g. 250.00).
        # This completely ignores phone numbers, zip codes, dates, etc.
        if amount == 0.0:
            decimal_amounts = []
            for line in lines:
                line_clean = line.replace(',', '')
                dec_matches = re.findall(r'\b\d+\.\d{2}\b', line_clean)
                for m in dec_matches:
                    val = float(m)
                    if val > 0:
                        decimal_amounts.append(val)
            
            if decimal_amounts:
                amount = float(max(decimal_amounts))
            
        # 2. Description Extraction Logic
        paid_to_found = False
        ignore_words = ['transaction', 'date', 'upi', 'total']
        
        for i, line in enumerate(lines):
            if "paid to" in line.lower():
                if i + 1 < len(lines):
                    next_line = lines[i+1]
                    # Check if next_line is not just numbers
                    if not re.search(r'^\d+(\.\d+)?$', next_line.replace(',', '')):
                        description = next_line
                        paid_to_found = True
                        break
        
        if not paid_to_found:
            for line in lines:
                line_lower = line.lower()
                # Ignore if contains ignore words
                if any(w in line_lower for w in ignore_words):
                    continue
                # Ignore if it's just numbers and punctuation
                if re.match(r'^[\d\W_]+$', line):
                    continue
                # Found meaningful line
                description = line
                break
                
        description = description[:100]

        if amount == 0.0:
            return jsonify({'error': 'Could not read amount from bill. Try a clearer photo.'}), 400

        # Auto Classify
        category, confidence = classify_expense(description)

        return jsonify({
            'amount': amount,
            'description': description,
            'category': category,
            'confidence': confidence,
            'raw_text': text
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/predict', methods=['POST'])
def predict():
    try:
        data = request.json or {}
        res = run_prediction_and_maybe_alert(email=data.get('email'))
        if 'error' in res:
            return jsonify(res), 400
        res['over_budget'] = res.get('over_threshold', False)
        res['buffer'] = res.get('last_month_actual', 0) - res.get('predicted_amount', 0)
        return jsonify(res), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/predict_alert', methods=['GET'])
def predict_alert():
    try:
        res = run_current_month_alert()
        if 'error' in res:
            return jsonify(res), 400
        return jsonify(res), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/insights', methods=['GET'])
def insights():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT amount, date FROM expenses").fetchall()
        conn.close()

        if len(rows) < 2:
            return jsonify({"message": "Add more expenses to see insights.", "change": 0})

        monthly = {}
        for row in rows:
            month = row["date"][:7]
            monthly[month] = monthly.get(month, 0) + row["amount"]

        months = sorted(monthly.keys())
        last = monthly[months[-1]]
        prev = monthly[months[-2]]
        change = ((last - prev) / prev * 100) if prev else 0

        if change > 0:
            msg = f"⚠️ Spending increased by {round(change)}% compared to last month"
        elif change < 0:
            msg = f"✅ Spending decreased by {round(abs(change))}% compared to last month"
        else:
            msg = "➡️ Spending is the same as last month"

        return jsonify({"message": msg, "change": change, "current": last, "previous": prev})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/category-alerts', methods=['GET'])
def category_alerts():
    """Return category totals with limits and percentage for UI progress bars"""
    try:
        limits = {"Food": 5000, "Travel": 3000, "Shopping": 4000}

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT amount, category FROM expenses").fetchall()
        conn.close()

        totals = {}
        for row in rows:
            cat = row["category"]
            totals[cat] = totals.get(cat, 0) + row["amount"]

        result = []
        for cat, limit in limits.items():
            total = totals.get(cat, 0)
            pct = min(int((total / limit) * 100), 100)
            result.append({
                'category': cat,
                'total': total,
                'limit': limit,
                'percentage': pct,
                'exceeded': total > limit
            })

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    try:
        data = request.json or request.form or {}
        name = (data.get('name') or data.get('username') or '').strip()
        email = (data.get('email') or '').strip()
        if not email:
            return jsonify({'error': 'Email is required'}), 400
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
    user = session.get('user')
    if user:
        return jsonify({
            'name': user.get('name'),
            'email': user.get('email'),
            'role': 'Primary Account',
            'member_since': user.get('member_since')
        }), 200
    saved = _get_saved_profile()
    return jsonify({
        'name': saved.get('name'),
        'email': saved.get('email'),
        'role': 'Primary Account',
        'member_since': saved.get('member_since')
    }), 200


@app.route('/profile_update', methods=['POST'])
def profile_update():
    try:
        data = request.json or {}
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        member_since = data.get('member_since')
        if not name or not email:
            return jsonify({'error': 'Name and email are required'}), 400
        _save_profile(name, email, member_since)
        if session.get('user'):
            session['user'].update({'name': name, 'email': email, 'member_since': member_since})
        return jsonify({'success': True, 'profile': {'name': name, 'email': email, 'member_since': member_since}}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/run_prediction_manual', methods=['POST'])
def run_prediction_manual():
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
    return jsonify({'ml_active': ml_active, 'lr_active': True}), 200


# ============================================================================
# ENTRY POINT
# ============================================================================

# Initialize core services automatically when imported by Gunicorn
print("=" * 60)
print("Smart Family Finance Tracker - Initializing core services...")
init_db()
load_ml_model()
try:
    watcher = threading.Thread(target=_background_month_end_watcher, daemon=True)
    watcher.start()
except Exception as e:
    print(f"Watcher start failed: {e}")
print("=" * 60)

if __name__ == '__main__':
    print("\nFlask server starting at http://localhost:5000")
    print("=" * 60)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True, use_reloader=False)