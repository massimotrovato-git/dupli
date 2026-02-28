import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

def _dsn() -> str:
    user = os.getenv("POSTGRES_USER")
    pwd = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST", "postgres")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB")
    return f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{db}"

engine = create_engine(_dsn(), pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
