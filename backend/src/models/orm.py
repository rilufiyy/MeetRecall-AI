from sqlalchemy import Column, String, Float, DateTime, JSON, ForeignKey, Integer, Text, Boolean
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from src.core.database import Base
from datetime import datetime

class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(String, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    duration = Column(Float, default=0.0)
    upload_timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="processing") # processing, completed, failed
    
    # Transcription Data
    transcript_text = Column(Text, nullable=True) # Normalized Full Text
    transcript_segments = Column(JSON, nullable=True) # Segments with speaker/time
    
    # Metadata about processing
    processing_mode = Column(String, default="single")
    provider = Column(String, nullable=True)
    model_name = Column(String, nullable=True)

    # Relationships
    analytics = relationship("Analytics", back_populates="meeting", uselist=False, cascade="all, delete-orphan")
    chunks = relationship("TranscriptChunk", back_populates="meeting", cascade="all, delete-orphan")

class Analytics(Base):
    __tablename__ = "analytics"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(String, ForeignKey("meetings.id"), unique=True, nullable=False)
    
    # Insights
    summary = Column(Text, nullable=True)
    action_items = Column(JSON, nullable=True) 
    key_questions = Column(JSON, nullable=True) 
    topics = Column(JSON, nullable=True) 
    keywords = Column(JSON, nullable=True) 
    speaker_percentage = Column(JSON, nullable=True) 
    
    meeting = relationship("Meeting", back_populates="analytics")

class TranscriptChunk(Base):
    __tablename__ = "transcript_chunks"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(String, ForeignKey("meetings.id"), nullable=False)
    
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    
    embedding = Column(Vector(768))

    meeting = relationship("Meeting", back_populates="chunks")
