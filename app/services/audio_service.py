import whisper
import openai
from typing import Optional, Dict, Any
import tempfile
import os
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class AudioService:
    def __init__(self):
        self.whisper_model = whisper.load_model(settings.WHISPER_MODEL)
        self.openai_client = openai.OpenAI()
    
    async def transcribe_audio(self, audio_file_path: str) -> Dict[str, Any]:
        """Transcribe audio file to text using Whisper"""
        try:
            result = self.whisper_model.transcribe(audio_file_path)
            
            return {
                "text": result["text"],
                "language": result["language"],
                "segments": result["segments"],
                "confidence": self._calculate_average_confidence(result["segments"])
            }
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            raise
    
    async def transcribe_audio_chunk(self, audio_data: bytes) -> Dict[str, Any]:
        """Transcribe audio chunk for real-time processing"""
        try:
            # Save audio chunk to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name
            
            try:
                result = await self.transcribe_audio(temp_file_path)
                return result
            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)
                
        except Exception as e:
            logger.error(f"Error transcribing audio chunk: {str(e)}")
            raise
    
    async def text_to_speech(self, text: str, voice: str = None) -> bytes:
        """Convert text to speech using OpenAI TTS"""
        try:
            voice = voice or settings.TTS_VOICE
            
            response = await self.openai_client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text,
                response_format="mp3"
            )
            
            return response.content
            
        except Exception as e:
            logger.error(f"Error converting text to speech: {str(e)}")
            raise
    
    async def analyze_voice_emotion(self, audio_file_path: str) -> Dict[str, Any]:
        """Analyze emotion and characteristics from voice"""
        try:
            # This would integrate with specialized voice analysis libraries
            # For now, returning mock data
            return {
                "emotion": "neutral",
                "confidence": 0.85,
                "stress_level": 0.3,
                "speaking_rate": "normal",
                "pitch_variation": "moderate",
                "voice_quality": "clear"
            }
            
        except Exception as e:
            logger.error(f"Error analyzing voice emotion: {str(e)}")
            raise
    
    def _calculate_average_confidence(self, segments: list) -> float:
        """Calculate average confidence from Whisper segments"""
        if not segments:
            return 0.0
        
        # Whisper doesn't provide confidence scores directly
        # This would need to be implemented with a different model
        return 0.85  # Mock confidence score

# Singleton instance
audio_service = AudioService()
