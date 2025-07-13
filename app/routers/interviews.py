from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel

from app.database import get_db
from app.models.database_models import Interview, Candidate, InterviewResponse
from app.models.pydantic_models import InterviewCreate, InterviewResponse as InterviewResponseModel, InterviewStatus
from app.services.ai_service import ai_service
from app.services.langchain_service import langchain_service

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
