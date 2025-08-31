from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.database_models import Interview, Candidate
from typing import Dict
from sqlalchemy import func
from app.models.database_models import InterviewResponse, Question
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/interviews", response_model=Dict)
async def interview_analytics(db: Session = Depends(get_db)):
    total = db.query(Interview).count()
    active = db.query(Interview).filter(Interview.status == "IN_PROGRESS").count()
    completed = db.query(Interview).filter(Interview.status == "COMPLETED").count()
    scheduled = db.query(Interview).filter(Interview.status == "SCHEDULED").count()
    avg_duration = db.query(Interview).filter(Interview.duration_minutes != None).with_entities(
        func.avg(Interview.duration_minutes)).scalar() or 0
    avg_score = db.query(Interview).with_entities(
        func.avg(Interview.overall_score)).scalar() or 0
    return {
        "total": total,
        "active": active,
        "completed": completed,
        "scheduled": scheduled,
        "avg_duration": avg_duration,
        "avg_score": avg_score
    }

@router.get("/candidates", response_model=Dict)
async def candidate_analytics(db: Session = Depends(get_db)):
    total = db.query(Candidate).count()
    # Example: count by position (if available)
    by_position = db.query(Candidate.position, func.count(Candidate.id)).group_by(Candidate.position).all() if hasattr(Candidate, "position") else []
    return {
        "total": total,
        "by_position": dict(by_position) if by_position else {}
    }

from sqlalchemy import func

@router.get("/performance", response_model=Dict)
async def performance_analytics(db: Session = Depends(get_db)):
    avg_technical = db.query(func.avg(Interview.technical_score)).scalar() or 0
    avg_communication = db.query(func.avg(Interview.communication_score)).scalar() or 0
    avg_problem_solving = db.query(func.avg(Interview.problem_solving_score)).scalar() or 0
    avg_cultural_fit = db.query(func.avg(Interview.cultural_fit_score)).scalar() or 0
    return {
        "avg_technical": avg_technical,
        "avg_communication": avg_communication,
        "avg_problem_solving": avg_problem_solving,
        "avg_cultural_fit": avg_cultural_fit
    }

# Per-question analytics
@router.get("/questions", response_model=Dict)
async def per_question_analytics(db: Session = Depends(get_db)):
    # Average score per question
    avg_scores = db.query(
        InterviewResponse.question_id,
        func.avg(InterviewResponse.score).label("avg_score"),
        func.count(InterviewResponse.id).label("attempts")
    ).group_by(InterviewResponse.question_id).all()
    # Most/least correctly answered
    best = max(avg_scores, key=lambda x: x.avg_score, default=None)
    worst = min(avg_scores, key=lambda x: x.avg_score, default=None)
    # Average time per question
    avg_time = db.query(
        InterviewResponse.question_id,
        func.avg(InterviewResponse.response_duration_seconds).label("avg_time")
    ).group_by(InterviewResponse.question_id).all()
    return {
        "avg_scores": [{"question_id": qid, "avg_score": float(score), "attempts": int(attempts)} for qid, score, attempts in avg_scores],
        "best_question": best.question_id if best else None,
        "worst_question": worst.question_id if worst else None,
        "avg_time": [{"question_id": qid, "avg_time": float(t)} for qid, t in avg_time]
    }

# Per-candidate analytics
@router.get("/candidates/{candidate_id}/performance", response_model=Dict)
async def candidate_performance(candidate_id: str, db: Session = Depends(get_db)):
    # Candidate's interviews and scores
    interviews = db.query(Interview).filter(Interview.candidate_id == candidate_id).all()
    scores = [i.overall_score for i in interviews if i.overall_score is not None]
    trend = [
        {"date": i.created_at, "score": i.overall_score}
        for i in sorted(interviews, key=lambda x: x.created_at)
        if i.overall_score is not None
    ]
    # Strengths/weaknesses by category
    responses = db.query(InterviewResponse).join(Interview).filter(Interview.candidate_id == candidate_id).all()
    by_category = {}
    for r in responses:
        if r.category not in by_category:
            by_category[r.category] = []
        if r.score is not None:
            by_category[r.category].append(r.score)
    strengths = sorted(((cat, sum(scores)/len(scores)) for cat, scores in by_category.items() if scores), key=lambda x: -x[1])
    weaknesses = sorted(((cat, sum(scores)/len(scores)) for cat, scores in by_category.items() if scores), key=lambda x: x[1])
    return {
        "scores": scores,
        "trend": trend,
        "strengths": strengths,
        "weaknesses": weaknesses
    }

# Time-based trends
@router.get("/trends", response_model=Dict)
async def time_based_trends(
    days: int = 30,
    position: str = None,
    db: Session = Depends(get_db)
):
    since = datetime.utcnow() - timedelta(days=days)
    query = db.query(Interview).filter(Interview.created_at >= since)
    if position:
        query = query.filter(Interview.position == position)
    interviews = query.all()
    by_day = {}
    for i in interviews:
        day = i.created_at.date().isoformat()
        if day not in by_day:
            by_day[day] = {"count": 0, "avg_score": 0, "scores": []}
        by_day[day]["count"] += 1
        if i.overall_score is not None:
            by_day[day]["scores"].append(i.overall_score)
    for day in by_day:
        scores = by_day[day]["scores"]
        by_day[day]["avg_score"] = sum(scores)/len(scores) if scores else 0
        del by_day[day]["scores"]
    return {"by_day": by_day} 