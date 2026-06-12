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
    """OCR bill upload — image is processed in memory and never stored."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        file = request.files['file']
        if not file or file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        ocr_api_key = os.getenv('OCR_API_KEY', 'K89037235588957')

        ocr_response = requests.post(
            'https://api.ocr.space/parse/image',
            files={'file': (file.filename, file.stream, file.content_type)},
            data={
                'apikey': ocr_api_key,
                'language': 'eng',
                'isOverlayRequired': False,
                'detectOrientation': True,
                'scale': True,
            },
            timeout=30
        )

        ocr_data = ocr_response.json()
        if ocr_data.get('IsErroredOnProcessing'):
            err_msg = str(ocr_data.get('ErrorMessage', 'Unknown OCR error'))
            return jsonify({'error': 'OCR failed: ' + err_msg}), 500

        parsed_results = ocr_data.get('ParsedResults', [])
        if not parsed_results:
            return jsonify({'error': 'No text found in image. Try a clearer photo.'}), 400

        full_text = parsed_results[0].get('ParsedText', '')
        # Clean lines and filter out empty inputs
        lines_text = [line.strip() for line in full_text.split('\n') if line.strip()]

        # ════════════════════════════════════════════════════════════════════
        # STEP 1 — Detect image type: UPI payment screenshot OR paper receipt
        # ════════════════════════════════════════════════════════════════════
        upi_signatures = re.compile(
            r'\b(google\s*pay|gpay|phonepe|phone\s*pe|paytm|bhim|amazon\s*pay|'
            r'whatsapp\s*pay|payment\s*successful|paid\s*successfully|'
            r'upi\s*transaction|transaction\s*id|upi\s*id|rupees?\s+\w+\s+only)\b',
            re.IGNORECASE
        )
        receipt_signatures = re.compile(
            r'\b(subtotal|sub\s*total|gst|vat|cgst|sgst|igst|discount|'
            r'grand\s*total|net\s*total|bill\s*amount|invoice|receipt|'
            r'cashier|item|qty|quantity|mrp|rate)\b',
            re.IGNORECASE
        )
        
        upi_score = len(upi_signatures.findall(full_text))
        receipt_score = len(receipt_signatures.findall(full_text))
        is_upi = upi_score >= 1 and upi_score >= receipt_score

        # ════════════════════════════════════════════════════════════════════
        # HELPERS
        # ════════════════════════════════════════════════════════════════════
        def safe_float(s):
            """Parse numeric string → float, or None if invalid / out of range."""
            try:
                # Remove common OCR noise symbols but keep decimals
                clean_s = re.sub(r'[^\d.]', '', s.replace(',', ''))
                v = float(clean_s)
                return v if 1 <= v <= 1000000 else None
            except Exception:
                return None

        def is_noise(val, raw=''):
            if val is None:
                return True
            if val < 5:
                return True  # tiny quantities / items
            if 2000 <= val <= 2099:
                return True  # validation year match
            if len(raw.replace(',', '').replace('.', '')) > 8:
                return True  # transaction hash fragments
            return False

        masked_text = re.sub(r'[A-Za-z0-9]{16,}', '', full_text)
        bank_suffixes = set(re.findall(
            r'(?:bank|a/c|acct?)\s*[-–:]\s*(\d{4})', full_text, re.IGNORECASE
        ))

        amount = 0.0

        # ════════════════════════════════════════════════════════════════════
        # STEP 2 — Extract Amount
        # ════════════════════════════════════════════════════════════════════
        if is_upi:
            # ── UPI PATH ────────────────────────────────────────────────────
            rupee_pat = re.compile(
                r'(?:[\u20b9\u20a8]|Rs\.?|INR)\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d{1,7}(?:\.\d{1,2})?)',
                re.IGNORECASE
            )
            rupee_amounts = []
            for m in rupee_pat.finditer(full_text):
                raw = m.group(1)
                val = safe_float(raw)
                if val and not is_noise(val, raw) and raw.replace(',', '').split('.')[0] not in bank_suffixes:
                    rupee_amounts.append(val)

            if rupee_amounts:
                amount = max(rupee_amounts)

            if amount == 0:
                paid_kw = re.compile(r'\b(paid|amount|payment)\b', re.IGNORECASE)
                for line in lines_text:
                    if paid_kw.search(line):
                        nums = re.findall(r'(?<!\d)(\d{1,7}(?:\.\d{1,2})?)(?!\d)', line)
                        for n in reversed(nums):
                            val = safe_float(n)
                            if val and not is_noise(val, n):
                                amount = val
                                break
                    if amount:
                        break
        else:
            # ── RECEIPT PATH (FIXED) ─────────────────────────────────────────
            # Strict multi-layered keywords to target explicit Final Payment lines
            final_total_kw = re.compile(
                r'\b(grand\s*total|net\s*total|total\s*payable|net\s*payable|amount\s*payable|bill\s*amount)\b',
                re.IGNORECASE
            )
            
            # Target standard strict totals while ignoring labels that denote subcomponents
            plain_total_kw = re.compile(
                r'(?<!\b(sub|gst|tax|item|cgst|sgst|discount)\s)\btotal\b(?!\s+(qty|price|rate|item))',
                re.IGNORECASE
            )

            def get_last_number_from_line(text_line):
                # Strip text phrases to isolate values safely
                clean = re.sub(r'[₹₨€$£¥%]|Rs\.?|INR', '', text_line, flags=re.IGNORECASE)
                nums = re.findall(r'(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d{1,7}(?:\.\d{1,2})?)', clean)
                for n in reversed(nums):
                    val = safe_float(n)
                    if val and not is_noise(val, n):
                        return val
                return None

            # Pass A: Look from the bottom up for structural Grand Totals
            for line in reversed(lines_text):
                if final_total_kw.search(line):
                    val = get_last_number_from_line(line)
                    if val:
                        amount = val
                        break

            # Pass B: Scan for isolated clean Total targets
            if amount == 0:
                for line in reversed(lines_text):
                    if plain_total_kw.search(line):
                        val = get_last_number_from_line(line)
                        if val:
                            amount = val
                            break

            # Pass C: Fallback to evaluating remaining valid totals if keywords failed
            if amount == 0:
                rupee_pat = re.compile(r'(?:[\u20b9\u20a8]|Rs\.?|INR)\s*(\d{1,6}(?:\.\d{2})?)', re.IGNORECASE)
                all_rupee = list(rupee_pat.finditer(full_text))
                for m in reversed(all_rupee):
                    val = safe_float(m.group(1))
                    if val and not is_noise(val, m.group(1)):
                        amount = val
                        break

        # ════════════════════════════════════════════════════════════════════
        # STEP 3 — Extract Description (merchant name)
        # ════════════════════════════════════════════════════════════════════
        noise_line = re.compile(
            r'^('
            r'g\s*pay|google\s*pay|phonepe|phone\s*pe|paytm|bhim|amazon\s*pay|whatsapp\s*pay|'
            r'payment\s*(successful|failed|pending)|paid\s*successfully|'
            r'transaction\s*(successful|complete|id)|thank\s*you.*|'
            r'note|from|to|date|upi|rupees?\s+\w+|only|cashier.*|'
            r'keep\s*this.*|item\s*qty.*|item\s*price.*|'
            r'\+?[\d\s\-]{8,}'  
            r')$',
            re.IGNORECASE
        )

        def is_good_description(text):
            t = text.strip()
            if len(t) < 2:
                return False
            if noise_line.match(t):
                return False
            if re.match(r'^[\d\s₹Rs.,/\-:]+$', t):
                return False 
            if re.match(r'^[A-Z0-9\-]{8,}$', t):
                return False 
            return True

        description = ''

        if is_upi:
            for i, line in enumerate(lines_text):
                if re.search(r'\bpaid\s+to\b|\bto\s*:', line, re.IGNORECASE):
                    for j in range(i + 1, min(i + 4, len(lines_text))):
                        candidate = lines_text[j].strip()
                        if is_good_description(candidate):
                            description = candidate[:100]
                            break
                if description:
                    break

        if not description:
            for line in lines_text:
                if is_good_description(line):
                    description = line[:100]
                    break

        if not description:
            description = 'Bill from receipt'

        # ── Auto-classify ────────────────────────────────────────────────────
        category, confidence = classify_expense(description + ' ' + full_text[:300])

        return jsonify({
            'amount': round(amount, 2),
            'description': description,
            'category': category,
            'confidence': confidence,
        }), 200

    except requests.Timeout:
        return jsonify({'error': 'OCR service timed out. Please try again.'}), 408
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

if __name__ == '__main__':
    print("=" * 60)
    print("Smart Family Finance Tracker - Starting...")
    print("=" * 60)
    init_db()
    load_ml_model()
    watcher = threading.Thread(target=_background_month_end_watcher, daemon=True)
    watcher.start()
    print("\nFlask server starting at http://localhost:5000")
    print("=" * 60)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True, use_reloader=False)