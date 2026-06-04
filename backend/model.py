import pandas as pd
import pickle
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
import os

def train_model():
    """Train ML model on expenses.csv"""
    print("🤖 Training ML Model...")
    
    # Check if expenses.csv exists
    if not os.path.exists('expenses.csv'):
        print("❌ expenses.csv not found. Run generate_data.py first!")
        return False
    
    try:
        # Load data
        df = pd.read_csv('expenses.csv')
        print(f"✓ Loaded {len(df)} training samples")
        print(f"✓ Categories: {df['Category'].unique().tolist()}")
        
        # Train vectorizer and classifier
        vectorizer = CountVectorizer(max_features=500, lowercase=True, stop_words='english')
        X = vectorizer.fit_transform(df['Description'])
        y = df['Category']
        
        classifier = MultinomialNB()
        classifier.fit(X, y)
        
        # Save models
        with open('model.pkl', 'wb') as f:
            pickle.dump(classifier, f)
        print("✓ Saved model.pkl")
        
        with open('vectorizer.pkl', 'wb') as f:
            pickle.dump(vectorizer, f)
        print("✓ Saved vectorizer.pkl")
        
        # Test predictions
        test_descriptions = [
            'Swiggy food delivery',
            'Uber cab ride',
            'Electricity bill payment',
            'Amazon shopping',
            'Netflix subscription'
        ]
        
        print("\n✓ Sample predictions:")
        for desc in test_descriptions:
            X_test = vectorizer.transform([desc])
            pred = classifier.predict(X_test)[0]
            confidence = max(classifier.predict_proba(X_test)[0])
            print(f"  '{desc}' → {pred} ({confidence:.1%})")
        
        return True
        
    except Exception as e:
        print(f"❌ Error training model: {e}")
        return False

if __name__ == '__main__':
    success = train_model()
    if success:
        print("\n✅ ML Model training complete!")
    else:
        print("\n❌ ML Model training failed!")
