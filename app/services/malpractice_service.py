from typing import Dict, Any, List
import logging
from datetime import datetime, timedelta
import numpy as np

logger = logging.getLogger(__name__)

class MalpracticeDetectionService:
    def __init__(self):
        self.suspicious_patterns = {
            "multiple_faces": {"weight": 0.3, "threshold": 2},
            "identity_changes": {"weight": 0.4, "threshold": 0.7},
            "extended_absence": {"weight": 0.2, "threshold": 30},  # seconds
            "voice_inconsistency": {"weight": 0.25, "threshold": 0.6},
            "unusual_pauses": {"weight": 0.15, "threshold": 5},  # count
            "gaze_deviation": {"weight": 0.2, "threshold": 0.4}  # percentage of time
        }
    
    async def analyze_interview_integrity(self, 
                                        video_analysis: Dict[str, Any],
                                        audio_analysis: Dict[str, Any],
                                        session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive malpractice analysis"""
        try:
            analysis = {
                "overall_score": 0,
                "flags": [],
                "detailed_analysis": {},
                "risk_level": "low",
                "recommendations": []
            }
            
            # Video-based analysis
            video_score, video_flags = await self._analyze_video_integrity(video_analysis)
            
            # Audio-based analysis
            audio_score, audio_flags = await self._analyze_audio_integrity(audio_analysis)
            
            # Session-based analysis
            session_score, session_flags = await self._analyze_session_integrity(session_data)
            
            # Combine scores (weighted average)
            analysis["overall_score"] = (
                video_score * 0.4 +
                audio_score * 0.3 +
                session_score * 0.3
            )
            
            # Combine flags
            analysis["flags"] = video_flags + audio_flags + session_flags
            
            # Determine risk level
            analysis["risk_level"] = self._determine_risk_level(analysis["overall_score"], analysis["flags"])
            
            # Generate recommendations
            analysis["recommendations"] = self._generate_recommendations(analysis["flags"])
            
            # Detailed breakdown
            analysis["detailed_analysis"] = {
                "video_integrity": {"score": video_score, "flags": video_flags},
                "audio_integrity": {"score": audio_score, "flags": audio_flags},
                "session_integrity": {"score": session_score, "flags": session_flags}
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing interview integrity: {str(e)}")
            raise
    
    async def _analyze_video_integrity(self, video_analysis: Dict[str, Any]) -> tuple[float, List[str]]:
        """Analyze video for signs of malpractice"""
        score = 100.0
        flags = []
        
        try:
            # Face detection consistency
            face_detection_rate = video_analysis.get("face_detection_rate", 1.0)
            if face_detection_rate < 0.8:
                score -= (0.8 - face_detection_rate) * 50
                flags.append("inconsistent_face_detection")
            
            # Identity consistency
            identity_match = video_analysis.get("average_identity_match", 1.0)
            if identity_match < self.suspicious_patterns["identity_changes"]["threshold"]:
                score -= (1.0 - identity_match) * 40
                flags.append("identity_inconsistency")
            
            # Multiple faces
            suspicious_counts = video_analysis.get("suspicious_activity_summary", {})
            if suspicious_counts.get("multiple_faces_detected", 0) > 0:
                score -= suspicious_counts["multiple_faces_detected"] * 15
                flags.append("multiple_faces_detected")
            
            # Gaze tracking
            looking_away_count = suspicious_counts.get("looking_away_from_camera", 0)
            total_frames = video_analysis.get("total_frames_analyzed", 1)
            gaze_deviation_rate = looking_away_count / total_frames
            
            if gaze_deviation_rate > self.suspicious_patterns["gaze_deviation"]["threshold"]:
                score -= gaze_deviation_rate * 30
                flags.append("excessive_gaze_deviation")
            
            return max(0, score), flags
            
        except Exception as e:
            logger.error(f"Error in video integrity analysis: {str(e)}")
            return 50.0, ["analysis_error"]
    
    async def _analyze_audio_integrity(self, audio_analysis: Dict[str, Any]) -> tuple[float, List[str]]:
        """Analyze audio for signs of malpractice"""
        score = 100.0
        flags = []
        
        try:
            # Voice consistency (mock implementation)
            voice_consistency = audio_analysis.get("voice_consistency", 1.0)
            if voice_consistency < self.suspicious_patterns["voice_inconsistency"]["threshold"]:
                score -= (1.0 - voice_consistency) * 35
                flags.append("voice_inconsistency")
            
            # Unusual silence patterns
            silence_periods = audio_analysis.get("silence_periods", [])
            long_silences = [s for s in silence_periods if s.get("duration", 0) > 10]
            
            if len(long_silences) > 3:
                score -= len(long_silences) * 5
                flags.append("unusual_silence_patterns")
            
            # Background noise analysis
            background_noise = audio_analysis.get("background_noise_level", 0)
            if background_noise > 0.7:
                score -= 15
                flags.append("high_background_noise")
            
            # Multiple voice detection
            if audio_analysis.get("multiple_voices_detected", False):
                score -= 25
                flags.append("multiple_voices_detected")
            
            return max(0, score), flags
            
        except Exception as e:
            logger.error(f"Error in audio integrity analysis: {str(e)}")
            return 50.0, ["analysis_error"]
    
    async def _analyze_session_integrity(self, session_data: Dict[str, Any]) -> tuple[float, List[str]]:
        """Analyze session behavior for signs of malpractice"""
        score = 100.0
        flags = []
        
        try:
            # Connection stability
            connection_drops = session_data.get("connection_drops", 0)
            if connection_drops > 2:
                score -= connection_drops * 10
                flags.append("frequent_connection_issues")
            
            # Tab switching or window focus changes
            focus_changes = session_data.get("focus_changes", 0)
            if focus_changes > 5:
                score -= focus_changes * 3
                flags.append("frequent_tab_switching")
            
            # Unusual response times
            response_times = session_data.get("response_times", [])
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
                if avg_response_time > 30:  # seconds
                    score -= 10
                    flags.append("unusually_long_response_times")
            
            # Device/browser changes
            if session_data.get("device_changes", 0) > 0:
                score -= 20
                flags.append("device_or_browser_changes")
            
            return max(0, score), flags
            
        except Exception as e:
            logger.error(f"Error in session integrity analysis: {str(e)}")
            return 50.0, ["analysis_error"]
    
    def _determine_risk_level(self, overall_score: float, flags: List[str]) -> str:
        """Determine risk level based on score and flags"""
        high_risk_flags = [
            "identity_inconsistency",
            "multiple_faces_detected",
            "multiple_voices_detected",
            "device_or_browser_changes"
        ]
        
        has_high_risk_flags = any(flag in flags for flag in high_risk_flags)
        
        if overall_score < 60 or has_high_risk_flags:
            return "high"
        elif overall_score < 80 or len(flags) > 3:
            return "medium"
        else:
            return "low"
    
    def _generate_recommendations(self, flags: List[str]) -> List[str]:
        """Generate recommendations based on detected issues"""
        recommendations = []
        
        flag_recommendations = {
            "identity_inconsistency": "Consider manual identity verification",
            "multiple_faces_detected": "Review video for unauthorized assistance",
            "multiple_voices_detected": "Investigate potential coaching or assistance",
            "excessive_gaze_deviation": "Review for potential screen reading or external assistance",
            "voice_inconsistency": "Verify candidate identity through additional means",
            "unusual_silence_patterns": "Check for potential technical assistance or coaching",
            "frequent_tab_switching": "Investigate potential research or external assistance",
            "device_or_browser_changes": "Verify technical setup and candidate identity"
        }
        
        for flag in flags:
            if flag in flag_recommendations:
                recommendations.append(flag_recommendations[flag])
        
        if not recommendations:
            recommendations.append("No specific concerns identified")
        
        return recommendations
    
    async def real_time_monitoring(self, 
                                 current_frame_analysis: Dict[str, Any],
                                 current_audio_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Real-time malpractice monitoring during interview"""
        try:
            alerts = []
            severity = "low"
            
            # Check for immediate red flags
            if current_frame_analysis.get("face_count", 1) > 1:
                alerts.append("Multiple faces detected")
                severity = "high"
            
            if not current_frame_analysis.get("face_detected", True):
                alerts.append("No face detected")
                severity = "medium"
            
            identity_match = current_frame_analysis.get("identity_match", 1.0)
            if identity_match < 0.6:
                alerts.append("Identity verification failed")
                severity = "high"
            
            if current_audio_analysis.get("multiple_voices_detected", False):
                alerts.append("Multiple voices detected")
                severity = "high"
            
            return {
                "alerts": alerts,
                "severity": severity,
                "timestamp": datetime.now().isoformat(),
                "requires_intervention": severity == "high"
            }
            
        except Exception as e:
            logger.error(f"Error in real-time monitoring: {str(e)}")
            return {"alerts": ["Monitoring error"], "severity": "medium"}

# Singleton instance
malpractice_service = MalpracticeDetectionService()
