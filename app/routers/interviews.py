from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models.database_models import Interview, Candidate, InterviewResponse
from app.models.pydantic_models import InterviewCreate, InterviewResponse as InterviewResponseModel, InterviewStatus
from app.services.ai_service import ai_service

router = APIRouter()

@router.post("/", response_model=InterviewResponseModel)
async def create_interview(
    interview: InterviewCreate,
    current_user_id: str = "demo_user",  # Mock user ID
    db: Session = Depends(get_db)
):
    candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    db_interview = Interview(
        candidate_id=interview.candidate_id,
        recruiter_id=1,
        position=interview.position,
        interview_type=interview.interview_type,
        scheduled_at=interview.scheduled_at,
        status=InterviewStatus.SCHEDULED
    )
    
    if candidate.resume_analysis:
        skills = []
        for skill_group in candidate.resume_analysis.get("skills", []):
            skills.extend(skill_group.get("items", []))
        
        questions = await ai_service.generate_questions(
            candidate_skills=skills,
            position=interview.position,
            count=8
        )
        db_interview.questions = questions
    
    db.add(db_interview)
    db.commit()
    db.refresh(db_interview)
    
    return db_interview

@router.get("/", response_model=List[InterviewResponseModel])
async def get_interviews(
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[InterviewStatus] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Interview)
    
    if status_filter:
        query = query.filter(Interview.status == status_filter)
    
    interviews = query.offset(skip).limit(limit).all()
    return interviews

@router.get("/{interview_id}", response_model=InterviewResponseModel)
async def get_interview(interview_id: str, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    return interview

@router.post("/{interview_id}/start")
async def start_interview(interview_id: str, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    if interview.status != InterviewStatus.SCHEDULED:
        raise HTTPException(status_code=400, detail="Interview cannot be started")
    
    interview.status = InterviewStatus.IN_PROGRESS
    interview.started_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "message": "Interview started successfully",
        "questions": interview.questions
    }

@router.post("/{interview_id}/end")
async def end_interview(interview_id: str, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    if interview.status != InterviewStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Interview is not in progress")
    
    interview.status = InterviewStatus.COMPLETED
    interview.ended_at = datetime.utcnow()
    
    if interview.started_at:
        duration = interview.ended_at - interview.started_at
        interview.duration_minutes = int(duration.total_seconds() / 60)
    
    db.commit()
    
    return {"message": "Interview ended successfully"}
