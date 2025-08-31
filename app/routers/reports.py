from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.database import get_db
from app.models.database_models import Interview

router = APIRouter()

@router.get("/{interview_id}")
async def get_interview_report(interview_id: str, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    if not interview.candidate:
        raise HTTPException(status_code=404, detail="Candidate not found for this interview")
    # Check for at least one score or analysis field
    if all(
        x is None for x in [
            interview.technical_score,
            interview.communication_score,
            interview.problem_solving_score,
            interview.cultural_fit_score,
            interview.overall_score,
            interview.malpractice_score,
            interview.ai_analysis,
            interview.recommendation
        ]
    ):
        raise HTTPException(status_code=404, detail="No report data available for this interview")
    report = {
        "interview_id": interview.id,
        "candidate": {
            "name": interview.candidate.name,
            "email": interview.candidate.email,
            "position": interview.position
        },
        "scores": {
            "technical": interview.technical_score or 0,
            "communication": interview.communication_score or 0,
            "problem_solving": interview.problem_solving_score or 0,
            "cultural_fit": interview.cultural_fit_score or 0,
            "overall": interview.overall_score or 0
        },
        "malpractice": {
            "score": interview.malpractice_score or 95,
            "flags": interview.malpractice_flags or [],
            "risk_level": "low"
        },
        "recommendation": interview.recommendation or "No recommendation available",
        "ai_analysis": interview.ai_analysis or {},
        "duration_minutes": interview.duration_minutes,
        "status": interview.status,
        "created_at": interview.created_at
    }
    return {"success": True, "data": report}
