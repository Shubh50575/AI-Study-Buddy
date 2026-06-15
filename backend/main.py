import os
import re
import json
import requests
import time
import random
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_, func
from pydantic import BaseModel, EmailStr
from database import Base, engine, get_db
import models, auth_utils
from validation_utils import validate_email_address, validate_mobile_number
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from dotenv import load_dotenv

# Import ML utils
from ml_utils import RAKEKeywordExtractor, TopicClassifier

load_dotenv()
Base.metadata.create_all(bind=engine)
app = FastAPI()

# ---------- CORS ----------
origins = [
    "https://ai-study-buddy-2-0bew.onrender.com",  # Your frontend URL
   "https://ai-study-buddy-1-6m0h.onrender.com",      # Your backend URL
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ---------- Initialize ML components ----------
rake_extractor = RAKEKeywordExtractor()

seed_training_data = [
    ("neural networks deep learning", "Technology"),
    ("history world war 2", "History"),
    ("python programming code", "Programming"),
    ("calculus derivatives integrals", "Mathematics"),
    ("human body anatomy", "Health"),
    ("business marketing strategy", "Business"),
    ("shakespeare hamlet", "Literature"),
    ("climate change global warming", "Science"),
]
train_texts = [item[0] for item in seed_training_data]
train_labels = [item[1] for item in seed_training_data]

topic_classifier = TopicClassifier()
topic_classifier.train(train_texts, train_labels)

# ---------- Pydantic Models ----------
class SignupReq(BaseModel):
    name: str
    email: EmailStr
    mobile: str
    password: str
    confirm_password: str

class LoginReq(BaseModel):
    identifier: str
    password: str

class MessageRequest(BaseModel):
    message: str

# ---------- Helper: Generate Fixed User ID ----------
def generate_user_id(name: str) -> str:
    """Generate a consistent user ID based on name (same user always gets same ID)"""
    name_part = re.sub(r'\s', '', name)[:6].capitalize()
    hash_val = hash(name) % 10000
    return f"{name_part}{abs(hash_val)}"

# ---------- AI Helper ----------
def call_ai(prompt):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "openai/gpt-3.5-turbo",
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        res = requests.post(url, headers=headers, json=data, timeout=60)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print("AI Error:", e)
        return f"AI Connection Error: {str(e)}"

def parse_json(raw_str):
    raw_str = re.sub(r'```json\s*|\s*```', '', raw_str.strip())
    match = re.search(r'(\[.*\]|\{.*\})', raw_str, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            return None
    return None

# ---------- Auth Endpoints ----------
@app.post("/signup")
def signup(user: SignupReq, db: Session = Depends(get_db)):
    if user.password != user.confirm_password:
        raise HTTPException(400, "Passwords do not match")
    
    if len(user.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters long")
    
    # Email validation: Must end with @gmail.com (case-insensitive)
    email = user.email.strip()
    if not email.lower().endswith("@gmail.com"):
        raise HTTPException(400, "Only Gmail addresses are allowed. Email must end with @gmail.com")
    
    # Normalize to lowercase for storage
    normalized_email = email.lower()
    
    # Mobile validation - only 10 digits (no +91, no prefix restrictions)
    mobile = user.mobile.strip()
    if not mobile.isdigit() or len(mobile) != 10:
        raise HTTPException(400, "Mobile number must be exactly 10 digits (0-9 only)")
    
    # Check existing email
    existing_email = db.query(models.User).filter(models.User.email == normalized_email).first()
    if existing_email:
        raise HTTPException(400, "Email already registered")
    
    # Check existing mobile
    existing_mobile = db.query(models.User).filter(models.User.mobile == mobile).first()
    if existing_mobile:
        raise HTTPException(400, "Mobile number already registered")
    
    user_id = generate_user_id(user.name)
    
    new_user = models.User(
        name=user.name.strip(),
        email=normalized_email,
        mobile=mobile,
        hashed_password=auth_utils.hash_password(user.password),
        user_id=user_id
    )
    
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "Registration failed. Please try again.")
    
    return {
        "message": "Signup successful! Please login.",
        "user_info": {
            "name": new_user.name,
            "email": new_user.email,
            "mobile": new_user.mobile,
            "user_id": user_id
        }
    }

@app.post("/login")
def login(req: LoginReq, db: Session = Depends(get_db)):
    if not req.identifier or not req.password:
        raise HTTPException(400, "All fields are required")
    
    identifier = req.identifier.strip()
    
    # Check if identifier looks like an email (contains @)
    if "@" in identifier:
        # Check if it's a Gmail address (case-insensitive)
        if not identifier.lower().endswith("@gmail.com"):
            raise HTTPException(400, "Only Gmail addresses are allowed for login")
        
        # Normalize email to lowercase for matching
        normalized_identifier = identifier.lower()
        user = db.query(models.User).filter(
            func.lower(models.User.email) == normalized_identifier
        ).first()
    else:
        # Mobile number - only 10 digits allowed (no prefix restrictions)
        if not identifier.isdigit() or len(identifier) != 10:
            raise HTTPException(400, "Mobile number must be exactly 10 digits")
        
        user = db.query(models.User).filter(
            models.User.mobile == identifier
        ).first()
    
    if not user:
        raise HTTPException(401, "Invalid email/mobile or password")
    
    if not auth_utils.verify_password(req.password, user.hashed_password):
        raise HTTPException(401, "Invalid email/mobile or password")
    
    user_id = generate_user_id(user.name)
    
    return {
        "message": "Login successful",
        "token": auth_utils.create_access_token({"sub": user.email, "id": user.id}),
        "user": {
            "name": user.name,
            "email": user.email,
            "mobile": user.mobile,
            "user_id": user_id
        }
    }

# ---------- Debug Endpoint (Remove in production) ----------
@app.get("/debug/users")
def debug_users():
    from database import SessionLocal
    db = SessionLocal()
    users = db.query(models.User).all()
    result = [{"name": u.name, "email": u.email, "mobile": u.mobile} for u in users]
    db.close()
    return {"users": result}

# ---------- AI Endpoints (Protected) ----------
@app.post("/explain")
def explain(data: MessageRequest, current_user=Depends(auth_utils.get_current_user), db: Session = Depends(get_db)):
    prompt = (
        f"Explain '{data.message}' with exactly these 4 sections.\n"
        "Format rules:\n"
        "- Use **Section Name:** as section header\n"
        "- For 'Explanation' and 'Real-use cases' sections: write each point on a new line starting with '1. ', '2. ', '3. ' etc.\n"
        "- For 'Definition' and 'Summary': write as a short paragraph\n"
        "- Put double newline between sections\n\n"
        "Sections: **Definition:** **Explanation:** **Real-use cases:** **Summary:**"
    )
    response = call_ai(prompt)
    keywords = rake_extractor.extract(data.message, top_n=5)
    category_info = topic_classifier.predict(data.message)
    history = models.History(
        user_id=current_user.id,
        topic=data.message,
        type="explain",
        keywords=",".join(keywords),
        category=category_info["category"],
        confidence=category_info["confidence"]
    )
    db.add(history)
    db.commit()
    return {"response": response}

@app.post("/generate-quiz")
def quiz(data: MessageRequest, current_user=Depends(auth_utils.get_current_user), db: Session = Depends(get_db)):
    # Calculate number of questions based on topic length (5 to 8)
    topic_length = len(data.message)
    
    # Length mapping: 1-10→5, 11-20→6, 21-30→7, 31+→8
    if topic_length <= 10:
        num_questions = 5
    elif topic_length <= 20:
        num_questions = 6
    elif topic_length <= 30:
        num_questions = 7
    else:
        num_questions = 8
    
    prompt = (
        f"Create exactly {num_questions} multiple choice questions on the topic: '{data.message}'.\n"
        "Return ONLY a valid JSON array, no extra text, no markdown.\n"
        "Format: [{\"question\": \"...\", \"options\": [\"A. ...\", \"B. ...\", \"C. ...\", \"D. ...\"], \"correct_answer\": \"...\"}]\n"
        "IMPORTANT: Randomly distribute correct answers among A, B, C, or D. Do not always put correct answer as A.\n"
        "Make questions diverse, challenging, and cover different aspects of the topic."
    )
    raw = call_ai(prompt)
    parsed = parse_json(raw)
    
    if not isinstance(parsed, list) or len(parsed) != num_questions:
        # Generate completely random fallback quiz (no templates)
        parsed = []
        option_labels = ["A", "B", "C", "D"]
        
        # Random words for variety
        random_verbs = ["is", "are", "was", "were", "can be", "could be", "should be", "might be"]
        random_adjectives = ["important", "basic", "advanced", "fundamental", "complex", "simple", "critical", "essential"]
        
        for i in range(num_questions):
            correct_label = random.choice(option_labels)
            random_num = random.randint(1000, 9999)
            random_verb = random.choice(random_verbs)
            random_adj = random.choice(random_adjectives)
            
            options_dict = {}
            for label in option_labels:
                if label == correct_label:
                    options_dict[label] = f"{label}. Correct answer for question {random_num}"
                else:
                    options_dict[label] = f"{label}. Incorrect choice {random.randint(1, 999)}"
            
            parsed.append({
                "question": f"Q{i+1}: What {random_verb} {random_adj} about {data.message[:20]}? (ID:{random_num})",
                "options": [options_dict["A"], options_dict["B"], options_dict["C"], options_dict["D"]],
                "correct_answer": options_dict[correct_label]
            })
    
    keywords = rake_extractor.extract(data.message, top_n=5)
    category_info = topic_classifier.predict(data.message)
    history = models.History(
        user_id=current_user.id,
        topic=data.message,
        type="quiz",
        keywords=",".join(keywords),
        category=category_info["category"],
        confidence=category_info["confidence"]
    )
    db.add(history)
    db.commit()
    return {"quiz": parsed, "total_questions": len(parsed)}


@app.post("/generate-flashcards")
def flash(data: MessageRequest, current_user=Depends(auth_utils.get_current_user), db: Session = Depends(get_db)):
    # Calculate number of flashcards based on topic length (5 to 8)
    topic_length = len(data.message)
    
    # Length mapping: 1-10→5, 11-20→6, 21-30→7, 31+→8
    if topic_length <= 10:
        num_cards = 5
    elif topic_length <= 20:
        num_cards = 6
    elif topic_length <= 30:
        num_cards = 7
    else:
        num_cards = 8
    
    prompt = (
        f"Create exactly {num_cards} flashcards for: '{data.message}'.\n"
        "Return ONLY a valid JSON array, no extra text, no markdown.\n"
        "Format: [{\"question\": \"...\", \"answer\": \"...\"}]\n"
        "Make flashcards cover key concepts, definitions, and important facts about the topic."
    )
    raw = call_ai(prompt)
    parsed = parse_json(raw)
    
    if not isinstance(parsed, list) or len(parsed) != num_cards:
        # Generate completely random fallback flashcards (no templates)
        parsed = []
        
        # Random words for variety
        random_question_words = ["What", "Why", "How", "When", "Where", "Which", "Who", "What makes", "What defines"]
        random_verbs = ["is", "are", "was", "can be", "could be", "should be", "represents", "means"]
        
        for i in range(num_cards):
            random_q_word = random.choice(random_question_words)
            random_verb = random.choice(random_verbs)
            random_num = random.randint(1000, 9999)
            random_answer_num = random.randint(1, 999)
            
            question = f"{random_q_word} {random_verb} {data.message[:25]}? (Card #{random_num})"
            answer = f"This is the answer for {data.message[:20]} - Reference: {random_answer_num}"
            
            parsed.append({
                "question": question,
                "answer": answer
            })
    
    keywords = rake_extractor.extract(data.message, top_n=5)
    category_info = topic_classifier.predict(data.message)
    history = models.History(
        user_id=current_user.id,
        topic=data.message,
        type="flashcards",
        keywords=",".join(keywords),
        category=category_info["category"],
        confidence=category_info["confidence"]
    )
    db.add(history)
    db.commit()
    return {"flashcards": parsed, "total_cards": len(parsed)}

# ---------- Export Endpoints ----------
@app.post("/export-txt")
def export_txt(data: dict, current_user=Depends(auth_utils.get_current_user)):
    content = data.get("content", "")
    topic = data.get("topic", "Notes")
    header = f"Study Notes : {topic}\n{'-' * 40}\n\n"
    final_content = header + content
    path = f"notes_{current_user.id}.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(final_content)
    return FileResponse(path, filename=f"{topic.replace(' ', '_')}_notes.txt")

@app.post("/export-pdf")
def export_pdf(data: dict, current_user=Depends(auth_utils.get_current_user)):
    from reportlab.lib.units import inch
    content = data.get("content", "")
    topic = data.get("topic", "Notes")
    path = f"notes_{current_user.id}.pdf"
    doc = SimpleDocTemplate(path)
    styles = getSampleStyleSheet()
    story = []
    title_style = styles['Title']
    story.append(Paragraph(f"Study Notes : {topic}", title_style))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("-" * 60, styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    for line in content.split("\n"):
        if line.strip():
            line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)
            story.append(Paragraph(line, styles['Normal']))
            story.append(Spacer(1, 0.1*inch))
    doc.build(story)
    return FileResponse(path, filename=f"{topic.replace(' ', '_')}_notes.pdf")

# ---------- History Endpoint ----------
@app.get("/history")
def get_history(current_user=Depends(auth_utils.get_current_user), db: Session = Depends(get_db)):
    history = db.query(models.History).filter(models.History.user_id == current_user.id).order_by(models.History.created_at.desc()).limit(20).all()
    return [{
        "id": h.id,
        "topic": h.topic,
        "type": h.type,
        "created_at": h.created_at.isoformat(),
        "keywords": h.keywords.split(",") if h.keywords else [],
        "category": h.category,
        "confidence": h.confidence
    } for h in history]

# ---------- Delete History ----------
@app.delete("/history/{history_id}")
def delete_history(history_id: int, current_user=Depends(auth_utils.get_current_user), db: Session = Depends(get_db)):
    history_entry = db.query(models.History).filter(models.History.id == history_id, models.History.user_id == current_user.id).first()
    if not history_entry:
        raise HTTPException(404, "History entry not found")
    db.delete(history_entry)
    db.commit()
    return {"message": "Deleted successfully"}

@app.delete("/history/clear/all")
def clear_all_history(current_user=Depends(auth_utils.get_current_user), db: Session = Depends(get_db)):
    db.query(models.History).filter(models.History.user_id == current_user.id).delete()
    db.commit()
    return {"message": "All history cleared"}

# ---------- ML Endpoints ----------
@app.post("/extract-keywords")
def extract_keywords(data: MessageRequest, current_user=Depends(auth_utils.get_current_user)):
    keywords = rake_extractor.extract(data.message, top_n=5)
    return {"keywords": keywords}

@app.post("/classify-topic")
def classify_topic(data: MessageRequest, current_user=Depends(auth_utils.get_current_user)):
    result = topic_classifier.predict(data.message)
    return result

# ---------- Ping Endpoint ----------
@app.get("/ping")
def ping():
    return {
        "status": "alive",
        "timestamp": time.time(),
        "message": "Server is running!"
    }



# import os
# import re
# import json
# import requests
# import time  # ✅ Add this for timestamp
# from fastapi import FastAPI, Depends, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import FileResponse
# from sqlalchemy.orm import Session
# from sqlalchemy.exc import IntegrityError
# from sqlalchemy import or_, func
# from pydantic import BaseModel, EmailStr
# from database import Base, engine, get_db
# import models, auth_utils
# from validation_utils import validate_email_address, validate_mobile_number
# from validation_utils import quick_email_syntax_check, quick_mobile_syntax_check
# from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
# from reportlab.lib.styles import getSampleStyleSheet
# from dotenv import load_dotenv

# # Import ML utils
# from ml_utils import RAKEKeywordExtractor, TopicClassifier

# load_dotenv()
# Base.metadata.create_all(bind=engine)
# app = FastAPI()

# # ---------- CORS ----------
# origins = [
#     "https://ai-study-buddy-2-0bew.onrender.com",  # Your frontend URL
#     "http://localhost:5173",                      # Local frontend (Vite)
#     "http://127.0.0.1:5173",                      # Local frontend (alternative)
#     "http://localhost:8000",                      # Local backend
#     "http://127.0.0.1:8000",                      # Local backend (alternative)
# ]

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # ---------- Initialize ML components ----------
# rake_extractor = RAKEKeywordExtractor()

# # Seed training data for topic classification (you can add more)
# seed_training_data = [
#     ("neural networks deep learning", "Technology"),
#     ("history world war 2", "History"),
#     ("python programming code", "Programming"),
#     ("calculus derivatives integrals", "Mathematics"),
#     ("human body anatomy", "Health"),
#     ("business marketing strategy", "Business"),
#     ("shakespeare hamlet", "Literature"),
#     ("climate change global warming", "Science"),
# ]
# train_texts = [item[0] for item in seed_training_data]
# train_labels = [item[1] for item in seed_training_data]

# topic_classifier = TopicClassifier()
# topic_classifier.train(train_texts, train_labels)

# # ---------- Pydantic Models ----------
# class SignupReq(BaseModel):
#     name: str
#     email: EmailStr
#     mobile: str
#     password: str
#     confirm_password: str

# class LoginReq(BaseModel):
#     identifier: str
#     password: str

# class MessageRequest(BaseModel):
#     message: str

# # ---------- AI Helper ----------
# def call_ai(prompt):
#     url = "https://openrouter.ai/api/v1/chat/completions"
#     headers = {
#         "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
#         "Content-Type": "application/json"
#     }
#     data = {
#         "model": "openai/gpt-3.5-turbo",  # or "meta-llama/llama-3-8b-instruct"
#         "messages": [{"role": "user", "content": prompt}]
#     }
#     try:
#         res = requests.post(url, headers=headers, json=data, timeout=30)
#         res.raise_for_status()
#         return res.json()["choices"][0]["message"]["content"]
#     except Exception as e:
#         print("AI Error:", e)
#         if res.status_code == 401:
#             return "Invalid API Key. Please check your OPENROUTER_API_KEY"
#         return f"AI Connection Error: {str(e)}"

# def parse_json(raw_str):
#     raw_str = re.sub(r'```json\s*|\s*```', '', raw_str.strip())
#     match = re.search(r'(\[.*\]|\{.*\})', raw_str, re.DOTALL)
#     if match:
#         try:
#             return json.loads(match.group(1))
#         except:
#             return None
#     return None

# # ---------- Auth Endpoints ----------
# @app.post("/signup")
# def signup(user: SignupReq, db: Session = Depends(get_db)):
#     # 1. Check if passwords match
#     if user.password != user.confirm_password:
#         raise HTTPException(400, "Passwords do not match")
    
#     # 2. Validate password strength
#     if len(user.password) < 6:
#         raise HTTPException(400, "Password must be at least 6 characters long")
    
#     # 3. Email Validation (Full verification)
#     email_validation = validate_email_address(user.email)
#     if not email_validation["valid"]:
#         raise HTTPException(400, email_validation["message"])
    
#     # 4. Mobile Number Validation
#     mobile_validation = validate_mobile_number(user.mobile, "IN")
#     if not mobile_validation["valid"]:
#         raise HTTPException(400, mobile_validation["message"])
    
#     # 5. Check if email already exists
#     existing_email = db.query(models.User).filter(models.User.email == user.email).first()
#     if existing_email:
#         raise HTTPException(400, "Email already registered")
    
#     # 6. Check if mobile already exists
#     existing_mobile = db.query(models.User).filter(models.User.mobile == user.mobile).first()
#     if existing_mobile:
#         raise HTTPException(400, "Mobile number already registered")
    
#     # 7. Create new user
#     new_user = models.User(
#         name=user.name.strip(),
#         email=user.email.lower().strip(),
#         mobile=mobile_validation["e164_format"],  # Store in E.164 format
#         hashed_password=auth_utils.hash_password(user.password)
#     )
    
#     db.add(new_user)
#     try:
#         db.commit()
#     except IntegrityError:
#         db.rollback()
#         raise HTTPException(400, "Registration failed. Please try again.")
    
#     return {
#         "message": "Signup successful! Please login.",
#         "user_info": {
#             "name": new_user.name,
#             "email": new_user.email,
#             "mobile": new_user.mobile
#         }
#     }

# @app.post("/login")
# def login(req: LoginReq, db: Session = Depends(get_db)):
#     if not req.identifier or not req.password:
#         raise HTTPException(400, "All fields are required")
#     user = db.query(models.User).filter(
#         or_(
#             func.lower(models.User.email) == req.identifier.lower(),
#             models.User.mobile == req.identifier
#         )
#     ).first()
#     if not user or not auth_utils.verify_password(req.password, user.hashed_password):
#         raise HTTPException(401, "Invalid credentials")
#     return {
#         "message": "Login successful",
#         "token": auth_utils.create_access_token({"sub": user.email, "id": user.id}),
#         "user": {
#             "name": user.name,
#             "email": user.email,
#             "mobile": user.mobile
#         }
#     }

# # ---------- AI Endpoints (Protected) ----------
# @app.post("/explain")
# def explain(data: MessageRequest, current_user=Depends(auth_utils.get_current_user), db: Session = Depends(get_db)):
#     prompt = (
#         f"Explain '{data.message}' with exactly these 4 sections.\n"
#         "Format rules:\n"
#         "- Use **Section Name:** as section header\n"
#         "- For 'Explanation' and 'Real-use cases' sections: write each point on a new line starting with '1. ', '2. ', '3. ' etc.\n"
#         "- For 'Definition' and 'Summary': write as a short paragraph\n"
#         "- Put double newline between sections\n\n"
#         "Sections: **Definition:** **Explanation:** **Real-use cases:** **Summary:**"
#     )
#     response = call_ai(prompt)
#     keywords = rake_extractor.extract(data.message, top_n=5)
#     category_info = topic_classifier.predict(data.message)
#     history = models.History(
#         user_id=current_user.id,
#         topic=data.message,
#         type="explain",
#         keywords=",".join(keywords),
#         category=category_info["category"],
#         confidence=category_info["confidence"]
#     )
#     db.add(history)
#     db.commit()
#     return {"response": response}

# @app.post("/generate-quiz")
# def quiz(data: MessageRequest, current_user=Depends(auth_utils.get_current_user), db: Session = Depends(get_db)):
#     prompt = (
#         f"Create exactly 5 multiple choice questions on the topic: '{data.message}'.\n"
#         "Return ONLY a valid JSON array, no extra text, no markdown.\n"
#         "Format: [{\"question\": \"...\", \"options\": [\"A. ...\", \"B. ...\", \"C. ...\", \"D. ...\"], \"correct_answer\": \"A. ...\"}]\n"
#         "The correct_answer must exactly match one of the options strings."
#     )
#     raw = call_ai(prompt)
#     parsed = parse_json(raw)
#     if not isinstance(parsed, list):
#         parsed = [{
#             "question": "What is " + data.message + "?",
#             "options": ["A. Option1", "B. Option2", "C. Option3", "D. Option4"],
#             "correct_answer": "A. Option1"
#         }]
#     keywords = rake_extractor.extract(data.message, top_n=5)
#     category_info = topic_classifier.predict(data.message)
#     history = models.History(
#         user_id=current_user.id,
#         topic=data.message,
#         type="quiz",
#         keywords=",".join(keywords),
#         category=category_info["category"],
#         confidence=category_info["confidence"]
#     )
#     db.add(history)
#     db.commit()
#     return {"quiz": parsed}

# @app.post("/generate-flashcards")
# def flash(data: MessageRequest, current_user=Depends(auth_utils.get_current_user), db: Session = Depends(get_db)):
#     prompt = (
#         f"Create exactly 5 flashcards for: '{data.message}'.\n"
#         "Return ONLY a valid JSON array, no extra text, no markdown.\n"
#         "Format: [{\"question\": \"...\", \"answer\": \"...\"}]"
#     )
#     raw = call_ai(prompt)
#     parsed = parse_json(raw)
#     if not isinstance(parsed, list):
#         parsed = [{"question": "What is " + data.message + "?", "answer": "It is a concept."}]
#     keywords = rake_extractor.extract(data.message, top_n=5)
#     category_info = topic_classifier.predict(data.message)
#     history = models.History(
#         user_id=current_user.id,
#         topic=data.message,
#         type="flashcards",
#         keywords=",".join(keywords),
#         category=category_info["category"],
#         confidence=category_info["confidence"]
#     )
#     db.add(history)
#     db.commit()
#     return {"flashcards": parsed}

# # ---------- Export Endpoints (TXT and PDF) ----------
# @app.post("/export-txt")
# def export_txt(data: dict, current_user=Depends(auth_utils.get_current_user)):
#     content = data.get("content", "")
#     topic = data.get("topic", "Notes")  # already camelCase from frontend
#     header = f"Study Notes : {topic}\n{'-' * 40}\n\n"
#     final_content = header + content
#     path = f"notes_{current_user.id}.txt"
#     with open(path, "w", encoding="utf-8") as f:
#         f.write(final_content)
#     return FileResponse(path, filename=f"{topic.replace(' ', '_')}_notes.txt")

# @app.post("/export-pdf")
# def export_pdf(data: dict, current_user=Depends(auth_utils.get_current_user)):
#     from reportlab.lib.units import inch
#     content = data.get("content", "")
#     topic = data.get("topic", "Notes")
#     path = f"notes_{current_user.id}.pdf"
#     doc = SimpleDocTemplate(path)
#     styles = getSampleStyleSheet()
#     story = []
#     title_style = styles['Title']
#     story.append(Paragraph(f"Study Notes : {topic}", title_style))
#     story.append(Spacer(1, 0.2*inch))
#     story.append(Paragraph("-" * 60, styles['Normal']))
#     story.append(Spacer(1, 0.2*inch))
#     for line in content.split("\n"):
#         if line.strip():
#             line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)
#             story.append(Paragraph(line, styles['Normal']))
#             story.append(Spacer(1, 0.1*inch))
#     doc.build(story)
#     return FileResponse(path, filename=f"{topic.replace(' ', '_')}_notes.pdf")

# # ---------- History Endpoint (with keywords & category) ----------
# @app.get("/history")
# def get_history(current_user=Depends(auth_utils.get_current_user), db: Session = Depends(get_db)):
#     history = db.query(models.History).filter(models.History.user_id == current_user.id).order_by(models.History.created_at.desc()).limit(20).all()
#     return [{
#         "id": h.id,
#         "topic": h.topic,
#         "type": h.type,
#         "created_at": h.created_at.isoformat(),
#         "keywords": h.keywords.split(",") if h.keywords else [],
#         "category": h.category,
#         "confidence": h.confidence
#     } for h in history]

# # ---------- Delete History ----------
# @app.delete("/history/{history_id}")
# def delete_history(history_id: int, current_user=Depends(auth_utils.get_current_user), db: Session = Depends(get_db)):
#     history_entry = db.query(models.History).filter(models.History.id == history_id, models.History.user_id == current_user.id).first()
#     if not history_entry:
#         raise HTTPException(404, "History entry not found")
#     db.delete(history_entry)
#     db.commit()
#     return {"message": "Deleted successfully"}

# @app.delete("/history/clear/all")
# def clear_all_history(current_user=Depends(auth_utils.get_current_user), db: Session = Depends(get_db)):
#     db.query(models.History).filter(models.History.user_id == current_user.id).delete()
#     db.commit()
#     return {"message": "All history cleared"}

# # ---------- Additional ML Endpoints (optional) ----------
# @app.post("/extract-keywords")
# def extract_keywords(data: MessageRequest, current_user=Depends(auth_utils.get_current_user)):
#     keywords = rake_extractor.extract(data.message, top_n=5)
#     return {"keywords": keywords}

# @app.post("/classify-topic")
# def classify_topic(data: MessageRequest, current_user=Depends(auth_utils.get_current_user)):
#     result = topic_classifier.predict(data.message)
#     return result

# # ---------- ✅ PING ENDPOINT (For Render Keep Alive) ----------
# @app.get("/ping")
# def ping():
#     return {
#         "status": "alive",
#         "timestamp": time.time(),
#         "message": "Server is running!"
#     }
