from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
import os
import uuid
from pathlib import Path

from app.database import get_db
from app.models.database_models import Candidate
from app.models.pydantic_models import CandidateResponse, ResumeAnalysis
from app.services.ai_service import ai_service
from app.services.file_service import file_service
from app.core.config import settings

router = APIRouter()

@router.post("/upload", response_model=dict)
async def upload_resume(
    file: UploadFile = File(...),
    candidate_id: str = None,
    db: Session = Depends(get_db)
):
    try:
        if not file.filename.lower().endswith(tuple(settings.ALLOWED_FILE_TYPES)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not allowed. Supported types: {settings.ALLOWED_FILE_TYPES}"
            )
        
        if file.size > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size too large. Maximum size: {settings.MAX_FILE_SIZE} bytes"
            )
        
        file_id = str(uuid.uuid4())
        file_extension = Path(file.filename).suffix
        file_path = os.path.join(settings.UPLOAD_DIR, f"{file_id}{file_extension}")
        
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        resume_text = await file_service.extract_text_from_file(file_path)
        analysis = await ai_service.analyze_resume(resume_text)
        
        if candidate_id:
            candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
            if not candidate:
                raise HTTPException(status_code=404, detail="Candidate not found")
        else:
            candidate = Candidate(
                name=analysis.personal_info.get("name", "Unknown"),
                email=analysis.personal_info.get("email"),
                phone=analysis.personal_info.get("phone"),
                location=analysis.personal_info.get("location")
            )
            db.add(candidate)
        
        candidate.resume_path = file_path
        candidate.resume_analysis = analysis.dict()
        
        db.commit()
        db.refresh(candidate)
        
        return {
            "message": "Resume uploaded and analyzed successfully",
            "candidate_id": candidate.id,
            "analysis": analysis.dict()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing resume: {str(e)}"
        )

@router.get("/analysis/{candidate_id}", response_model=ResumeAnalysis)
async def get_resume_analysis(candidate_id: str, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    if not candidate.resume_analysis:
        raise HTTPException(status_code=404, detail="Resume analysis not found")
    
    return ResumeAnalysis(**candidate.resume_analysis)
