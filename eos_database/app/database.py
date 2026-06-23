"""
Database configuration and session management.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pydantic_settings import BaseSettings
from typing import Generator


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    database_url: str = "postgresql://user:password@localhost:5432/eos_db"

    class Config:
        env_file = ".env"
        extra = "ignore"  # .env also has API_HOST/API_PORT/etc for main.py


settings = Settings()

# Create engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # Verify connections before using
    echo=False  # Set to True for SQL logging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator:
    """
    Dependency function to get database session.
    
    Usage in FastAPI:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database - create all tables"""
    from app.models import Base
    Base.metadata.create_all(bind=engine)
