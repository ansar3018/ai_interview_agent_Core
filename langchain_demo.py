#!/usr/bin/env python3
"""
Demo script showing LangChain integration for AI Interview Agent

This script demonstrates:
1. Maintaining conversational context during interviews
2. Generating follow-up questions based on responses
3. Providing real-time AI feedback
4. Dynamic question adaptation
"""

import asyncio
import json
from typing import Dict, Any

# Mock data for demonstration
SAMPLE_RESUME = {
    "personal_info": {
        "name": "John Doe",
        "email": "john.doe@email.com",
        "location": "San Francisco, CA"
    },
    "skills": [
        {"type": "Python", "proficiency": "Expert"},
        {"type": "JavaScript", "proficiency": "Advanced"},
        {"type": "React", "proficiency": "Advanced"},
        {"type": "AWS", "proficiency": "Intermediate"}
    ],
    "experience": [
        {
            "company": "Tech Corp",
            "role": "Senior Software Engineer",
            "duration": "2020-2023",
            "responsibilities": ["Led team of 5 developers", "Implemented microservices architecture"]
        }
    ],
    "education": [
        {
            "institution": "Stanford University",
            "degree": "BS Computer Science",
            "year": "2020"
        }
    ],
    "summary": "Experienced software engineer with 3+ years in full-stack development"
}

async def demo_langchain_interview():
    """Demonstrate LangChain interview capabilities"""
    
    # Import the service (in real app, this would be from the FastAPI app)
    from app.services.langchain_service import langchain_service
    
    interview_id = "demo_interview_001"
    position = "Senior Software Engineer"
    
    print("🤖 AI Interview Agent with LangChain Demo")
    print("=" * 50)
    
    # Simulate interview conversation
    conversation_flow = [
        {
            "question": "Can you tell me about your experience with Python?",
            "response": "I've been working with Python for about 4 years now. I started with Django for web development and then moved into data science with pandas and scikit-learn. Recently, I've been using FastAPI for building microservices."
        },
        {
            "question": "What was your most challenging project at Tech Corp?",
            "response": "The most challenging project was migrating our monolithic application to microservices. I led a team of 5 developers and we had to break down a large Django application into smaller, independent services. The biggest challenge was managing data consistency across services."
        },
        {
            "question": "How do you handle debugging in a microservices architecture?",
            "response": "I use distributed tracing with tools like Jaeger and centralized logging with ELK stack. I also implement comprehensive monitoring with Prometheus and Grafana to track service health and performance metrics."
        }
    ]
    
    print(f"📋 Candidate: John Doe")
    print(f"🎯 Position: {position}")
    print(f"🆔 Interview ID: {interview_id}")
    print()
    
    # Simulate the interview
    for i, qa_pair in enumerate(conversation_flow, 1):
        print(f"Q{i}: {qa_pair['question']}")
        print(f"A{i}: {qa_pair['response']}")
        print()
        
        # Add to LangChain memory
        langchain_service.add_to_conversation(
            interview_id=interview_id,
            question=qa_pair['question'],
            response=qa_pair['response']
        )
        
        # Get real-time feedback
        feedback = await langchain_service.provide_real_time_feedback(
            interview_id=interview_id,
            question=qa_pair['question'],
            response=qa_pair['response'],
            expected_keywords=["Python", "microservices", "team leadership"]
        )
        
        print(f"📊 AI Feedback:")
        print(f"   Score: {feedback['score']}/100")
        print(f"   Feedback: {feedback['feedback']}")
        print(f"   Strengths: {', '.join(feedback['strengths'])}")
        print(f"   Improvements: {', '.join(feedback['improvements'])}")
        print()
        
        # Generate follow-up question
        follow_up = await langchain_service.generate_follow_up_question(
            interview_id=interview_id,
            original_question=qa_pair['question'],
            candidate_response=qa_pair['response']
        )
        
        print(f"🔄 Follow-up Question: {follow_up}")
        print("-" * 50)
        print()
    
    # Generate next question based on context
    print("🎯 Generating next question based on conversation context...")
    next_question = await langchain_service.generate_next_question(
        interview_id=interview_id,
        resume_info=SAMPLE_RESUME,
        position=position,
        asked_questions=[qa['question'] for qa in conversation_flow]
    )
    
    print(f"Next Question: {next_question}")
    print()
    
    # Get conversation summary
    summary = langchain_service.get_conversation_summary(interview_id)
    print("📝 Conversation Summary:")
    print(summary)
    print()
    
    # Clear memory
    langchain_service.clear_conversation_memory(interview_id)
    print("🧹 Interview session cleared!")

async def demo_websocket_integration():
    """Demonstrate WebSocket integration with LangChain"""
    
    print("\n🌐 WebSocket Integration Demo")
    print("=" * 30)
    
    # Simulate WebSocket messages
    websocket_messages = [
        {
            "type": "next_question",
            "data": {
                "resume_info": SAMPLE_RESUME,
                "conversation_history": [],
                "position": "Senior Software Engineer"
            }
        },
        {
            "type": "candidate_response",
            "data": {
                "question": "Tell me about your Python experience",
                "response": "I've been using Python for 4 years, mainly for web development and data science."
            }
        },
        {
            "type": "request_feedback",
            "data": {
                "question": "Tell me about your Python experience",
                "response": "I've been using Python for 4 years, mainly for web development and data science.",
                "expected_keywords": ["Python", "experience", "web development"]
            }
        }
    ]
    
    for i, message in enumerate(websocket_messages, 1):
        print(f"WebSocket Message {i}: {message['type']}")
        print(f"Data: {json.dumps(message['data'], indent=2)}")
        print()

def main():
    """Run the LangChain demo"""
    print("🚀 Starting LangChain Integration Demo")
    print()
    
    # Run the main demo
    asyncio.run(demo_langchain_interview())
    
    # Run WebSocket demo
    asyncio.run(demo_websocket_integration())
    
    print("✅ Demo completed successfully!")

if __name__ == "__main__":
    main() 