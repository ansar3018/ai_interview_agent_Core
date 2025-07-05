from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class InterviewStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: str = "recruiter"

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class CandidateBase(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    location: Optional[str] = None

class CandidateCreate(CandidateBase):
    pass

class CandidateResponse(CandidateBase):
    id: str
    resume_analysis: Optional[Dict[str, Any]] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class SkillGroup(BaseModel):
    type: str
    proficiency: str

class Experience(BaseModel):
    company: str
    role: str
    duration: str
    responsibilities: List[str]

class Education(BaseModel):
    institution: str
    degree: str
    year: Optional[str] = None

class Project(BaseModel):
    name: str
    description: str
    technologies: List[str]

class ResumeAnalysis(BaseModel):
    personal_info: Dict[str, str]
    skills: List[SkillGroup]
    experience: List[Experience]
    education: List[Education]
    projects: List[Project]
    summary: str
    recommended_questions: List[Dict[str, str]]

class InterviewBase(BaseModel):
    candidate_id: str
    position: str
    interview_type: str = "technical"
    scheduled_at: Optional[datetime] = None

class InterviewCreate(InterviewBase):
    questions: Optional[List[str]] = []

class InterviewResponse(InterviewBase):
    id: str
    recruiter_id: str
    status: InterviewStatus
    duration_minutes: Optional[int] = None
    technical_score: Optional[float] = None
    communication_score: Optional[float] = None
    problem_solving_score: Optional[float] = None
    cultural_fit_score: Optional[float] = None
    overall_score: Optional[float] = None
    malpractice_score: Optional[float] = None
    recommendation: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True
