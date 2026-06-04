import csv
import random
from datetime import datetime, timedelta

# Indian merchants and keywords
merchants_by_category = {
    'Food': [
        'Swiggy order #1245', 'Zomato delivery - Biryani House', 'Dominos Pizza Delivery',
        'BigBasket weekly grocery', 'McDonald\'s - Highway 1', 'Starbucks Coffee',
        'Blinkit grocery delivery', 'DMart - Weekly shopping', 'Haldiram\'s Snacks',
        'FreshMenu meal plan', 'EatFit meal box', 'Cafe Coffee Day',
        'Maggi noodles bulk order', 'Croma snacks delivery', 'ITC Aashirvaad atta',
        'Mother Diary milk subscription', 'Amul cheese purchase', 'Nestlé products',
        'Unilever ice cream', 'Britannia biscuits', 'Lay\'s chips bulk',
        'CCD cafe card recharge', 'Subway sandwich', 'KFC bucket meal'
    ],
    'Travel': [
        'Uber ride to office', 'Ola Cab premium', 'Metro Smart Card Recharge',
        'Indigo flight booking', 'SpiceJet Air Ticket', 'Goibibo hotel booking',
        'IRCTC train ticket', 'MakeMyTrip bus ticket', 'Redbus ticket purchase',
        'Ola ride to airport', 'Uber Eats delivery fee', 'Auto rickshaw payment',
        'Bus pass monthly', 'Train season ticket', 'Petrol pump refuel',
        'Car parking charges', 'Toll tax payment', 'Autorickshaw to station',
        'Rapido auto booking', 'Intra city cab', 'Long distance cab booking'
    ],
    'Bills': [
        'Monthly House Rent Payment', 'Airtel fiber broadband bill', 'BESCOM electricity bill',
        'Jio prepaid recharge 299', 'Water supply payment', 'BSNL Internet bill',
        'VI (Vodafone) postpaid', 'Insurance premium payment', 'Property tax payment',
        'Airtel fiber monthly bill', 'Dish TV subscription', 'Broadband unlimited plan',
        'Gas cylinder booking', 'Electricity meter payment', 'Society maintenance fees',
        'Emergency hospital bill', 'Doctor consultation fee', 'Medicine purchase pharmacy',
        'Dental treatment', 'Eye checkup and glasses', 'Vaccination charges'
    ],
    'Shopping': [
        'Amazon online shopping', 'Flipkart delivery order', 'Myntra clothing purchase',
        'Ajio fashion items', 'Nykaa makeup products', 'Unbox Therapy gadget',
        'Best Buy electronics', 'Croma laptop purchase', 'Redmi phone accessory',
        'Apple Watch band', 'Samsung TV wall mount', 'Sony headphones',
        'Mi band fitness tracker', 'Kindle e-reader', 'Smart home speaker',
        'USB-C cable pack', 'Phone charger fast', 'Screen protector glass',
        'Phone case premium', 'Laptop bag backpack', 'Travel suitcase luggag'
    ],
    'Entertainment': [
        'Netflix monthly subscription', 'Amazon Prime Video', 'Disney+ Hotstar',
        'BookMyShow movie tickets', 'PVR cinema tickets', 'Inox theatre seats',
        'YouTube Premium annual', 'Spotify music subscription', 'Audible audiobooks',
        'Steam game purchase', 'PlayStation Store', 'Xbox Game Pass',
        'Clash of Clans gems', 'PUBG Mobile UC purchase', 'Zynga slots coins',
        'Concert ticket booking', 'Comedy show ticket', 'Sports match ticket',
        'Theme park entry', 'Swimming pool membership', 'Gym membership annual'
    ]
}

# Generate 1000 expenses
expenses = []
categories = list(merchants_by_category.keys())
start_date = datetime(2026, 1, 1)

print("Generating 1000 Indian expense descriptions...")

for i in range(1000):
    category = random.choice(categories)
    description = random.choice(merchants_by_category[category])
    
    # Create varied expense amounts by category
    if category == 'Food':
        amount = random.uniform(150, 2000)
    elif category == 'Travel':
        amount = random.uniform(100, 3000)
    elif category == 'Bills':
        amount = random.uniform(500, 8000)
    elif category == 'Shopping':
        amount = random.uniform(500, 15000)
    else:  # Entertainment
        amount = random.uniform(200, 5000)
    
    # Random date within 6 months
    random_days = random.randint(0, 180)
    date = start_date + timedelta(days=random_days)
    
    expenses.append({
        'Description': description,
        'Category': category
    })

# Write to CSV
with open('expenses.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['Description', 'Category'])
    writer.writeheader()
    writer.writerows(expenses)

print(f"✓ Generated expenses.csv with {len(expenses)} rows")
print(f"Categories: {', '.join(categories)}")
print(f"Sample rows:")
for expense in expenses[:5]:
    print(f"  {expense['Description']} → {expense['Category']}")
