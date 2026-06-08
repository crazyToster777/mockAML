from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import Settings, settings as default_settings


def create_session_factory(cfg: Settings = default_settings) -> sessionmaker[Session]:
    engine = create_engine(
        cfg.postgres_dsn,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        echo=False,
    )
    # таблицы создаются только через: alembic upgrade head
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
