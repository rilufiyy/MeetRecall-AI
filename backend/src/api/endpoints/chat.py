from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.services.rag_service import rag_service

router = APIRouter()

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    answer: str

@router.post("/ask/{meeting_id}", response_model=ChatResponse)
async def ask_meeting(meeting_id: str, request: ChatRequest):
    try:
        answer = rag_service.chat(meeting_id, request.query)
        return ChatResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
