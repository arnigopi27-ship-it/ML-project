# 💰 Smart Family Finance Tracker

A full-stack web application for tracking family finances with intelligent ML-powered category prediction and spending forecasting.

## 🎯 Features

✅ **Expense Tracking** - Add, view, and delete expenses with automatic category prediction  
✅ **ML Classification** - MultinomialNB classifier with rule-based fallback  
✅ **Spending Prediction** - Linear Regression forecasting for next month  
✅ **Budget Alerts** - Email notifications when spending exceeds budget  
✅ **Visual Analytics** - Interactive Chart.js dashboards  
✅ **Month Comparison** - Compare spending patterns across months  
✅ **Dark Theme** - Modern, responsive UI with deep navy/purple theme  
✅ **Indian Localization** - ₹ currency formatting, Indian number system  

## 🛠️ Tech Stack

**Backend:**
- Python 3.x
- Flask (API server)
- SQLite (database)
- scikit-learn (ML: CountVectorizer, MultinomialNB, LinearRegression)
- python-dotenv (environment variables)
- smtplib (Gmail email alerts)

**Frontend:**
- HTML5, CSS3, Vanilla JavaScript
- Chart.js 4.x (CDN)
- Responsive design (mobile-friendly)

## 📁 Project Structure

```
finacialtracker/
├── backend/
│   ├── app.py              # Flask API server
│   ├── model.py            # ML model training
│   ├── generate_data.py    # Training data generation
│   ├── .env                # Environment variables (not committed)
│   ├── finance.db          # SQLite database (auto-created)
│   ├── model.pkl           # Trained ML model (auto-created)
│   └── vectorizer.pkl      # ML vectorizer (auto-created)
├── frontend/
│   ├── templates/
│   │   └── index.html      # Main UI (4 tabs)
│   └── static/
│       ├── style.css       # Dark theme styling
│       └── script.js       # API calls & interactivity
├── requirements.txt        # Python dependencies
├── .gitignore             # Git exclusions
└── README.md              # This file
```

## 🚀 Quick Start

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Generate Training Data

Creates `expenses.csv` with 1000 realistic Indian expense descriptions:

```bash
cd backend
python generate_data.py
```

Expected output:
```
✓ Generated expenses.csv with 1000 rows
Categories: Food, Travel, Bills, Shopping, Entertainment
```

### Step 3: Train ML Model

Trains CountVectorizer + MultinomialNB classifier, saves `model.pkl` and `vectorizer.pkl`:

```bash
python model.py
```

Expected output:
```
✓ Loaded 1000 training samples
✓ Saved model.pkl
✓ Saved vectorizer.pkl
✓ Sample predictions:
  'Swiggy food delivery' → Food (92.4%)
  'Uber cab ride' → Travel (88.1%)
  ...
```

### Step 4: Start Flask Server

```bash
python app.py
```

Expected output:
```
════════════════════════════════════════════════════════════
💰 Smart Family Finance Tracker - Starting...
════════════════════════════════════════════════════════════
✓ Database initialized (finance.db)
✓ ML Model loaded (MultinomialNB)

🚀 Starting Flask server on http://127.0.0.1:5000
════════════════════════════════════════════════════════════
```

### Step 5: Open in Browser

Navigate to **http://127.0.0.1:5000** in your web browser.

## 📊 Application Tabs

### Tab 1: Dashboard 📊
- **Metric Cards:** This Month Total, Last Month Total, Month-over-Month Change, Total Count
- **Bar Chart:** Spending by category (all-time)
- **Expense List:** Scrollable recent expenses with delete buttons
- Category badges with color-coding

### Tab 2: Add Expense ➕
- **Form Fields:**
  - Amount (₹)
  - Date (date picker, defaults to today)
  - Description (text input)
  - Category (dropdown or "Auto Predict" option)
- **ML Prediction:** Click "Predict Category" to use MultinomialNB
- **Info Box:** Explains how the ML model works

### Tab 3: Predict & Alert 🔮
- **Inputs:** Monthly Budget (₹), Alert Email
- **Prediction Results:**
  - Large forecasted amount with "Linear Regression" label
  - Sub-cards: Your Budget, Last Month Actual, Change (₹ and %)
  - Trend indicator (📈 Increasing / 📉 Decreasing)
- **Alert Box:** Green if within budget, red with email confirmation if exceeds
- **Line Chart:** Historical actual spending (purple) + Linear Regression forecast (orange dashed)

### Tab 4: Compare Months ⚖️
- **Month Selectors:** Choose Month A and Month B
- **Comparison Cards:** Side-by-side totals
- **Difference Summary:** Amount and percentage change
- **Category Bars:** Horizontal progress bars comparing both months
- **Grouped Bar Chart:** Month A (solid purple) vs Month B (light purple)

