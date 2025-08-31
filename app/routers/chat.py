from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.database_models import ChatMessage, Interview, User
from app.models.pydantic_models import ChatMessageCreate, ChatMessageResponse
from typing import List
from jose import jwt, JWTError
from app.core.config import settings
import json
from datetime import datetime

# In-memory connection manager for chat
class ChatConnectionManager:
    def __init__(self):
        self.active_connections = {}  # interview_id -> list of websockets
        self.user_sessions = {}  # websocket -> {user_id, role, interview_id}

    async def connect(self, websocket: WebSocket, interview_id: str, token: str):
        # JWT authentication
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id = payload.get("sub")
            role = payload.get("role", "candidate")
        except JWTError:
            await websocket.close(code=4001)
            return None, None
        await websocket.accept()
        if interview_id not in self.active_connections:
            self.active_connections[interview_id] = []
        self.active_connections[interview_id].append(websocket)
        self.user_sessions[websocket] = {"user_id": user_id, "role": role, "interview_id": interview_id}
        return user_id, role

    def disconnect(self, websocket: WebSocket):
        session = self.user_sessions.get(websocket)
        if session:
            interview_id = session["interview_id"]
            if interview_id in self.active_connections and websocket in self.active_connections[interview_id]:
                self.active_connections[interview_id].remove(websocket)
            del self.user_sessions[websocket]

    async def broadcast(self, interview_id: str, message: dict):
        if interview_id in self.active_connections:
            for ws in self.active_connections[interview_id]:
                try:
                    await ws.send_text(json.dumps(message))
                except:
                    pass

chat_manager = ChatConnectionManager()

router = APIRouter()

@router.get("/history/{interview_id}", response_model=List[ChatMessageResponse])
async def get_chat_history(interview_id: str, db: Session = Depends(get_db)):
    messages = db.query(ChatMessage).filter(ChatMessage.interview_id == interview_id).order_by(ChatMessage.created_at).all()
    return messages

@router.post("/send", response_model=ChatMessageResponse)
async def send_chat_message(payload: ChatMessageCreate, db: Session = Depends(get_db)):
    # Optionally: validate sender/interview
    db_msg = ChatMessage(
        interview_id=payload.interview_id,
        sender_id=payload.sender_id,
        sender_role=payload.sender_role,
        content=payload.content,
        message_type=payload.message_type
    )
    db.add(db_msg)
    db.commit()
    db.refresh(db_msg)
    return db_msg 

@router.websocket("/ws/{interview_id}")
async def chat_websocket(websocket: WebSocket, interview_id: str, token: str = Query(...), db: Session = Depends(get_db)):
    user_id, role = await chat_manager.connect(websocket, interview_id, token)
    if not user_id:
        return
    try:
        # Notify others of join
        join_msg = {"type": "join", "user_id": user_id, "role": role, "timestamp": datetime.utcnow().isoformat()}
        await chat_manager.broadcast(interview_id, join_msg)
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            msg_type = msg.get("type", "text")
            content = msg.get("content", "")
            # Handle typing indicator
            if msg_type == "typing":
                await chat_manager.broadcast(interview_id, {"type": "typing", "user_id": user_id, "timestamp": datetime.utcnow().isoformat()})
                continue
            # Store and broadcast chat message
            if msg_type == "text":
                db_msg = ChatMessage(
                    interview_id=interview_id,
                    sender_id=user_id,
                    sender_role=role,
                    content=content,
                    message_type="text"
                )
                db.add(db_msg)
                db.commit()
                db.refresh(db_msg)
                chat_msg = {
                    "type": "text",
                    "user_id": user_id,
                    "role": role,
                    "content": content,
                    "timestamp": db_msg.created_at.isoformat()
                }
                await chat_manager.broadcast(interview_id, chat_msg)
    except WebSocketDisconnect:
        chat_manager.disconnect(websocket)
        leave_msg = {"type": "leave", "user_id": user_id, "role": role, "timestamp": datetime.utcnow().isoformat()}
        await chat_manager.broadcast(interview_id, leave_msg) 