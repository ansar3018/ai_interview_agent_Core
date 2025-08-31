from fastapi import WebSocket, WebSocketDisconnect, Query
from typing import Dict, List
import json
import logging
from datetime import datetime

from app.services.audio_service import audio_service
from app.services.video_service import video_service
from app.services.malpractice_service import malpractice_service
from app.core.config import settings
from jose import jwt, JWTError

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.interview_sessions: Dict[str, Dict] = {}
        self.user_sessions: Dict[str, dict] = {}  # user_id -> {role, interview_id, websocket}
    
    async def connect(self, websocket: WebSocket, interview_id: str, token: str = Query(...)):
        # JWT authentication
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id = payload.get("sub")
            role = payload.get("role", "candidate")
        except JWTError:
            await websocket.close(code=4001)
            return
        await websocket.accept()
        # Store user session
        self.user_sessions[user_id] = {"role": role, "interview_id": interview_id, "websocket": websocket}
        
        if interview_id not in self.active_connections:
            self.active_connections[interview_id] = []
            self.interview_sessions[interview_id] = {
                "current_question": 0,
                "is_recording": False,
                "participants": 0,
                "start_time": datetime.now().isoformat(),
                "monitors": []  # List of user_ids monitoring
            }
        
        self.active_connections[interview_id].append(websocket)
        self.interview_sessions[interview_id]["participants"] += 1
        
        # Add to monitors if interviewer/admin
        if role in ["interviewer", "admin"]:
            self.interview_sessions[interview_id]["monitors"].append(user_id)
        
        # Send current session state
        await self.send_to_interview(interview_id, {
            "type": "session_state",
            "data": self.interview_sessions[interview_id]
        })
        
        logger.info(f"User {user_id} ({role}) connected to interview {interview_id}")
    
    def disconnect(self, interview_id: str, websocket: WebSocket = None):
        # Remove from user_sessions
        for user_id, session in list(self.user_sessions.items()):
            if session["websocket"] == websocket:
                del self.user_sessions[user_id]
                # Remove from monitors if present
                if user_id in self.interview_sessions.get(interview_id, {}).get("monitors", []):
                    self.interview_sessions[interview_id]["monitors"].remove(user_id)
        
        if interview_id in self.active_connections:
            if websocket and websocket in self.active_connections[interview_id]:
                self.active_connections[interview_id].remove(websocket)
                self.interview_sessions[interview_id]["participants"] -= 1
            
            if not self.active_connections[interview_id]:
                del self.active_connections[interview_id]
                if interview_id in self.interview_sessions:
                    del self.interview_sessions[interview_id]
        
        logger.info(f"Client disconnected from interview {interview_id}")
    
    async def send_to_interview(self, interview_id: str, message: dict):
        if interview_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[interview_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except:
                    disconnected.append(connection)
            
            # Remove disconnected connections
            for conn in disconnected:
                self.active_connections[interview_id].remove(conn)
    
    async def handle_message(self, interview_id: str, message: dict):
        """Handle incoming WebSocket messages"""
        try:
            message_type = message.get("type")
            data = message.get("data", {})
            # Identify user
            user_id = None
            role = None
            for uid, session in self.user_sessions.items():
                if session["websocket"] == message.get("_websocket", None):
                    user_id = uid
                    role = session["role"]
                    break
            # Monitoring events
            if message_type == "start_monitoring":
                if role not in ["interviewer", "admin"]:
                    await self.send_to_interview(interview_id, {"type": "error", "message": "Unauthorized to start monitoring"})
                    return
                self.interview_sessions[interview_id]["monitoring_active"] = True
                await self.send_to_interview(interview_id, {"type": "monitoring_started", "by": user_id, "timestamp": datetime.now().isoformat()})
            elif message_type == "stop_monitoring":
                if role not in ["interviewer", "admin"]:
                    await self.send_to_interview(interview_id, {"type": "error", "message": "Unauthorized to stop monitoring"})
                    return
                self.interview_sessions[interview_id]["monitoring_active"] = False
                await self.send_to_interview(interview_id, {"type": "monitoring_stopped", "by": user_id, "timestamp": datetime.now().isoformat()})
            elif message_type == "monitor_joined":
                if user_id and user_id not in self.interview_sessions[interview_id]["monitors"]:
                    self.interview_sessions[interview_id]["monitors"].append(user_id)
                await self.send_to_interview(interview_id, {"type": "monitor_joined", "user_id": user_id, "timestamp": datetime.now().isoformat()})
            elif message_type == "monitor_left":
                if user_id and user_id in self.interview_sessions[interview_id]["monitors"]:
                    self.interview_sessions[interview_id]["monitors"].remove(user_id)
                await self.send_to_interview(interview_id, {"type": "monitor_left", "user_id": user_id, "timestamp": datetime.now().isoformat()})
            # ... existing message types ...
            elif message_type == "audio_chunk":
                await self._handle_audio_chunk(interview_id, data)
            elif message_type == "video_frame":
                await self._handle_video_frame(interview_id, data)
            elif message_type == "start_recording":
                await self._handle_start_recording(interview_id)
            elif message_type == "stop_recording":
                await self._handle_stop_recording(interview_id)
            elif message_type == "next_question":
                await self._handle_next_question(interview_id, data)
            elif message_type == "transcript_update":
                await self._handle_transcript_update(interview_id, data)
            else:
                logger.warning(f"Unknown message type: {message_type}")
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            await self.send_to_interview(interview_id, {
                "type": "error",
                "message": "Error processing message"
            })
    
    async def _handle_audio_chunk(self, interview_id: str, data: dict):
        """Process audio chunk for real-time transcription"""
        try:
            audio_data = data.get("audio_data")
            if audio_data:
                # Convert base64 to bytes
                import base64
                audio_bytes = base64.b64decode(audio_data)
                
                # Transcribe audio chunk
                transcription = await audio_service.transcribe_audio_chunk(audio_bytes)
                
                # Send transcription back
                await self.send_to_interview(interview_id, {
                    "type": "transcription",
                    "data": {
                        "text": transcription.get("text", ""),
                        "confidence": transcription.get("confidence", 0),
                        "timestamp": datetime.now().isoformat()
                    }
                })
        
        except Exception as e:
            logger.error(f"Error processing audio chunk: {str(e)}")
    
    async def _handle_video_frame(self, interview_id: str, data: dict):
        """Process video frame for malpractice detection"""
        try:
            frame_data = data.get("frame_data")
            if frame_data:
                # Analyze video frame
                analysis = await video_service.process_video_frame(frame_data)
                
                # Check for real-time malpractice alerts
                malpractice_alert = await malpractice_service.real_time_monitoring(
                    analysis, {}  # Audio analysis would be passed here
                )
                
                # Send analysis back
                await self.send_to_interview(interview_id, {
                    "type": "video_analysis",
                    "data": {
                        "face_detected": analysis.get("face_detected", False),
                        "identity_match": analysis.get("identity_match", 1.0),
                        "gaze_direction": analysis.get("gaze_direction"),
                        "malpractice_alert": malpractice_alert,
                        "timestamp": datetime.now().isoformat()
                    }
                })
        
        except Exception as e:
            logger.error(f"Error processing video frame: {str(e)}")
    
    async def _handle_start_recording(self, interview_id: str):
        """Handle start recording command"""
        if interview_id in self.interview_sessions:
            self.interview_sessions[interview_id]["is_recording"] = True
            
            await self.send_to_interview(interview_id, {
                "type": "recording_started",
                "timestamp": datetime.now().isoformat()
            })
    
    async def _handle_stop_recording(self, interview_id: str):
        """Handle stop recording command"""
        if interview_id in self.interview_sessions:
            self.interview_sessions[interview_id]["is_recording"] = False
            
            await self.send_to_interview(interview_id, {
                "type": "recording_stopped",
                "timestamp": datetime.now().isoformat()
            })
    
    async def _handle_next_question(self, interview_id: str, data: dict):
        """Handle next question command"""
        question_index = data.get("question_index", 0)
        
        if interview_id in self.interview_sessions:
            self.interview_sessions[interview_id]["current_question"] = question_index
            
            await self.send_to_interview(interview_id, {
                "type": "question_changed",
                "data": {
                    "question_index": question_index,
                    "timestamp": datetime.now().isoformat()
                }
            })
    
    async def _handle_transcript_update(self, interview_id: str, data: dict):
        """Handle transcript update"""
        await self.send_to_interview(interview_id, {
            "type": "transcript_update",
            "data": {
                "text": data.get("text", ""),
                "timestamp": datetime.now().isoformat()
            }
        })

# Global connection manager instance
manager = ConnectionManager()