## 📧 Email Alerts

To enable email alerts:

1. **Create Gmail App Password:**
   - Go to https://myaccount.google.com/apppasswords
   - Select "Mail" and "Windows Computer"
   - Copy the 16-character password

2. **Edit `backend/.env`:**
   ```
   SMTP_USER=your-email@gmail.com
   SMTP_PASS=your-16-character-app-password
   ```

3. **Use Predict & Alert tab:**
   - Enter your budget
   - Enter your email address
   - Click "Predict Next Month"
   - If prediction exceeds budget, alert email is sent automatically

## 🤖 ML Model Details

**CountVectorizer + MultinomialNB Classifier:**
- Trained on 1000 expense descriptions
- 5 categories: Food, Travel, Bills, Shopping, Entertainment
- Max features: 500
- Fallback rules if model not found:
  - Swiggy/Zomato → Food
  - Uber/Ola/Metro → Travel
  - Bill/Rent/Electricity → Bills
  - Amazon/Flipkart → Shopping
  - Netflix/Games → Entertainment

**LinearRegression Forecast:**
- Trained on monthly spending totals
- Predicts next month's spending
- Displayed with trend line chart

## 💾 Database Schema

**expenses table:**
```sql
CREATE TABLE expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount REAL NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    date TEXT NOT NULL  -- YYYY-MM-DD format
);
```

**Seed Data:** 11 sample expenses from March-May 2026 are inserted on first run.

## 📱 Responsive Design

- Desktop: Multi-column layouts, full charts
- Tablet: Adjusted grid columns
- Mobile: Single-column layout, scrollable lists

## 🎨 Color Scheme

**Background:** Deep navy (#0f172a) to dark (#020617)  
**Cards:** Slate (#1e293b)  
**Categories:**
- Food: Orange (#f97316)
- Travel: Blue (#3b82f6)
- Bills: Red (#ef4444)
- Shopping: Purple (#8b5cf6)
- Entertainment: Green (#10b981)
- Other: Gray (#64748b)

## 🔒 Security Notes

- `.env` file is git-ignored (never commit credentials)
- CORS enabled for local development
- No sensitive data in frontend code
- Database stored locally in `backend/finance.db`

## 🐛 Troubleshooting

**ML Model Not Found:**
- Run `python generate_data.py && python model.py`
- App will use rule-based fallback automatically

**Email Alerts Not Working:**
- Verify `.env` has correct SMTP credentials
- Check Gmail account allows app passwords
- Disable 2FA or use App Password instead of regular password

**Charts Not Loading:**
- Clear browser cache (Ctrl+Shift+Delete)
- Check browser console for JavaScript errors
- Verify Chart.js CDN is accessible

**Database Locked:**
- Close other Flask instances
- Delete `finance.db` and restart app to reinitialize

## 📖 API Endpoints

```
GET  /                    → Serve index.html
POST /expenses            → Add expense (auto-predict category)
GET  /expenses            → Return all expenses as JSON
DELETE /expenses/<id>     → Delete expense by ID
POST /classify            → Classify expense description (ML)
POST /predict             → Predict next month & send alert
GET  /api/status          → Return ML and LR model status
```

## 🚦 Status Badges

Top-right corner shows:
- 🤖 **MultinomialNB ML Active** (blue) - Model loaded successfully
- 📈 **LinearRegression Active** (green) - Prediction available

## 📊 Sample Workflow

1. **Add Expenses:**
   - Description: "Swiggy food delivery"
   - ML auto-predicts: "Food" (92%)
   - Submit → Added to dashboard

2. **View Dashboard:**
   - See monthly totals, MoM change
   - View all expenses with category badges
   - Interactive bar chart by category

3. **Predict Spending:**
   - Enter budget: ₹25,000
   - Enter email: you@gmail.com
   - See forecast + trend line chart
   - If over budget → Alert email sent

4. **Compare Months:**
   - Select March vs May
   - See totals, differences, category breakdowns
   - Analyze spending patterns

## 🎯 Next Steps (Future Enhancements)

- [ ] User authentication & multi-user support
- [ ] Recurring expense templates
- [ ] Custom budget limits by category
- [ ] Expense tags and search filters
- [ ] Mobile app (React Native)
- [ ] Export to CSV/PDF
- [ ] Weekly/daily spending insights
- [ ] Savings goals tracking

## 📝 License

This project is open source and available under the MIT License.

---

**Questions?** Check the info boxes in each tab for explanations of how features work!

**Happy tracking!** 💰📊
