import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from langchain.memory import ConversationBufferMemory, ConversationSummaryMemory
from langchain_openai import ChatOpenAI
from langchain.chains import ConversationChain, LLMChain
from langchain.prompts import PromptTemplate
from langchain.schema import HumanMessage, AIMessage
from app.core.config import settings

logger = logging.getLogger(__name__)


class InterviewLangChainService:
    def __init__(self):
        """Initialize LangChain components for interview management"""
        self.llm = ChatOpenAI(
            model="gpt-4",
            temperature=0.7,
            api_key=settings.OPENAI_API_KEY
        )
        
        # Memory for maintaining conversation context
        self.conversation_memories: Dict[str, ConversationBufferMemory] = {}
        
        # Interview-specific prompt templates
        self.question_generation_prompt = PromptTemplate(
            input_variables=["resume_info", "conversation_history", "position", "asked_questions", "question_count"],
            template="""
            You are an expert AI interviewer conducting a {position} interview.
            
            Candidate's Resume Information:
            {resume_info}
            
            Conversation History:
            {conversation_history}
            
            Previously Asked Questions:
            {asked_questions}
            
            Current Question Count: {question_count}
            
            Based on the candidate's background and the conversation so far, generate the next most relevant interview question.
            
            INTERVIEW STRATEGY:
            1. For technical positions (Software Engineer, Developer, Data Scientist, etc.), follow this pattern:
               - Questions 1-3: Behavioral and experience questions
               - Questions 4-5: Include a coding/technical assessment question
               - Questions 6+: Continue with behavioral and technical questions
            
            2. For non-technical positions (Marketing, Sales, HR, etc.):
               - Focus on behavioral, situational, and experience-based questions
               - No coding questions needed
            
            3. When to include coding questions:
               - Position requires technical skills (programming, data analysis, etc.)
               - Candidate has technical background in resume
               - Question count is 4-6 (optimal timing)
               - No coding question has been asked yet
            
            CODING QUESTION FORMAT:
            If you decide to include a coding question, format it as:
            "Let's move to a technical assessment. Here's a coding problem for you: [Problem description with clear requirements, examples, and constraints]"
            
            The question should:
            1. Build upon previous responses
            2. Probe deeper into areas mentioned
            3. Be specific to their experience and skills
            4. Avoid repetition of already asked questions
            5. Be appropriate for a {position} role
            6. Include coding assessment when appropriate for technical roles
            
            IMPORTANT: If you have asked 8 or more questions OR if you have gathered sufficient information to make a hiring decision, respond with exactly: "INTERVIEW_COMPLETE: Thank you for completing the interview. We have gathered enough information to proceed with the evaluation."
            
            Otherwise, generate only the question text, no additional formatting.
            """
        )
        
        self.follow_up_prompt = PromptTemplate(
            input_variables=["question", "response", "conversation_history"],
            template="""
            You are an AI interviewer. The candidate just answered a question.
            
            Original Question: {question}
            Candidate's Response: {response}
            Conversation History: {conversation_history}
            
            Based on their response, generate a follow-up question that:
            1. Probes deeper into their answer
            2. Asks for specific examples or details
            3. Explores related aspects they mentioned
            4. Helps understand their experience better
            
            Generate only the follow-up question text.
            """
        )
        
        self.feedback_prompt = PromptTemplate(
            input_variables=["question", "response", "expected_keywords", "conversation_history"],
            template="""
            You are an expert interview evaluator. Analyze the candidate's response.
            
            Question: {question}
            Response: {response}
            Expected Keywords: {expected_keywords}
            Conversation Context: {conversation_history}
            
            Provide real-time feedback in JSON format:
            {{
                "score": 0-100,
                "feedback": "brief constructive feedback",
                "strengths": ["strength1", "strength2"],
                "improvements": ["improvement1", "improvement2"],
                "suggested_follow_up": "next question to ask",
                "confidence_level": "high/medium/low"
            }}
            """
        )
        
        self.coding_question_prompt = PromptTemplate(
            input_variables=["resume_info", "position", "difficulty_level", "question_count"],
            template="""
            You are an expert technical interviewer. Generate a coding question for a {position} position.
            
            Candidate's Resume Information:
            {resume_info}
            
            Position: {position}
            Difficulty Level: {difficulty_level}
            Question Count: {question_count}
            
            Based on the candidate's background and the position requirements, generate a coding question that:
            1. Is appropriate for the candidate's experience level and skills
            2. Tests relevant technical skills for the {position} role
            3. Has clear problem description with specific requirements
            4. Includes practical input/output examples
            5. Can be solved in 15-30 minutes
            6. Aligns with the candidate's technical background
            
            SKILL-BASED QUESTION SELECTION:
            - For Software Engineers: Focus on algorithms, data structures, system design
            - For Frontend Developers: Focus on JavaScript, React, DOM manipulation, UI/UX
            - For Backend Developers: Focus on APIs, databases, server-side logic
            - For Data Scientists: Focus on data manipulation, algorithms, statistical analysis
            - For DevOps Engineers: Focus on automation, infrastructure, deployment
            - For Mobile Developers: Focus on mobile-specific patterns, UI components
            
            DIFFICULTY ADJUSTMENT:
            - Junior positions: Basic algorithms, simple data structures
            - Mid-level positions: Moderate complexity, real-world scenarios
            - Senior positions: System design, optimization, advanced concepts
            
            Return the question in this JSON format:
            {{
                "question": "Clear problem description with specific requirements",
                "examples": [
                    {{"input": "example input", "output": "expected output"}}
                ],
                "constraints": ["constraint1", "constraint2"],
                "hints": ["hint1", "hint2"],
                "expected_approach": "Brief description of expected solution approach",
                "time_limit": "15-30 minutes"
            }}
            """
        )
        
        self.coding_evaluation_prompt = PromptTemplate(
            input_variables=["question", "solution", "expected_approach", "position"],
            template="""
            You are an expert code reviewer evaluating a coding solution.
            
            Problem: {question}
            Candidate's Solution: {solution}
            Expected Approach: {expected_approach}
            Position: {position}
            
            Evaluate the solution and provide feedback in JSON format:
            {{
                "score": 0-100,
                "correctness": "Correct/Partially Correct/Incorrect",
                "efficiency": "Excellent/Good/Fair/Poor",
                "code_quality": "Excellent/Good/Fair/Poor",
                "feedback": "Detailed feedback on the solution",
                "strengths": ["strength1", "strength2"],
                "improvements": ["improvement1", "improvement2"],
                "suggested_optimizations": ["optimization1", "optimization2"]
            }}
            """
        )
        
        # Initialize chains
        self.question_chain = LLMChain(
            llm=self.llm,
            prompt=self.question_generation_prompt
        )
        
        self.follow_up_chain = LLMChain(
            llm=self.llm,
            prompt=self.follow_up_prompt
        )
        
        self.feedback_chain = LLMChain(
            llm=self.llm,
            prompt=self.feedback_prompt
        )
        
        self.coding_question_chain = LLMChain(
            llm=self.llm,
            prompt=self.coding_question_prompt
        )
        
        self.coding_evaluation_chain = LLMChain(
            llm=self.llm,
            prompt=self.coding_evaluation_prompt
        )
    
    def get_or_create_memory(self, interview_id: str) -> ConversationBufferMemory:
        """Get or create conversation memory for an interview session"""
        if interview_id not in self.conversation_memories:
            self.conversation_memories[interview_id] = ConversationBufferMemory(
                return_messages=True,
                memory_key="conversation_history"
            )
        return self.conversation_memories[interview_id]
    
    async def generate_next_question(
        self,
        interview_id: str,
        resume_info: Dict[str, Any],
        position: str,
        asked_questions: List[str] = None
    ) -> str:
        """Generate the next interview question based on context"""
        try:
            memory = self.get_or_create_memory(interview_id)
            
            # Format resume info for prompt
            resume_text = self._format_resume_for_prompt(resume_info)
            
            # Get conversation history
            conversation_history = memory.buffer or ""
            
            # Format asked questions
            asked_questions_text = "\n".join(asked_questions or [])
            question_count = len(asked_questions or []) + 1
            
            # Enhanced technical position detection
            technical_positions = [
                "software engineer", "developer", "programmer", "software developer",
                "full stack developer", "frontend developer", "backend developer",
                "data scientist", "machine learning engineer", "data engineer",
                "devops engineer", "site reliability engineer", "cloud engineer",
                "systems engineer", "application developer", "web developer",
                "mobile developer", "ios developer", "android developer",
                "python developer", "java developer", "javascript developer",
                "react developer", "node.js developer", "database developer",
                "qa engineer", "test engineer", "automation engineer"
            ]
            
            # Check if position is technical
            is_technical_position = any(tech_pos in position.lower() for tech_pos in technical_positions)
            
            # Check if candidate has technical skills in resume
            has_technical_skills = False
            if resume_info:
                resume_text_lower = str(resume_info).lower()
                technical_skills = [
                    "programming", "coding", "software", "development", "python", "java", "javascript",
                    "react", "angular", "vue", "node.js", "sql", "database", "api", "git",
                    "docker", "kubernetes", "aws", "azure", "gcp", "machine learning",
                    "data analysis", "algorithm", "data structure", "web development",
                    "mobile development", "frontend", "backend", "full stack"
                ]
                has_technical_skills = any(skill in resume_text_lower for skill in technical_skills)
            
            # Determine if we should include a coding question
            should_include_coding = (
                is_technical_position and 
                has_technical_skills and
                question_count >= 4 and 
                question_count <= 6 and
                not any("coding" in q.lower() or "programming" in q.lower() or "code" in q.lower() or "technical assessment" in q.lower()
                       for q in (asked_questions or []))
            )
            
            # Log the decision process
            logger.info(f"Coding question decision for interview {interview_id}:")
            logger.info(f"  - Position: {position}")
            logger.info(f"  - Is technical position: {is_technical_position}")
            logger.info(f"  - Has technical skills: {has_technical_skills}")
            logger.info(f"  - Question count: {question_count}")
            logger.info(f"  - Should include coding: {should_include_coding}")
            
            if should_include_coding:
                # Determine appropriate difficulty level
                difficulty_level = self._determine_difficulty_level(resume_info, position)
                
                # Generate a coding question
                coding_question = await self.generate_coding_question(
                    interview_id=interview_id,
                    resume_info=resume_info,
                    position=position,
                    difficulty_level=difficulty_level,
                    question_count=question_count
                )
                
                # Format the coding question as a regular interview question
                formatted_coding_question = f"""
Let's move to a technical assessment. Here's a coding problem for you:

{coding_question['question']}

Examples:
{chr(10).join([f"Input: {ex['input']} → Output: {ex['output']}" for ex in coding_question.get('examples', [])])}

Constraints:
{chr(10).join([f"• {constraint}" for constraint in coding_question.get('constraints', [])])}

Hints:
{chr(10).join([f"• {hint}" for hint in coding_question.get('hints', [])])}

Please explain your approach to solving this problem and walk me through your solution.
"""
                
                return formatted_coding_question.strip()
            
            # Generate regular question using LangChain
            response = await self.question_chain.ainvoke({
                "resume_info": resume_text,
                "conversation_history": conversation_history,
                "position": position,
                "asked_questions": asked_questions_text,
                "question_count": question_count
            })
            
            response_text = response["text"].strip()
            
            # Check if the interview should end
            if response_text.startswith("INTERVIEW_COMPLETE:"):
                return "INTERVIEW_COMPLETE: Thank you for completing the interview. We have gathered enough information to proceed with the evaluation."
            
            return response_text
            
        except Exception as e:
            logger.error(f"Error generating next question: {str(e)}")
            return "Could you tell me about your experience with this role?"
    
    async def generate_follow_up_question(
        self,
        interview_id: str,
        original_question: str,
        candidate_response: str
    ) -> str:
        """Generate a follow-up question based on the candidate's response"""
        try:
            memory = self.get_or_create_memory(interview_id)
            conversation_history = memory.buffer or ""
            
            response = await self.follow_up_chain.ainvoke({
                "question": original_question,
                "response": candidate_response,
                "conversation_history": conversation_history
            })
            
            return response["text"].strip()
            
        except Exception as e:
            logger.error(f"Error generating follow-up question: {str(e)}")
            return "Could you elaborate on that?"
    
    async def provide_real_time_feedback(
        self,
        interview_id: str,
        question: str,
        response: str,
        expected_keywords: List[str] = None
    ) -> Dict[str, Any]:
        """Provide real-time feedback on candidate's response"""
        try:
            memory = self.get_or_create_memory(interview_id)
            conversation_history = memory.buffer or ""
            
            response_text = await self.feedback_chain.ainvoke({
                "question": question,
                "response": response,
                "expected_keywords": ", ".join(expected_keywords or []),
                "conversation_history": conversation_history
            })
            
            # Parse JSON response
            feedback_data = json.loads(response_text["text"])
            return feedback_data
            
        except Exception as e:
            logger.error(f"Error providing feedback: {str(e)}")
            return {
                "score": 50,
                "feedback": "Response received, continuing with interview",
                "strengths": [],
                "improvements": [],
                "suggested_follow_up": "",
                "confidence_level": "low"
            }
    
    def add_to_conversation(
        self,
        interview_id: str,
        question: str,
        response: str
    ):
        """Add a Q&A pair to the conversation memory"""
        try:
            memory = self.get_or_create_memory(interview_id)
            
            # Add the exchange to memory
            memory.chat_memory.add_user_message(f"Question: {question}")
            memory.chat_memory.add_ai_message(f"Answer: {response}")
            
            logger.info(f"Added Q&A to conversation memory for interview {interview_id}")
            
        except Exception as e:
            logger.error(f"Error adding to conversation memory: {str(e)}")
    
    def get_conversation_summary(self, interview_id: str) -> str:
        """Get a summary of the conversation so far"""
        try:
            memory = self.get_or_create_memory(interview_id)
            return memory.buffer or "No conversation history available."
        except Exception as e:
            logger.error(f"Error getting conversation summary: {str(e)}")
            return "Unable to retrieve conversation summary."
    
    def clear_conversation_memory(self, interview_id: str):
        """Clear conversation memory for an interview"""
        if interview_id in self.conversation_memories:
            del self.conversation_memories[interview_id]
            logger.info(f"Cleared conversation memory for interview {interview_id}")
    
    async def generate_coding_question(
        self,
        interview_id: str,
        resume_info: Dict[str, Any],
        position: str,
        difficulty_level: str = "medium",
        question_count: int = 1
    ) -> Dict[str, Any]:
        """Generate a coding question based on candidate's background"""
        try:
            resume_text = self._format_resume_for_prompt(resume_info)
            
            response = await self.coding_question_chain.ainvoke({
                "resume_info": resume_text,
                "position": position,
                "difficulty_level": difficulty_level,
                "question_count": question_count
            })
            
            # Parse JSON response
            coding_question = json.loads(response["text"])
            return coding_question
            
        except Exception as e:
            logger.error(f"Error generating coding question: {str(e)}")
            return {
                "question": "Write a function to reverse a string.",
                "examples": [{"input": "hello", "output": "olleh"}],
                "constraints": ["Use only basic string operations"],
                "hints": ["Think about using a loop"],
                "expected_approach": "Iterate through the string in reverse order",
                "time_limit": "15-30 minutes"
            }
    
    async def evaluate_coding_solution(
        self,
        interview_id: str,
        question: str,
        solution: str,
        expected_approach: str,
        position: str
    ) -> Dict[str, Any]:
        """Evaluate a coding solution"""
        try:
            response = await self.coding_evaluation_chain.ainvoke({
                "question": question,
                "solution": solution,
                "expected_approach": expected_approach,
                "position": position
            })
            
            # Parse JSON response
            evaluation = json.loads(response["text"])
            return evaluation
            
        except Exception as e:
            logger.error(f"Error evaluating coding solution: {str(e)}")
            return {
                "score": 50,
                "correctness": "Partially Correct",
                "efficiency": "Fair",
                "code_quality": "Fair",
                "feedback": "Solution received, evaluation in progress",
                "strengths": [],
                "improvements": [],
                "suggested_optimizations": []
            }
    
    def _format_resume_for_prompt(self, resume_info: Dict[str, Any]) -> str:
        """Format resume information for use in prompts"""
        try:
            formatted = []
            
            # Personal info
            if "personal_info" in resume_info:
                personal = resume_info["personal_info"]
                formatted.append(f"Name: {personal.get('name', 'N/A')}")
                formatted.append(f"Location: {personal.get('location', 'N/A')}")
            
            # Skills
            if "skills" in resume_info:
                skills = resume_info["skills"]
                skill_text = ", ".join([f"{s.get('type', '')} ({s.get('proficiency', '')})" 
                                      for s in skills if isinstance(s, dict)])
                formatted.append(f"Skills: {skill_text}")
            
            # Experience
            if "experience" in resume_info:
                experience = resume_info["experience"]
                exp_text = []
                for exp in experience:
                    if isinstance(exp, dict):
                        exp_text.append(f"{exp.get('role', '')} at {exp.get('company', '')} "
                                      f"({exp.get('duration', '')})")
                formatted.append(f"Experience: {'; '.join(exp_text)}")
            
            # Education
            if "education" in resume_info:
                education = resume_info["education"]
                edu_text = []
                for edu in education:
                    if isinstance(edu, dict):
                        edu_text.append(f"{edu.get('degree', '')} from {edu.get('institution', '')} "
                                      f"({edu.get('year', '')})")
                formatted.append(f"Education: {'; '.join(edu_text)}")
            
            # Summary
            if "summary" in resume_info:
                formatted.append(f"Summary: {resume_info['summary']}")
            
            return "\n".join(formatted)
            
        except Exception as e:
            logger.error(f"Error formatting resume: {str(e)}")
            return "Resume information not available"

    def _determine_difficulty_level(self, resume_info: Dict[str, Any], position: str) -> str:
        """Determine the appropriate difficulty level based on candidate's experience"""
        try:
            # Extract experience information from resume
            experience_years = 0
            position_level = "mid"  # default to mid-level
            
            # Check for experience indicators in resume
            resume_text = str(resume_info).lower()
            
            # Look for years of experience
            import re
            experience_patterns = [
                r'(\d+)\s*years?\s*of\s*experience',
                r'experience:\s*(\d+)\s*years?',
                r'(\d+)\s*years?\s*in\s*development',
                r'(\d+)\s*years?\s*as\s*developer'
            ]
            
            for pattern in experience_patterns:
                match = re.search(pattern, resume_text)
                if match:
                    experience_years = int(match.group(1))
                    break
            
            # Check for senior/junior indicators in position title
            position_lower = position.lower()
            if any(word in position_lower for word in ["senior", "lead", "principal", "architect"]):
                position_level = "senior"
            elif any(word in position_lower for word in ["junior", "entry", "associate", "trainee"]):
                position_level = "junior"
            
            # Determine difficulty based on experience and position level
            if position_level == "senior" or experience_years >= 5:
                return "hard"
            elif position_level == "junior" or experience_years <= 2:
                return "easy"
            else:
                return "medium"
                
        except Exception as e:
            logger.error(f"Error determining difficulty level: {str(e)}")
            return "medium"  # default to medium


# Global instance
langchain_service = InterviewLangChainService() 