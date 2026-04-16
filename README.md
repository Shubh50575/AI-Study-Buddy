# 🤖 AI Study Buddy

AI Smart Buddy is a full-stack intelligent study assistant built with FastAPI backend and React frontend that helps students generate notes, quizzes, flashcards, and explanations using AI, featuring PDF/TXT export functionality, secure JWT authentication, search history tracking, and fully responsive design.
---

## 🚀 Features

- 🧠 AI-powered content generation (notes, quizzes, flashcards)
- 🔐 User authentication (JWT-based)
- 📄 Export notes as PDF/TXT
- 🏷️ Keyword extraction (RAKE algorithm)
- 📊 Topic classification using Machine Learning
- 💾 History tracking
- ⚡ Fast and responsive UI

---

## 🏗️ Tech Stack

### 🔹 Backend
- Python 3.13+
- FastAPI
- Uvicorn
- SQLAlchemy
- SQLite
- Pydantic
- bcrypt (password hashing)
- JWT (python-jose)
- reportlab (PDF generation)
- scikit-learn (ML)
- nltk + rake-nltk (NLP)

---

### 🔹 Frontend
- React (Vite)
- JavaScript (ES6+)
- CSS
- Fetch API
- LocalStorage

---

### 🔹 Dev Tools
- VS Code
- Git
- Postman / Swagger UI
- npm / pip

---

## 🌐 API Integration

- OpenRouter API (GPT-4o-mini)
- Used for:
  - AI explanations
  - Quiz generation
  - Flashcards

---

## 📁 Project Structure

ai-smart-buddy/
│
├── backend/
│ ├── main.py
│ ├── models.py
│ ├── database.py
│ ├── auth_utils.py
│ ├── ml_utils.py
│ ├── requirements.txt
│ └── aistudybuddy.db
│
├── frontend/
│ ├── src/
│ │ ├── App.jsx
│ │ ├── App.css
│ │ └── main.jsx
│ ├── index.html
│ └── package.json
│
└── README.md


---

## 🔐 Authentication Flow

1. User registers/login
2. Password hashed using bcrypt
3. JWT token generated
4. Token stored in localStorage
5. Protected routes use Bearer token

---

## 🤖 Machine Learning

| Task                  | Algorithm              | Library         |
|----------------------|-----------------------|-----------------|
| Topic Classification | Naive Bayes + TF-IDF  | scikit-learn    |
| Keyword Extraction   | RAKE                  | rake-nltk       |

---
