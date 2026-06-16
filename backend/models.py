from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    mobile = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    user_id = Column(String, nullable=True)  # Custom display ID (e.g., "KumarS1234")

class History(Base):
    __tablename__ = "history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    topic = Column(String)
    type = Column(String)  # "explain", "quiz", "flashcards"
    keywords = Column(String, nullable=True)
    category = Column(String, nullable=True)
    confidence = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
