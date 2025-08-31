from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel

from app.database import get_db
from app.models.database_models import Interview, Candidate, InterviewResponse, InterviewNote
from app.models.pydantic_models import InterviewCreate, InterviewResponse as InterviewResponseModel, InterviewStatus, InterviewNoteCreate, InterviewNoteResponse
from app.services.ai_service import ai_service
from app.services.langchain_service import langchain_service
from app.routers.websocket_manager import manager
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class QAPair(BaseModel):
    question: str
    answer: str

class NextQuestionRequest(BaseModel):
    interview_id: str
    resume: Dict[str, Any]
    history: List[QAPair]
    position: str

class NextQuestionResponse(BaseModel):
    nextQuestion: str

class FollowUpRequest(BaseModel):
    interview_id: str
    original_question: str
    candidate_response: str

class FollowUpResponse(BaseModel):
    follow_up_question: str

class FeedbackRequest(BaseModel):
    interview_id: str
    question: str
    response: str
    expected_keywords: List[str] = []

class FeedbackResponse(BaseModel):
    score: int
    feedback: str
    strengths: List[str]
    improvements: List[str]
    suggested_follow_up: str
    confidence_level: str

class ConversationSummaryResponse(BaseModel):
    summary: str

class CodingQuestionRequest(BaseModel):
    interview_id: str
    resume: Dict[str, Any]
    position: str
    difficulty_level: str = "medium"

class CodingQuestionResponse(BaseModel):
    question: str
    examples: List[Dict[str, str]]
    constraints: List[str]
    hints: List[str]
    expected_approach: str
    time_limit: str

class CodingEvaluationRequest(BaseModel):
    interview_id: str
    question: str
    solution: str
    expected_approach: str
    position: str

class CodingEvaluationResponse(BaseModel):
    score: int
    correctness: str
    efficiency: str
    code_quality: str
    feedback: str
    strengths: List[str]
    improvements: List[str]
    suggested_optimizations: List[str]

class MonitorPermissionRequest(BaseModel):
    user_id: str

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

@router.post("/next-question", response_model=NextQuestionResponse)
async def next_question(payload: NextQuestionRequest):
    resume = payload.resume
    history = payload.history
    interview_id = payload.interview_id
    position = payload.position

    # Get asked questions from history
    asked_questions = [h.question for h in history]
    
    # Add conversation history to LangChain memory
    for qa_pair in history:
        langchain_service.add_to_conversation(
            interview_id=interview_id,
            question=qa_pair.question,
            response=qa_pair.answer
        )
    
    # Generate next question using LangChain
    next_question = await langchain_service.generate_next_question(
        interview_id=interview_id,
        resume_info=resume,
        position=position,
        asked_questions=asked_questions
    )
    
    return {"nextQuestion": next_question}

@router.post("/follow-up", response_model=FollowUpResponse)
async def generate_follow_up_question(payload: FollowUpRequest):
    """Generate a follow-up question based on candidate's response"""
    follow_up = await langchain_service.generate_follow_up_question(
        interview_id=payload.interview_id,
        original_question=payload.original_question,
        candidate_response=payload.candidate_response
    )
    
    return {"follow_up_question": follow_up}

@router.post("/feedback", response_model=FeedbackResponse)
async def provide_feedback(payload: FeedbackRequest):
    """Provide real-time feedback on candidate's response"""
    feedback = await langchain_service.provide_real_time_feedback(
        interview_id=payload.interview_id,
        question=payload.question,
        response=payload.response,
        expected_keywords=payload.expected_keywords
    )
    
    return FeedbackResponse(**feedback)

@router.get("/{interview_id}/conversation-summary", response_model=ConversationSummaryResponse)
async def get_conversation_summary(interview_id: str):
    """Get a summary of the conversation so far"""
    summary = langchain_service.get_conversation_summary(interview_id)
    return {"summary": summary}

@router.delete("/{interview_id}/conversation-memory")
async def clear_conversation_memory(interview_id: str):
    """Clear conversation memory for an interview"""
    langchain_service.clear_conversation_memory(interview_id)
    return {"message": "Conversation memory cleared successfully"}

@router.post("/coding-question", response_model=CodingQuestionResponse)
async def generate_coding_question(payload: CodingQuestionRequest):
    """Generate a coding question based on candidate's background"""
    coding_question = await langchain_service.generate_coding_question(
        interview_id=payload.interview_id,
        resume_info=payload.resume,
        position=payload.position,
        difficulty_level=payload.difficulty_level
    )
    
    return CodingQuestionResponse(**coding_question)

