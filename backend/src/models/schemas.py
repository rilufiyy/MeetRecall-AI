from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime

# --- Shared Models ---
class SpeakerSegment(BaseModel):
    start_time: float
    end_time: float
    speaker: str
    text: str

class ActionItem(BaseModel):
    text: str
    owner: Optional[str] = "Unassigned"
    timestamp: Optional[float] = 0.0

class Topic(BaseModel):
    name: str
    timestamp: Optional[float] = 0.0

# --- Response Models ---

class AnalyticsResponse(BaseModel):
    summary: Optional[str] = "No summary available."
    action_items: Optional[List[ActionItem]] = []
    key_questions: Optional[List[str]] = []
    topics: Optional[List[Topic]] = []
    keywords: Optional[List[str]] = []
    speaker_percentage: Optional[Dict[str, float]] = {}

class MeetingMetadata(BaseModel):
    filename: str
    duration: float
    upload_timestamp: datetime
    status: str
    provider: Optional[str] = None

class MeetingResponse(BaseModel):
    id: str
    metadata: MeetingMetadata
    transcript_text: Optional[str] = None # Renamed from transcript
    transcript_segments: Optional[List[SpeakerSegment]] = None # Renamed from segments
    analytics: Optional[AnalyticsResponse] = None

    class Config:
        from_attributes = True

class TranscriptionResult(BaseModel):
    transcript_text: str
    segments: List[SpeakerSegment] = []
    model_name: str
    language: str
    duration: float
    created_at: datetime = datetime.now()

# --- Internal Processing Models ---
class ProcessedMeeting(BaseModel):
    id: str
    metadata: MeetingMetadata
    transcript_text: Optional[str] = None
    transcript_segments: Optional[List[SpeakerSegment]] = None
    analytics: Optional[AnalyticsResponse] = None
    
    class Config:
        from_attributes = True
