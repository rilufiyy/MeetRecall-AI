import os
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    APP_NAME: str = "MeetRecall-Backend"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"
    
    # API Keys
    OPENAI_API_KEY: str = ""
    ASSEMBLY_API_KEY: str = "" 
    HUGGINGFACE_TOKEN: str = "" 

    # Database (Postgres)
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASS: str = "postgres"
    DB_NAME: str = "meetrecall_db"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    STORAGE_DIR: Path = BASE_DIR / "storage"

    # Pydantic v2 Config
    model_config = {
        "env_file": ".env",
        "extra": "ignore"
    }

def setup_directories(settings: Settings):
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)

settings = Settings()
setup_directories(settings)
