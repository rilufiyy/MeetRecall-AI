from fastapi import APIRouter, UploadFile, File, BackgroundTasks, Form, HTTPException
from src.services.pipeline_service import pipeline_service
from src.utils.logging import setup_logger
import uuid
import shutil
from pathlib import Path
from src.core.config import settings

router = APIRouter()
logger = setup_logger(__name__)

@router.post("/upload", status_code=202)
async def upload_meeting(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    provider: str = Form("assemblyai"),
    model: str = Form("universal-3-pro")
):
    """
    Uploads a meeting recording and triggers the processing pipeline.
    Returns immediately with a meeting ID.
    """
    meeting_id = str(uuid.uuid4())
    filename = file.filename

    # Save file temporarily
    temp_path = settings.UPLOAD_DIR / f"{meeting_id}_{filename}"
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        raise HTTPException(status_code=500, detail="File upload failed")

    # Trigger pipeline with selected provider and model
    logger.info(f"UPLOAD ENDPOINT RECEIVED: provider='{provider}', model='{model}'")
    print(f"DEBUG_PRINT: UPLOAD ENDPOINT RECEIVED: provider='{provider}', model='{model}'", flush=True)
    background_tasks.add_task(pipeline_service.process_meeting, temp_path, filename, meeting_id, provider, model)

    return {
        "message": "Upload successful. Processing started.",
        "meeting_id": meeting_id,
        "status": "PROCESSING",
        "provider": provider,
        "model": model
    }
