import logging
from collections.abc import Generator
from contextlib import contextmanager

import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from tenacity import before_log, retry, stop_after_attempt, wait_exponential

from src.config import Settings, settings as default_settings

logger = structlog.get_logger(__name__)
_stdlib_logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(10),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    before=before_log(_stdlib_logger, logging.WARNING),
    reraise=True,
)
def create_session_factory(cfg: Settings = default_settings) -> sessionmaker[Session]:
    engine = create_engine(
        cfg.postgres_dsn,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        echo=False,
    )
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return sessionmaker(bind=engine, expire_on_commit=False)


_SessionFactory: sessionmaker[Session] | None = None


def get_session_factory(cfg: Settings = default_settings) -> sessionmaker[Session]:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = create_session_factory(cfg)
    return _SessionFactory


@contextmanager
def db_session(cfg: Settings = default_settings) -> Generator[Session, None, None]:
    factory = get_session_factory(cfg)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
