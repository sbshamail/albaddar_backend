from contextlib import contextmanager
from sqlmodel import (
    Session,
    create_engine,
)

from src.config import DATABASE_URL


engine = create_engine(
    DATABASE_URL,
    echo=True,
    pool_pre_ping=True,  # checks if connection is alive
    pool_recycle=1800,  # refresh stale connections
)


def get_session():
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
