from fastapi import APIRouter
from src.api.endpoints import upload, analytics, chat, transcription

api_router = APIRouter()

api_router.include_router(upload.router, tags=["Meeting Operations"])
api_router.include_router(transcription.router, tags=["Transcription"])
api_router.include_router(analytics.router, tags=["Analytics"])
api_router.include_router(chat.router, tags=["AI Chat"])