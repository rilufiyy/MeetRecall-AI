from fastapi import APIRouter, HTTPException, Depends
from src.services.storage_service import storage_service
from src.models.schemas import MeetingResponse

router = APIRouter()

@router.get("/analysis/{meeting_id}", response_model=MeetingResponse)
async def get_analysis(meeting_id: str):
    try:
        meeting = await storage_service.load_meeting(meeting_id)
        
        # Guard: Strict API Contract
        status = meeting.metadata.status
        
        if status == "FAILED":
            # Requirement: Return 200 with failure info (or 500 if strict, but user asked for 200 valid response)
            # We return the meeting object, which has status=FAILED. 
            # The frontend should handle this.
            return meeting
            
        if status != "COMPLETED":
             raise HTTPException(
                 status_code=409, 
                 detail=f"Analysis not ready. Current status: {status}"
             )
             
        return meeting
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Meeting not found")
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/transcript/{meeting_id}")
async def get_transcript(meeting_id: str):
    try:
        meeting = await storage_service.load_meeting(meeting_id)
        return {
            "meeting_id": meeting_id,
            "transcript": meeting.transcript_text,
            "segments": meeting.transcript_segments
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Meeting not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/meetings", response_model=list[MeetingResponse])
async def list_meetings():
    from src.core.database import SessionLocal
    from src.models.orm import Meeting
    
    db = SessionLocal()
    try:
        meetings = db.query(Meeting).order_by(Meeting.upload_timestamp.desc()).all()
        results = []
        for m in meetings:
            results.append(await storage_service.load_meeting(m.id))
        return results
    finally:
        db.close()