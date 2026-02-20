from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.core.database import engine, Base
from src.api.routes import api_router
from src.utils.wait_for_db import wait_for_db

import src.models  

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    description="Backend for MeetRecall AI Meeting Intelligence Platform",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    wait_for_db()

    # Create tables (idempotent)
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
            print("INFO:   pgvector extension enabled.")
    except Exception as e:
        print(f"WARNING: Failed to enable pgvector: {e}")

    Base.metadata.create_all(bind=engine)


@app.get("/")
async def root():
    return {
        "message": "Welcome to MeetRecall API",
        "docs": "/docs",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)


app.include_router(api_router, prefix=settings.API_PREFIX)
