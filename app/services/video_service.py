import cv2
import numpy as np
from typing import Dict, Any, List, Optional
import logging
import base64
from io import BytesIO
from PIL import Image
import face_recognition
import mediapipe as mp

logger = logging.getLogger(__name__)

class VideoService:
    def __init__(self):
        self.mp_face_detection = mp.solutions.face_detection
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_detection = self.mp_face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.5
        )
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # Store reference face encoding for identity verification
        self.reference_face_encoding = None
    
    async def process_video_frame(self, frame_data: str) -> Dict[str, Any]:
        """Process a single video frame for analysis"""
        try:
            # Decode base64 frame
            frame_bytes = base64.b64decode(frame_data)
            image = Image.open(BytesIO(frame_bytes))
            frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            analysis = {
                "face_detected": False,
                "face_count": 0,
                "gaze_direction": None,
                "emotion": None,
                "identity_match": None,
                "suspicious_activity": []
            }
            
            # Face detection
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.face_detection.process(rgb_frame)
            
            if results.detections:
                analysis["face_detected"] = True
                analysis["face_count"] = len(results.detections)
                
                # Analyze first detected face
                detection = results.detections[0]
                analysis.update(await self._analyze_face(rgb_frame, detection))
            
            # Check for suspicious activity
            analysis["suspicious_activity"] = await self._detect_suspicious_activity(frame, analysis)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error processing video frame: {str(e)}")
            raise
    
    async def _analyze_face(self, frame: np.ndarray, detection) -> Dict[str, Any]:
        """Analyze detected face for various characteristics"""
        try:
            analysis = {}
            
            # Face encoding for identity verification
            face_encodings = face_recognition.face_encodings(frame)
            if face_encodings:
                current_encoding = face_encodings[0]
                
                if self.reference_face_encoding is None:
                    # Set first face as reference
                    self.reference_face_encoding = current_encoding
                    analysis["identity_match"] = 1.0
                else:
                    # Compare with reference
                    distance = face_recognition.face_distance([self.reference_face_encoding], current_encoding)[0]
                    analysis["identity_match"] = max(0, 1 - distance)
            
            # Gaze direction analysis using face mesh
            mesh_results = self.face_mesh.process(frame)
            if mesh_results.multi_face_landmarks:
                landmarks = mesh_results.multi_face_landmarks[0]
                analysis["gaze_direction"] = self._calculate_gaze_direction(landmarks)
            
            # Emotion detection (simplified)
            analysis["emotion"] = await self._detect_emotion(frame)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing face: {str(e)}")
            return {}
    
    def _calculate_gaze_direction(self, landmarks) -> Dict[str, float]:
        """Calculate gaze direction from face landmarks"""
        try:
            # Simplified gaze calculation
            # In production, this would use more sophisticated eye tracking
            left_eye = landmarks.landmark[33]  # Left eye landmark
            right_eye = landmarks.landmark[362]  # Right eye landmark
            nose_tip = landmarks.landmark[1]  # Nose tip
            
            # Calculate relative positions
            eye_center_x = (left_eye.x + right_eye.x) / 2
            eye_center_y = (left_eye.y + right_eye.y) / 2
            
            # Gaze direction relative to face center
            gaze_x = nose_tip.x - eye_center_x
            gaze_y = nose_tip.y - eye_center_y
            
            return {
                "horizontal": float(gaze_x),
                "vertical": float(gaze_y),
                "looking_at_camera": abs(gaze_x) < 0.1 and abs(gaze_y) < 0.1
            }
            
        except Exception as e:
            logger.error(f"Error calculating gaze direction: {str(e)}")
            return {"horizontal": 0, "vertical": 0, "looking_at_camera": True}
    
    async def _detect_emotion(self, frame: np.ndarray) -> Dict[str, Any]:
        """Detect emotion from facial expression"""
        try:
            # This would integrate with emotion detection models
            # For now, returning mock data
            return {
                "primary_emotion": "neutral",
                "confidence": 0.75,
                "emotions": {
                    "happy": 0.1,
                    "sad": 0.05,
                    "angry": 0.02,
                    "surprised": 0.08,
                    "neutral": 0.75
                }
            }
            
        except Exception as e:
            logger.error(f"Error detecting emotion: {str(e)}")
            return {"primary_emotion": "neutral", "confidence": 0.0}
    
    async def _detect_suspicious_activity(self, frame: np.ndarray, face_analysis: Dict[str, Any]) -> List[str]:
        """Detect suspicious activities that might indicate cheating"""
        suspicious_activities = []
        
        try:
            # Multiple faces detected
            if face_analysis.get("face_count", 0) > 1:
                suspicious_activities.append("multiple_faces_detected")
            
            # No face detected
            if not face_analysis.get("face_detected", False):
                suspicious_activities.append("no_face_detected")
            
            # Looking away from camera
            gaze = face_analysis.get("gaze_direction", {})
            if not gaze.get("looking_at_camera", True):
                suspicious_activities.append("looking_away_from_camera")
            
            # Identity mismatch
            identity_match = face_analysis.get("identity_match", 1.0)
            if identity_match < 0.7:
                suspicious_activities.append("identity_mismatch")
            
            return suspicious_activities
            
        except Exception as e:
            logger.error(f"Error detecting suspicious activity: {str(e)}")
            return []
    
    async def analyze_video_file(self, video_path: str) -> Dict[str, Any]:
        """Analyze entire video file for comprehensive assessment"""
        try:
            cap = cv2.VideoCapture(video_path)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            analysis_results = []
            frame_interval = max(1, int(fps))  # Analyze every second
            
            for frame_num in range(0, frame_count, frame_interval):
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame = cap.read()
                
                if ret:
                    # Convert frame to base64 for processing
                    _, buffer = cv2.imencode('.jpg', frame)
                    frame_b64 = base64.b64encode(buffer).decode()
                    
                    frame_analysis = await self.process_video_frame(frame_b64)
                    frame_analysis["timestamp"] = frame_num / fps
                    analysis_results.append(frame_analysis)
            
            cap.release()
            
            # Aggregate results
            return self._aggregate_video_analysis(analysis_results)
            
        except Exception as e:
            logger.error(f"Error analyzing video file: {str(e)}")
            raise
    
    def _aggregate_video_analysis(self, frame_analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate frame-by-frame analysis into overall video assessment"""
        if not frame_analyses:
            return {}
        
        total_frames = len(frame_analyses)
        face_detected_count = sum(1 for f in frame_analyses if f.get("face_detected", False))
        
        # Calculate averages and statistics
        identity_matches = [f.get("identity_match", 0) for f in frame_analyses if f.get("identity_match") is not None]
        avg_identity_match = sum(identity_matches) / len(identity_matches) if identity_matches else 0
        
        # Count suspicious activities
        all_suspicious = []
        for frame in frame_analyses:
            all_suspicious.extend(frame.get("suspicious_activity", []))
        
        suspicious_counts = {}
        for activity in all_suspicious:
            suspicious_counts[activity] = suspicious_counts.get(activity, 0) + 1
        
        return {
            "total_frames_analyzed": total_frames,
            "face_detection_rate": face_detected_count / total_frames,
            "average_identity_match": avg_identity_match,
            "suspicious_activity_summary": suspicious_counts,
            "malpractice_score": self._calculate_malpractice_score(
                face_detected_count / total_frames,
                avg_identity_match,
                suspicious_counts
            )
        }
    
    def _calculate_malpractice_score(self, face_detection_rate: float, 
                                   identity_match: float, 
                                   suspicious_counts: Dict[str, int]) -> float:
        """Calculate overall malpractice score (0-100, higher is better)"""
        base_score = 100
        
        # Deduct points for poor face detection
        if face_detection_rate < 0.8:
            base_score -= (0.8 - face_detection_rate) * 50
        
        # Deduct points for identity mismatch
        if identity_match < 0.9:
            base_score -= (0.9 - identity_match) * 30
        
        # Deduct points for suspicious activities
        for activity, count in suspicious_counts.items():
            if activity == "multiple_faces_detected":
                base_score -= count * 10
            elif activity == "looking_away_from_camera":
                base_score -= min(count * 2, 20)  # Cap at 20 points
            elif activity == "identity_mismatch":
                base_score -= count * 15
        
        return max(0, min(100, base_score))

# Singleton instance
video_service = VideoService()
