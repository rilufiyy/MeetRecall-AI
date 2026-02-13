from fastapi import APIRouter, BackgroundTasks, HTTPException
from src.services.pipeline_service import pipeline_service
from src.services.storage_service import storage_service
from src.utils.logging import setup_logger
from src.core.config import settings
from pathlib import Path

router = APIRouter()
logger = setup_logger(__name__)

@router.post("/transcribe/{meeting_id}")
async def transcribe_meeting(
    meeting_id: str,
    background_tasks: BackgroundTasks,
    provider: str = "assemblyai"
):
    """
    Manually triggers transcription for a meeting.
    """
    try:
        meeting = await storage_service.load_meeting(meeting_id)
        
        # Try to find the file
        file_path = None
        candidates = [
            f"{meeting_id}_{meeting.metadata.filename}",
            meeting.metadata.filename
        ]
        
        for name in candidates:
            p = settings.UPLOAD_DIR / name
            if p.exists():
                file_path = p
                break
        
        if not file_path:
             raise HTTPException(status_code=404, detail="Source file not found")

        background_tasks.add_task(
            pipeline_service.process_meeting, 
            file_path, 
            meeting.metadata.filename, 
            meeting_id, 
            provider
        )

        return {"message": "Transcription started", "meeting_id": meeting_id, "provider": provider}

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Meeting not found")
    except Exception as e:
        logger.error(f"Transcribe trigger failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
