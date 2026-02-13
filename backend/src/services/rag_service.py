from openai import OpenAI
from sqlalchemy.orm import Session
from sqlalchemy import select, text
from src.core.config import settings
from src.models.orm import Meeting, TranscriptChunk
from src.utils.logging import setup_logger
from src.core.database import SessionLocal
import numpy as np

logger = setup_logger(__name__)

class RAGService:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        # OpenAI "text-embedding-3-small" supports dimensions parameter.
        self.embedding_model = "text-embedding-3-small"
        self.embedding_dim = 768 
        self.chat_model = "gpt-4o" 

    def index_meeting(self, meeting_id: str, transcript_text: str):
        """
        Splits transcript into chunks, generates embeddings, and saves to DB.
        """
        db = SessionLocal()
        try:
            # Chunking Strategy (Simple: Split by paragraphs or fixed size)
            chunks_data = self._chunk_text(transcript_text)
            
            logger.info(f"Indexing {len(chunks_data)} chunks for meeting {meeting_id}")

            # Delete existing chunks for this meeting to avoid duplicates if re-indexing
            db.execute(
                text("DELETE FROM transcript_chunks WHERE meeting_id = :meeting_id"),
                {"meeting_id": meeting_id}
            )

            for i, chunk_text in enumerate(chunks_data):
                # Generate Embedding
                embedding = self._get_embedding(chunk_text)
                
                # Save to DB
                db_chunk = TranscriptChunk(
                    meeting_id=meeting_id,
                    chunk_index=i,
                    text=chunk_text,
                    embedding=embedding
                )
                db.add(db_chunk)
            
            db.commit()
            logger.info(f"Indexing complete for {meeting_id}")
            
        except Exception as e:
            logger.error(f"Error indexing meeting {meeting_id}: {e}")
            db.rollback()
        finally:
            db.close()

    def chat(self, meeting_id: str, query: str) -> str:
        """
        Retrieves relevant context and generates an answer.
        """
        db = SessionLocal()
        try:
            # Embed Query
            query_embedding = self._get_embedding(query)
            
            # Vector Search (using l2_distance from pgvector)
            # We want the chunks with the smallest distance
            results = db.scalars(
                select(TranscriptChunk)
                .filter(TranscriptChunk.meeting_id == meeting_id)
                .order_by(TranscriptChunk.embedding.l2_distance(query_embedding))
                .limit(5)
            ).all()
            
            if not results:
                return "I couldn't find any relevant information in the meeting transcript."

            # Construct Prompt
            context_text = "\n\n".join([f"Chunk {c.chunk_index}: {c.text}" for c in results])
            
            system_prompt = """
            You are a helpful and intelligent meeting assistant. Your goal is to answer the user's question accurately using the provided transcript segments.
            
            Instructions:
            - Synthesize information from the provided chunks to answer the question.
            - If the chunks contain partial information, try to piece it together.
            - If the answer is legitimately not in the context, explicitly state that the provided transcript does not contain the answer, but do not guess.
            - **Language Support**: ALWAYS reply in the same language as the user's question. If the user asks in Indonesian, answer in Indonesian. If in English, answer in English.
            - Maintain a professional and helpful tone.
            """
            
            user_prompt = f"""
            Context from meeting transcript:
            {context_text}
            
            Question: {query}
            """
            
            # Generate Answer
            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return "Sorry, I encountered an error while processing your request."
        finally:
            db.close()

    def _get_embedding(self, text: str):
        text = text.replace("\n", " ")
        return self.client.embeddings.create(
            input=[text], 
            model=self.embedding_model,
            dimensions=self.embedding_dim
        ).data[0].embedding

    def _chunk_text(self, text: str, chunk_size=500, overlap=50) -> list[str]:
        chunks = []
        if not text:
            return []
        
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start += chunk_size - overlap
        return chunks

rag_service = RAGService()