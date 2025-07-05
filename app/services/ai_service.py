import os

import openai
from typing import List, Dict, Any
import json
import logging
from app.core.config import settings
from app.models.pydantic_models import ResumeAnalysis

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self):
        api_key = settings.OPENAI_API_KEY
        self.client = openai.OpenAI(api_key=api_key)

    async def analyze_resume(self, resume_text: str) -> ResumeAnalysis:
        """Analyze resume and extract structured information"""
        try:
            prompt = f"""
            Analyze the following resume and extract structured information in JSON format.

            Resume Content:
            {resume_text}

            Please provide a comprehensive analysis including:
            1. Personal information (name, email, phone, location)
            2. Skills categorized by type with proficiency levels
            3. Work experience with key responsibilities
            4. Education background
            5. Notable projects with technologies used
            6. A brief professional summary
            7. 5-8 recommended interview questions tailored to their background

            Ensure the JSON response matches the following schema:
            {{
                "personal_info": {{
                    "name": "string",
                    "email": "string",
                    "phone": "string",
                    "location": "string"
                }},
                "skills": [
                    {{
                        "type": "string",
                        "proficiency": "string"
                    }}
                ],
                "experience": [
                    {{
                        "company": "string",
                        "role": "string",
                        "duration": "string",
                        "responsibilities": ["string"]
                    }}
                ],
                "education": [
                    {{
                        "institution": "string",
                        "degree": "string",
                        "year": "string"
                    }}
                ],
                "projects": [
                    {{
                        "name": "string",
                        "technologies": ["string"],
                        "description": "string"
                    }}
                ],
                "summary": "string",
                "recommended_questions": [
                    {{
                        "question": "string",
                        "category": "string",
                        "difficulty": "string"
                    }}
                ]
            }}
            Return the response in JSON format matching the ResumeAnalysis schema.
            """
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert resume analyzer. "
                                                  "Return in JSON format.ignore missing data."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )

            analysis_json = json.loads(response.choices[0].message.content)
            return ResumeAnalysis(**analysis_json)

        except Exception as e:
            logger.error(f"Error analyzing resume: {str(e)}")
            raise

    async def generate_questions(self,
                                 candidate_skills: List[str],
                                 position: str,
                                 difficulty: str = "medium",
                                 count: int = 5) -> List[Dict[str, Any]]:
        """Generate personalized interview questions"""
        try:
            prompt = f"""
            Generate {count} interview questions for a {position} position.
            
            Candidate Skills: {', '.join(candidate_skills)}
            Difficulty Level: {difficulty}
            
            For each question, provide JSON with:
            1. question: The question text
            2. category: technical/behavioral/situational
            3. difficulty: easy/medium/hard
            4. expected_keywords: Array of keywords for good answers
            5. model_answer: A sample good answer
            
            Return as JSON array.
            """

            response =  self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert technical interviewer. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4
            )

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            logger.error(f"Error generating questions: {str(e)}")
            raise

    async def evaluate_response(self,
                                question: str,
                                response: str,
                                expected_keywords: List[str],
                                model_answer: str) -> Dict[str, Any]:
        """Evaluate candidate's response to a question"""
        try:
            prompt = f"""
            Evaluate the following interview response and return JSON:
            
            Question: {question}
            Candidate Response: {response}
            Expected Keywords: {', '.join(expected_keywords)}
            Model Answer: {model_answer}
            
            Return JSON with:
            {{
                "score": 0-100,
                "feedback": "detailed feedback string",
                "strengths": ["strength1", "strength2"],
                "improvements": ["improvement1", "improvement2"],
                "keywords_detected": ["keyword1", "keyword2"],
                "sentiment_score": 0.0-1.0
            }}
            """

            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert interview evaluator. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2
            )

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            logger.error(f"Error evaluating response: {str(e)}")
            raise


ai_service = AIService()