@router.post("/coding-evaluation", response_model=CodingEvaluationResponse)
async def evaluate_coding_solution(payload: CodingEvaluationRequest):
    """Evaluate a coding solution"""
    evaluation = await langchain_service.evaluate_coding_solution(
        interview_id=payload.interview_id,
        question=payload.question,
        solution=payload.solution,
        expected_approach=payload.expected_approach,
        position=payload.position
    )
    
    return CodingEvaluationResponse(**evaluation)

@router.post("/{interview_id}/monitor/start")
async def start_monitoring(interview_id: str, request: Request, db: Session = Depends(get_db)):
    user_role = request.headers.get("X-User-Role", "candidate")
    user_id = request.headers.get("X-User-Id", "unknown")
    if user_role not in ["interviewer", "admin"]:
        logger.warning(f"Unauthorized monitoring start attempt by {user_id} ({user_role}) for interview {interview_id}")
        raise HTTPException(status_code=403, detail="Unauthorized to start monitoring")
    # Set monitoring active in WebSocket manager
    session = manager.interview_sessions.get(interview_id)
    if session:
        session["monitoring_active"] = True
        if user_id not in session["monitors"]:
            session["monitors"].append(user_id)
    logger.info(f"Monitoring started for interview {interview_id} by {user_id} ({user_role})")
    return {"message": f"Monitoring started for interview {interview_id}"}

@router.post("/{interview_id}/monitor/stop")
async def stop_monitoring(interview_id: str, request: Request, db: Session = Depends(get_db)):
    user_role = request.headers.get("X-User-Role", "candidate")
    user_id = request.headers.get("X-User-Id", "unknown")
    if user_role not in ["interviewer", "admin"]:
        logger.warning(f"Unauthorized monitoring stop attempt by {user_id} ({user_role}) for interview {interview_id}")
        raise HTTPException(status_code=403, detail="Unauthorized to stop monitoring")
    session = manager.interview_sessions.get(interview_id)
    if session:
        session["monitoring_active"] = False
        if user_id in session["monitors"]:
            session["monitors"].remove(user_id)
    logger.info(f"Monitoring stopped for interview {interview_id} by {user_id} ({user_role})")
    return {"message": f"Monitoring stopped for interview {interview_id}"}

@router.get("/{interview_id}/monitors")
async def list_monitors(interview_id: str):
    session = manager.interview_sessions.get(interview_id)
    monitors = session["monitors"] if session else []
    return {"monitors": monitors}

@router.post("/{interview_id}/monitor/grant")
async def grant_monitor_permission(interview_id: str, payload: MonitorPermissionRequest, request: Request):
    user_role = request.headers.get("X-User-Role", "candidate")
    user_id = request.headers.get("X-User-Id", "unknown")
    if user_role != "admin":
        logger.warning(f"Unauthorized grant attempt by {user_id} ({user_role}) for interview {interview_id}")
        raise HTTPException(status_code=403, detail="Only admin can grant monitor permissions")
    session = manager.interview_sessions.get(interview_id)
    if session and payload.user_id not in session["monitors"]:
        session["monitors"].append(payload.user_id)
    logger.info(f"Granted monitor permission to {payload.user_id} for interview {interview_id} by {user_id} ({user_role})")
    return {"message": f"Granted monitor permission to {payload.user_id} for interview {interview_id}"}

@router.post("/{interview_id}/monitor/revoke")
async def revoke_monitor_permission(interview_id: str, payload: MonitorPermissionRequest, request: Request):
    user_role = request.headers.get("X-User-Role", "candidate")
    user_id = request.headers.get("X-User-Id", "unknown")
    if user_role != "admin":
        logger.warning(f"Unauthorized revoke attempt by {user_id} ({user_role}) for interview {interview_id}")
        raise HTTPException(status_code=403, detail="Only admin can revoke monitor permissions")
    session = manager.interview_sessions.get(interview_id)
    if session and payload.user_id in session["monitors"]:
        session["monitors"].remove(payload.user_id)
    logger.info(f"Revoked monitor permission from {payload.user_id} for interview {interview_id} by {user_id} ({user_role})")
    return {"message": f"Revoked monitor permission from {payload.user_id} for interview {interview_id}"}

