from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.database_models import Feedback
from app.models.pydantic_models import FeedbackCreate, FeedbackResponse
from typing import List

router = APIRouter()

@router.post("/", response_model=FeedbackResponse)
async def submit_feedback(payload: FeedbackCreate, db: Session = Depends(get_db)):
    db_feedback = Feedback(
        user_id=payload.user_id,
        interview_id=payload.interview_id,
        content=payload.content,
        rating=payload.rating
    )
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    return db_feedback

@router.get("/", response_model=List[FeedbackResponse])
async def list_feedback(db: Session = Depends(get_db)):
    # TODO: Add admin check
    feedback = db.query(Feedback).order_by(Feedback.created_at.desc()).all()
    return feedback 