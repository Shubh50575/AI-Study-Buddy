# backend/ml_utils.py

import pickle
import os
from typing import List, Dict
import nltk
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from rake_nltk import Rake

# Ensure stopwords are available
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)

# ------------------------------------------------------------------
# 1. Topic Classification: Naive Bayes + TF-IDF
# ------------------------------------------------------------------
class TopicClassifier:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(stop_words='english', max_features=5000)
        self.model = MultinomialNB()
        self.is_trained = False

    def train(self, texts: List[str], labels: List[str]):
        """Train the classifier on a list of texts and corresponding category labels."""
        X = self.vectorizer.fit_transform(texts)
        self.model.fit(X, labels)
        self.is_trained = True

    def predict(self, text: str) -> Dict[str, any]:
        """Predict category and confidence for a single text."""
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first.")
        X = self.vectorizer.transform([text])
        pred_label = self.model.predict(X)[0]
        proba = self.model.predict_proba(X)[0].max()
        return {"category": pred_label, "confidence": round(float(proba), 3)}

    def save(self, path: str):
        """Save trained model + vectorizer to disk."""
        if not self.is_trained:
            raise ValueError("Model not trained yet.")
        with open(path, 'wb') as f:
            pickle.dump({
                'vectorizer': self.vectorizer,
                'model': self.model
            }, f)

    def load(self, path: str):
        """Load pre-trained model from disk."""
        with open(path, 'rb') as f:
            data = pickle.load(f)
        self.vectorizer = data['vectorizer']
        self.model = data['model']
        self.is_trained = True


# ------------------------------------------------------------------
# 2. Keyword Extraction: RAKE (bonus) + TF-IDF (mandatory)
# ------------------------------------------------------------------
class RAKEKeywordExtractor:
    def __init__(self):
        self.rake = Rake()

    def extract(self, text: str, top_n: int = 5) -> List[str]:
        """Extract key phrases using RAKE."""
        if not text:
            return []
        self.rake.extract_keywords_from_text(text)
        return self.rake.get_ranked_phrases()[:top_n]


class TFIDFKeywordExtractor:
    def __init__(self, corpus: List[str] = None):
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words='english', max_features=1000)
        if corpus:
            self.fit(corpus)

    def fit(self, corpus: List[str]):
        """Fit TF-IDF vectorizer on a background corpus (e.g., all past topics)."""
        self.vectorizer.fit(corpus)

    def extract(self, text: str, top_n: int = 5) -> List[str]:
        """Extract keywords from a single document using fitted TF-IDF."""
        if not hasattr(self.vectorizer, 'idf_'):
            raise ValueError("Call fit() first with a background corpus.")
        tfidf_matrix = self.vectorizer.transform([text])
        feature_names = self.vectorizer.get_feature_names_out()
        scores = tfidf_matrix.toarray()[0]
        # Sort by score descending
        top_indices = scores.argsort()[-top_n:][::-1]
        keywords = [feature_names[i] for i in top_indices if scores[i] > 0]
        return keywords

    def save(self, path: str):
        with open(path, 'wb') as f:
            pickle.dump(self.vectorizer, f)

    def load(self, path: str):
        with open(path, 'rb') as f:
            self.vectorizer = pickle.load(f)