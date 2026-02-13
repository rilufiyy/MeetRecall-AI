from openai import OpenAI
from src.core.config import settings
from src.models.schemas import AnalyticsResponse, SpeakerSegment
from src.utils.logging import setup_logger
import json
from typing import List

logger = setup_logger(__name__)

class AnalysisService:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4o" 

    async def analyze_meeting(self, transcript_text: str, segments: List[SpeakerSegment]) -> AnalyticsResponse:
        logger.info("Starting AI analysis...")
        
        # Calculate speaker percentage accurately from segments
        speaker_percentage = self._calculate_speaker_percentage(segments)
        
        system_prompt = """
        You are an advanced AI meeting analyst. Your goal is to extract structured intelligence from meeting transcripts.
        
        You MUST return a valid JSON object matching the following structure exactly:
        {
            "summary": "Concise executive summary of the meeting.",
            "action_items": [
                {"text": "Action item description", "owner": "Name or Unassigned", "timestamp": 0.0}
            ],
            "key_questions": ["Question 1?", "Question 2?"],
            "topics": [
                {"name": "Topic 1", "timestamp": 0.0},
                {"name": "Topic 2", "timestamp": 120.5}
            ],
            "keywords": ["keyword1", "keyword2"]
        }
        
        Rules:
        - "timestamp" should be the float start time in seconds where the item was discussed. Use the provided transcript segments to estimate if needed.
        - "owner" should be inferred from context.
        """
        
        # Prepare context with timestamps
        # We'll truncate if too long, but GPT-4o has 128k context so should be fine for most meetings.
        transcript_context = ""
        for seg in segments[:1000]: # Safety limit
            transcript_context += f"[{seg.start_time:.1f}s] {seg.speaker}: {seg.text}\n"
            
        if not transcript_context:
             # Fallback if no segments (shouldn't happen with Assembly)
             transcript_context = transcript_text[:50000]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Analyze this meeting:\n\n{transcript_context}"}
                ],
                response_format={"type": "json_object"}
            )
            
            data = json.loads(response.choices[0].message.content)
            
            return AnalyticsResponse(
                summary=data.get("summary", "No summary generated."),
                action_items=data.get("action_items", []),
                key_questions=data.get("key_questions", []),
                topics=data.get("topics", []),
                keywords=data.get("keywords", []),
                speaker_percentage=speaker_percentage
            )
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            # Return empty/default
            return AnalyticsResponse(
                summary="Analysis failed.",
                action_items=[],
                key_questions=[],
                topics=[],
                keywords=[],
                speaker_percentage=speaker_percentage
            )

    def _calculate_speaker_percentage(self, segments: List[SpeakerSegment]):
        total_duration = 0.0
        speaker_time = {}
        
        for seg in segments:
            duration = seg.end_time - seg.start_time
            total_duration += duration
            speaker_time[seg.speaker] = speaker_time.get(seg.speaker, 0.0) + duration
            
        if total_duration == 0:
            return {}
            
        return {k: round((v / total_duration) * 100, 2) for k, v in speaker_time.items()}

analysis_service = AnalysisService()