@router.post("/{interview_id}/notes", response_model=InterviewNoteResponse)
async def add_interview_note(interview_id: str, payload: InterviewNoteCreate, db: Session = Depends(get_db), current_user_role: str = "admin"):
    # Only allow admin/interviewer (mocked for now)
    if current_user_role not in ["admin", "interviewer"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    note = InterviewNote(
        interview_id=interview_id,
        user_id=payload.user_id,
        content=payload.content,
        type=payload.type
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note

@router.get("/{interview_id}/notes", response_model=List[InterviewNoteResponse])
async def get_interview_notes(interview_id: str, db: Session = Depends(get_db), current_user_role: str = "admin"):
    # Only allow admin/interviewer (mocked for now)
    if current_user_role not in ["admin", "interviewer"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    notes = db.query(InterviewNote).filter(InterviewNote.interview_id == interview_id).order_by(InterviewNote.created_at).all()
    return notes

@router.get("/ongoing", response_model=List[Dict[str, Any]])
async def list_ongoing_interviews(db: Session = Depends(get_db), current_user_role: str = "admin"):
    # Only allow admin/interviewer (mocked for now)
    if current_user_role not in ["admin", "interviewer"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    soon = now + timedelta(minutes=30)
    interviews = db.query(Interview).filter(
        (Interview.status == "in_progress") |
        ((Interview.status == "scheduled") & (Interview.scheduled_at != None) & (Interview.scheduled_at <= soon))
    ).all()
    result = []
    for i in interviews:
        result.append({
            "interview_id": i.id,
            "candidate_name": i.candidate.name if i.candidate else None,
            "interviewer_name": i.recruiter.full_name if i.recruiter else None,
            "start_time": i.scheduled_at,
            "status": i.status,
            "position": i.position
        })
    return result

    # --- REAL LLM LOGIC (uncomment to use OpenAI) ---
    """
    import openai
    import os
    openai.api_key = os.getenv("OPENAI_API_KEY")
    prompt = f"You are an AI interview agent. Here is the candidate's resume:\n{resume}\n\nHere is the conversation so far:\n"
    for turn in history:
        prompt += f"Q: {turn.question}\nA: {turn.answer}\n"
    prompt += "\nBased on the above, ask the next most relevant, non-repetitive interview question. Only output the question."

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100,
        temperature=0.7,
    )
    next_question = response.choices[0].message.content.strip()
    return {"nextQuestion": next_question}
    """

@router.get("/{interview_id}/live", response_model=Dict[str, Any])
async def get_live_interview_data(interview_id: str, db: Session = Depends(get_db), current_user_role: str = "admin"):
    # Only allow admin/interviewer (mocked for now)
    if current_user_role not in ["admin", "interviewer"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    from datetime import datetime
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    # Get all responses for this interview
    responses = db.query(InterviewResponse).filter(InterviewResponse.interview_id == interview_id).order_by(InterviewResponse.question_asked_at).all()
    # Determine current question (next unanswered or last in list)
    questions = interview.questions or []
    answered_qids = [r.question_id for r in responses]
    current_question = None
    for q in questions:
        if q not in answered_qids:
            current_question = q
            break
    if not current_question and questions:
        current_question = questions[-1]
    # Time elapsed
    started = interview.started_at or interview.scheduled_at
    time_elapsed = (datetime.utcnow() - started).total_seconds() // 60 if started else None
    return {
        "interview_id": interview.id,
        "candidate_name": interview.candidate.name if interview.candidate else None,
        "interviewer_name": interview.recruiter.full_name if interview.recruiter else None,
        "status": interview.status,
        "current_question": current_question,
        "answers": [
            {
                "question_id": r.question_id,
                "question_text": r.question_text,
                "response_text": r.response_text,
                "score": r.score,
                "answered_at": r.response_ended_at
            } for r in responses
        ],
        "time_elapsed_minutes": time_elapsed
    }

@router.get("/{interview_id}/analytics", response_model=Dict[str, Any])
async def get_interview_analytics(interview_id: str, db: Session = Depends(get_db), current_user_role: str = "admin"):
    # Only allow admin/interviewer (mocked for now)
    if current_user_role not in ["admin", "interviewer"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    responses = db.query(InterviewResponse).filter(InterviewResponse.interview_id == interview_id).all()
    if not responses:
        raise HTTPException(status_code=404, detail="No responses found for this interview")
    # Response times per question
    response_times = [r.response_duration_seconds for r in responses if r.response_duration_seconds is not None]
    avg_response_time = sum(response_times) / len(response_times) if response_times else None
    # Scores per question
    scores = [{
        "question_id": r.question_id,
        "score": r.score
    } for r in responses if r.score is not None]
    overall_score = sum(r.score for r in responses if r.score is not None) / len([r for r in responses if r.score is not None]) if any(r.score is not None for r in responses) else None
    # Engagement metrics
    num_responses = len(responses)
    avg_response_length = sum(len(r.response_text or "") for r in responses) / num_responses if num_responses else 0
    return {
        "interview_id": interview_id,
        "num_responses": num_responses,
        "avg_response_time_seconds": avg_response_time,
        "scores": scores,
        "overall_score": overall_score,
        "avg_response_length": avg_response_length
    }
