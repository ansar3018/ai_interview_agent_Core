from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging
import openai
from app.database import engine, Base
from app.routers import auth, candidates, interviews, resume_analysis, reports
from app.routers import analytics
from app.routers import test_data
from app.routers import chat
from app.routers import i18n
from app.routers import feedback
from app.routers import faq
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.services.websocket_manager import manager
import os

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting AI Interview Agent Backend")
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown
    logger.info("Shutting down AI Interview Agent Backend")

app = FastAPI(
    title="AI Interview Agent API",
    description="Intelligent Virtual Interview Platform Backend",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(candidates.router, prefix="/api/v1/candidates", tags=["Candidates"])
app.include_router(interviews.router, prefix="/api/v1/interviews", tags=["Interviews"])
app.include_router(resume_analysis.router, prefix="/api/v1/resume", tags=["Resume Analysis"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(i18n.router, prefix="/api/v1/i18n", tags=["i18n"])
app.include_router(feedback.router, prefix="/api/v1/feedback", tags=["Feedback"])
app.include_router(faq.router, prefix="/api/v1/faq", tags=["FAQ"])

if getattr(settings, "ENV", "development") in ["development", "testing", "test"] or os.environ.get("ENV") in ["development", "testing", "test"]:
    app.include_router(test_data.router, prefix="/api/v1/test-data", tags=["Test Data"])

@app.get("/")
async def root():
    return {
        "message": "AI Interview Agent API",
        "version": "1.0.0",
        "status": "active",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "database": "connected",
        "ai_services": "active"
    }

# WebSocket endpoint for real-time interview
@app.websocket("/ws/interview/{interview_id}")
async def websocket_interview_endpoint(websocket: WebSocket, interview_id: str):
    await manager.connect(websocket, interview_id)
    try:
        while True:
            data = await websocket.receive_json()
            await manager.handle_message(interview_id, data)
    except WebSocketDisconnect:
        manager.disconnect(interview_id)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
