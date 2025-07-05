from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    role = Column(String, default="recruiter")  # recruiter, admin, candidate
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    interviews = relationship("Interview", back_populates="recruiter")

class Candidate(Base):
    __tablename__ = "candidates"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True)
    phone = Column(String)
    location = Column(String)
    resume_path = Column(String)
    resume_analysis = Column(JSON)  # Structured resume data
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    interviews = relationship("Interview", back_populates="candidate")

class Interview(Base):
    __tablename__ = "interviews"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    recruiter_id = Column(String, ForeignKey("users.id"), nullable=False)
    position = Column(String, nullable=False)
    status = Column(String, default="scheduled")  # scheduled, in_progress, completed, cancelled
    scheduled_at = Column(DateTime(timezone=True))
    started_at = Column(DateTime(timezone=True))
    ended_at = Column(DateTime(timezone=True))
    duration_minutes = Column(Integer)
    
    # Interview Configuration
    questions = Column(JSON)  # List of questions
    interview_type = Column(String, default="technical")  # technical, behavioral, mixed
    
    # Media Files
    video_path = Column(String)
    audio_path = Column(String)
    transcript = Column(Text)
    
    # Scores and Analysis
    technical_score = Column(Float)
    communication_score = Column(Float)
    problem_solving_score = Column(Float)
    cultural_fit_score = Column(Float)
    overall_score = Column(Float)
    
    # Malpractice Detection
    malpractice_score = Column(Float)
    malpractice_flags = Column(JSON)
    
    # AI Analysis
    ai_analysis = Column(JSON)
    recommendation = Column(String)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    candidate = relationship("Candidate", back_populates="interviews")
    recruiter = relationship("User", back_populates="interviews")
    responses = relationship("InterviewResponse", back_populates="interview")

class InterviewResponse(Base):
    __tablename__ = "interview_responses"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    interview_id = Column(String, ForeignKey("interviews.id"), nullable=False)
    question_id = Column(String, nullable=False)
    question_text = Column(Text, nullable=False)
    response_text = Column(Text)
    response_audio_path = Column(String)
    
    # Scoring
    score = Column(Float)
    category = Column(String)  # technical, behavioral, communication
    difficulty = Column(String)  # easy, medium, hard
    
    # Timing
    question_asked_at = Column(DateTime(timezone=True))
    response_started_at = Column(DateTime(timezone=True))
    response_ended_at = Column(DateTime(timezone=True))
    response_duration_seconds = Column(Integer)
    
    # Analysis
    ai_feedback = Column(Text)
    keywords_detected = Column(JSON)
    sentiment_score = Column(Float)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    interview = relationship("Interview", back_populates="responses")

class Question(Base):
    __tablename__ = "questions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    text = Column(Text, nullable=False)
    category = Column(String, nullable=False)  # technical, behavioral, situational
    difficulty = Column(String, nullable=False)  # easy, medium, hard
    skills = Column(JSON)  # List of skills this question tests
    expected_keywords = Column(JSON)  # Keywords expected in good answers
    model_answer = Column(Text)
    scoring_rubric = Column(JSON)
    
    # Metadata
    created_by = Column(String, ForeignKey("users.id"))
    is_active = Column(Boolean, default=True)
    usage_count = Column(Integer, default=0)
    avg_score = Column(Float)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class InterviewSession(Base):
    __tablename__ = "interview_sessions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    interview_id = Column(String, ForeignKey("interviews.id"), nullable=False)
    session_token = Column(String, unique=True, nullable=False)
    
    # Real-time data
    current_question_index = Column(Integer, default=0)
    is_recording = Column(Boolean, default=False)
    connection_quality = Column(String)
    
    # Malpractice monitoring
    face_detection_active = Column(Boolean, default=True)
    voice_analysis_active = Column(Boolean, default=True)
    screen_monitoring_active = Column(Boolean, default=True)
    
    # Session metadata
    user_agent = Column(String)
    ip_address = Column(String)
    device_info = Column(JSON)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_activity = Column(DateTime(timezone=True), server_default=func.now())
