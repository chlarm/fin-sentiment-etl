from __future__ import annotations
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from src.config import Settings

def get_engine(settings: Settings) -> Engine:
    return create_engine(settings.sqlalchemy_url, pool_pre_ping=True)
