from datetime import datetime
import asyncio
import aiofiles
import shutil
from pathlib import Path
from src.core.config import settings
from src.core.database import SessionLocal
from src.models.orm import Meeting, Analytics
from src.models.schemas import ProcessedMeeting, MeetingMetadata, AnalyticsResponse, SpeakerSegment
from src.utils.logging import setup_logger
import json

logger = setup_logger(__name__)

class StorageService:
    async def save_upload(self, file, original_filename: str) -> Path:
        """Saves uploaded file to storage."""
        # Create safe filename
        safe_filename = f"{datetime.utcnow().timestamp()}_{original_filename.replace(' ', '_')}"
        file_path = settings.UPLOAD_DIR / safe_filename
        
        try:
            # Write file in chunks to avoid memory issues
            async with aiofiles.open(file_path, 'wb') as out_file:
                while content := await file.read(1024 * 1024):  # 1MB chunks
                    await out_file.write(content)
        except Exception as e:
            logger.error(f"Failed to save upload: {e}")
            raise e
            
        return file_path

    def _check_ffmpeg(self):
        """Validates ffmpeg is installed and reachable."""
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg not found in PATH. Please install ffmpeg.")

    async def extract_audio(self, input_path: Path) -> Path:
        """Video -> Audio (Mono, 16kHz) for optimal transcription."""
        self._check_ffmpeg()
        
        output_path = input_path.with_suffix('.mp3')
        
        # If it's already audio, just verify and return
        if input_path.suffix.lower() in ['.mp3', '.wav', '.m4a']:
            if not input_path.exists() or input_path.stat().st_size < 1024:
                 raise ValueError("Input audio file is missing or too small.")
            return input_path

        # Strict conversion: Mono (1ch), 16000Hz
        cmd = [
            'ffmpeg',
            '-i', str(input_path),
            '-vn',                
            '-acodec', 'libmp3lame',
            '-ac', '1',          
            '-ar', '16000',       # 16kHz
            '-q:a', '2',
            '-y',                 # Overwrite
            str(output_path)
        ]
        
        logger.info(f"Extracting audio: {' '.join(cmd)}")
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"ffmpeg failed: {stderr.decode()}")
                raise RuntimeError(f"ffmpeg extraction failed: {stderr.decode()}")
            
            # Post-extraction validation
            if not output_path.exists():
                raise FileNotFoundError(f"Audio extraction failed to create file: {output_path}")
            
            if output_path.stat().st_size < 1024: # < 1KB is suspicious
                 logger.error(f"Extracted audio too small: {output_path.stat().st_size} bytes")
                 raise ValueError("Extracted audio file is too small/corrupt.")

            logger.info(f"Audio extracted successfully: {output_path} ({output_path.stat().st_size} bytes)")
            return output_path

        except Exception as e:
            logger.error(f"Audio extraction error: {e}")
            raise e

    async def save_meeting(self, meeting_data: ProcessedMeeting):
        """Saves the meeting data to PostgreSQL (Sync wrapper)."""
        try:
            db = SessionLocal()
            
            # Check if exists
            existing_meeting = db.query(Meeting).filter(Meeting.id == meeting_data.id).first()
            
            # Prepare Analytics Data
            analytics_orm = None
            if meeting_data.analytics:
                # Check if analytics already exists for this meeting
                existing_analytics = db.query(Analytics).filter(Analytics.meeting_id == meeting_data.id).first()
                if existing_analytics:
                    analytics_orm = existing_analytics
                    analytics_orm.summary = meeting_data.analytics.summary
                    analytics_orm.action_items = [item.model_dump() for item in meeting_data.analytics.action_items]
                    analytics_orm.key_questions = meeting_data.analytics.key_questions
                    analytics_orm.topics = [t.model_dump() for t in meeting_data.analytics.topics]
                    analytics_orm.keywords = meeting_data.analytics.keywords
                    analytics_orm.speaker_percentage = meeting_data.analytics.speaker_percentage
                else:
                    analytics_orm = Analytics(
                        meeting_id=meeting_data.id,
                        summary=meeting_data.analytics.summary,
                        action_items=[item.model_dump() for item in meeting_data.analytics.action_items],
                        key_questions=meeting_data.analytics.key_questions,
                        topics=[t.model_dump() for t in meeting_data.analytics.topics],
                        keywords=meeting_data.analytics.keywords,
                        speaker_percentage=meeting_data.analytics.speaker_percentage
                    )
                    db.add(analytics_orm)

            # Prepare Transcript Segments
            segments_json = [seg.model_dump() for seg in meeting_data.transcript_segments] if meeting_data.transcript_segments else None

            if existing_meeting:
                existing_meeting.transcript_text = meeting_data.transcript_text
                existing_meeting.transcript_segments = segments_json
                existing_meeting.status = meeting_data.metadata.status
                existing_meeting.duration = meeting_data.metadata.duration
                existing_meeting.provider = meeting_data.metadata.provider
                # Analytics is handled via relationship/foreign key logic above if added to session
            else:
                new_meeting = Meeting(
                    id=meeting_data.id,
                    filename=meeting_data.metadata.filename,
                    duration=meeting_data.metadata.duration,
                    upload_timestamp=meeting_data.metadata.upload_timestamp,
                    status=meeting_data.metadata.status,
                    provider=meeting_data.metadata.provider,
                    transcript_text=meeting_data.transcript_text,
                    transcript_segments=segments_json
                )
                db.add(new_meeting)
                # If analytics existed (unlikely for new meeting but possible safely), it's linked via meeting_id
            
            db.commit()
            db.close()
            
        except Exception as e:
            logger.error(f"DB Save Error: {e}")
            raise e

    async def load_meeting(self, meeting_id: str) -> ProcessedMeeting:
        db = SessionLocal()
        try:
            orm_meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
            if not orm_meeting:
                raise FileNotFoundError(f"Meeting {meeting_id} not found in DB")

            # Reconstruct Metadata
            status = orm_meeting.status or "PROCESSING" 
            if status == "unknown": status = "PROCESSING"
            if not status: status = "PROCESSING"
            
            metadata = MeetingMetadata(
                filename=orm_meeting.filename,
                duration=orm_meeting.duration,
                upload_timestamp=orm_meeting.upload_timestamp,
                status=status,
                provider=orm_meeting.provider
            )
            
            # CRITICAL GUARD: API Contract
            if status != "COMPLETED":
                return ProcessedMeeting(
                    id=orm_meeting.id,
                    metadata=metadata,
                    transcript_text=None,
                    transcript_segments=None,
                    analytics=None
                )
            
            # Reconstruct Analytics (Robust)
            analytics_data = None
            if orm_meeting.analytics:
                try:
                    # Sanitize inputs to ensure they match expected types (list vs None)
                    action_items_raw = orm_meeting.analytics.action_items or []
                    topics_raw = orm_meeting.analytics.topics or []
                    
                    analytics_data = AnalyticsResponse(
                        summary=orm_meeting.analytics.summary or "No summary available.",
                        action_items=action_items_raw,
                        key_questions=orm_meeting.analytics.key_questions or [],
                        topics=topics_raw,
                        keywords=orm_meeting.analytics.keywords or [],
                        speaker_percentage=orm_meeting.analytics.speaker_percentage or {}
                    )
                except Exception as e:
                    logger.error(f"Error parsing analytics for {meeting_id}: {e}")
                    # Fallback to empty if parsing fails
                    analytics_data = AnalyticsResponse(
                        summary="Error parsing analytics data.",
                        action_items=[],
                        key_questions=[],
                        topics=[],
                        keywords=[],
                        speaker_percentage={}
                    )

            # Reconstruct Segments (Only if COMPLETED - flow reaches here)
            segments = []
            if orm_meeting.transcript_segments:
                try:
                    segments = [SpeakerSegment(**seg) for seg in orm_meeting.transcript_segments]
                except Exception as e:
                    logger.error(f"Error parsing segments for {meeting_id}: {e}")
                    segments = []


            return ProcessedMeeting(
                id=orm_meeting.id,
                metadata=metadata,
                transcript_text=orm_meeting.transcript_text,
                transcript_segments=segments,
                analytics=analytics_data
            )
        finally:
            db.close()

storage_service = StorageService()
