from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.database_models import User, Candidate, Interview
from app.models.pydantic_models import UserCreate, CandidateCreate, InterviewCreate
from app.core.config import settings
from typing import List
import os
import random
from datetime import datetime, timedelta

router = APIRouter()

# Only enable in dev/test environments
def is_test_env():
    return getattr(settings, "ENV", "development") in ["development", "testing", "test"] or os.environ.get("ENV") in ["development", "testing", "test"]

@router.post("/seed", tags=["test-data"])
async def seed_test_data(
    users: List[UserCreate] = None,
    candidates: List[CandidateCreate] = None,
    interviews: List[InterviewCreate] = None,
    db: Session = Depends(get_db)
):
    if not is_test_env():
        raise HTTPException(status_code=403, detail="Test data endpoints are disabled in production.")
    created = {"users": [], "candidates": [], "interviews": []}
    # Seed users
    if users:
        for user in users:
            db_user = User(
                email=user.email,
                hashed_password="test",  # Set a dummy password
                full_name=user.full_name,
                role=user.role
            )
            db.add(db_user)
            created["users"].append(user.email)
    # Seed candidates
    if candidates:
        for cand in candidates:
            db_cand = Candidate(
                name=cand.name,
                email=cand.email,
                phone=cand.phone,
                location=cand.location
            )
            db.add(db_cand)
            created["candidates"].append(cand.name)
    db.commit()
    # Seed interviews
    if interviews:
        for interview in interviews:
            db_cand = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()
            db_user = db.query(User).filter(User.id == getattr(interview, "recruiter_id", None)).first()
            if not db_cand or not db_user:
                continue
            db_interview = Interview(
                candidate_id=db_cand.id,
                recruiter_id=db_user.id,
                position=interview.position,
                interview_type=interview.interview_type,
                scheduled_at=interview.scheduled_at or datetime.utcnow() + timedelta(days=random.randint(1, 10)),
                status="scheduled"
            )
            db.add(db_interview)
            created["interviews"].append(db_interview.id)
        db.commit()
    return {"success": True, "created": created}

@router.post("/clear", tags=["test-data"])
async def clear_test_data(db: Session = Depends(get_db)):
    if not is_test_env():
        raise HTTPException(status_code=403, detail="Test data endpoints are disabled in production.")
    db.query(Interview).delete()
    db.query(Candidate).delete()
    db.query(User).delete()
    db.commit()
    return {"success": True, "message": "Test data cleared."} 