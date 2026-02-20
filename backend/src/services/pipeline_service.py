import asyncio
import logging
from datetime import datetime
from pathlib import Path

from src.services.transcription_service import transcription_service
from src.services.analysis_service import analysis_service
from src.services.rag_service import rag_service
from src.services.storage_service import storage_service
from src.models.schemas import ProcessedMeeting, MeetingMetadata
from src.core.config import settings

logger = logging.getLogger(__name__)

class PipelineService:
    async def process_meeting(self, video_path: Path, filename: str, meeting_id: str, provider: str = "assemblyai", model: str = "universal-3-pro") -> str:
        """
        Orchestrates the V2 processing pipeline:
        1. Extract Audio
        2. Transcribe (Selected Provider with specific model)
        3. Analyze (OpenAI - Summary, Action Items, Chapters, etc.)
        4. RAG Indexing (OpenAI Embeddings)
        5. Save all results
        """

        # Initial metadata save
        metadata = MeetingMetadata(
            filename=filename,
            duration=0.0,
            upload_timestamp=datetime.now(),
            status="PROCESSING",
            provider=provider
        )
        
        process_data = ProcessedMeeting(
            id=meeting_id,
            metadata=metadata
        )
        await storage_service.save_meeting(process_data) 
        
        try:
            # Audio Extraction
            if video_path.suffix.lower() in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
                 audio_path = await storage_service.extract_audio(video_path)
            else:
                 audio_path = video_path

            # Validate Audio before sending to API
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio file missing after extraction: {audio_path}")
            if audio_path.stat().st_size < 1024:
                raise ValueError(f"Audio file too small ({audio_path.stat().st_size} bytes). Extraction likely failed.")
            
            # Transcription (Variable Provider)
            logger.info(f"Starting transcription for {meeting_id} using {provider} with model {model}")
            transcription_result = await transcription_service.transcribe(audio_path, provider, model)
            
            process_data.transcript_text = transcription_result.transcript_text
            process_data.transcript_segments = transcription_result.segments
            process_data.metadata.status = "TRANSCRIBED"
            await storage_service.save_meeting(process_data)
            
            # Update duration from transcript
            process_data.metadata.duration = transcription_result.duration
            process_data.metadata.model_name = transcription_result.model_name
            
            # Analysis (OpenAI)
            logger.info(f"Starting analysis for {meeting_id}")
            analytics_result = await analysis_service.analyze_meeting(
                process_data.transcript_text, 
                process_data.transcript_segments
            )
            process_data.analytics = analytics_result
            
            # RAG Indexing (Background)
            logger.info(f"Starting RAG indexing for {meeting_id}")
            rag_service.index_meeting(meeting_id, process_data.transcript_text)

            # Final State
            process_data.metadata.status = "COMPLETED"
            await storage_service.save_meeting(process_data)
            
            logger.info(f"Processing complete for meeting {meeting_id}")
            
        except Exception as e:
            logger.error(f"Pipeline failed for meeting {meeting_id}: {e}")
            process_data.metadata.status = "FAILED"
            await storage_service.save_meeting(process_data)
            raise e
            
        return meeting_id

pipeline_service = PipelineService()
