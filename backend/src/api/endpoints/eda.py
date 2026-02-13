from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
from src.services.rag_service import rag_service
from src.services.storage_service import storage_service
from src.core.config import settings
from openai import OpenAI

router = APIRouter()
client = OpenAI(api_key=settings.OPENAI_API_KEY)

class EDAChatRequest(BaseModel):
    query: str
    history: List[Dict[str, str]] = []

class EDAChatResponse(BaseModel):
    answer: str

@router.post("/analysis/chat/{meeting_id}", response_model=EDAChatResponse)
async def chat_eda(meeting_id: str, request: EDAChatRequest):
    try:
        # 1. Fetch meeting data (transcript + analytics)
        # We need the full analysis for context
        meeting_data = await storage_service.get_meeting(meeting_id)
        if not meeting_data:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        analytics = meeting_data.analytics
        if not analytics:
            raise HTTPException(status_code=400, detail="Analytics not ready for this meeting")
            
        sentiment_data = analytics.sentiment_analysis or {}
        
        # 2. Construct System Prompt (from User Request)
        system_prompt = f"""
Project: MeetRecall AI
Focus: EDA Sentiment Analysis and Chat Interface

Role Definition
You are an AI Meeting Intelligence Agent embedded in the MeetRecall AI platform.
Your primary responsibility is to analyze meeting transcripts and provide sentiment based exploratory data analysis and accurate conversational responses grounded strictly in retrieved data.
You must behave as an analytical assistant, not a general chatbot.

Knowledge Base Scope
Your knowledge base consists only of:
- Meeting transcript text: (Available via RAG context if needed, but summary provided below)
- Speaker segmentation data: (Available in context)
- Timestamps and duration metadata: {meeting_data.metadata.duration} seconds
- Derived analytics such as sentiment scores, engagement scores, and speaking time distribution.

Analytics Context:
Overall Sentiment: {sentiment_data.get('overall', {})}
Speaker Sentiment: {sentiment_data.get('speakers', [])}
Topics: {[t.name for t in analytics.topics]}

You must not use external knowledge or assumptions beyond the provided data.

Chat Response Rules
When answering a user:
Retrieve relevant transcript segments and sentiment analytics.
Explain answers step by step when reasoning is required.
Reference speakers or timestamps when applicable.
Avoid vague or generic responses.
If information is missing or insufficient, clearly state the limitation.

Output Style Guidelines
Use clear paragraphs.
Avoid emojis, icons, or decorative formatting.
Maintain a neutral, professional, and analytical tone.
Prefer clarity and traceability over verbosity.
"""

        # 3. Use RAG to get relevant transcript chunks for the query
        # We reuse the RAG service's retrieval logic but use our own prompt
        # Actually RAG service chat method encapsulates everything. 
        # We should probably expose a retrieval method or just pass the context here.
        # For simplicity, let's just use the query and the pre-loaded analytics context.
        # If the query is about specific details, we might need RAG.
        # Let's try to fetch RAG context manually here or extend RAGService?
        # To avoid changing RAGService too much, let's use the rag_service to get simple context 
        # but we control the generation.
        
        # Simplified RAG lookup
        from src.core.database import SessionLocal
        from src.models.orm import TranscriptChunk
        from sqlalchemy import select
        
        db = SessionLocal()
        context_text = ""
        try:
             query_embedding = rag_service._get_embedding(request.query)
             results = db.scalars(
                select(TranscriptChunk)
                .filter(TranscriptChunk.meeting_id == meeting_id)
                .order_by(TranscriptChunk.embedding.l2_distance(query_embedding))
                .limit(5)
            ).all()
             context_text = "\n\n".join([f"[{c.chunk_index}] {c.text}" for c in results])
        finally:
            db.close()

        user_prompt = f"""
Context from Transcript:
{context_text}

User History:
{request.history}

User Question: {request.query}
"""

        # 4. Generate Response
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        return EDAChatResponse(answer=response.choices[0].message.content)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
