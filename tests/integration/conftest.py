import pytest
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from testcontainers.kafka import KafkaContainer
from testcontainers.postgres import PostgresContainer

from sqlalchemy import text

from src.config import Settings


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:17-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def db_engine(postgres_container):
    url = postgres_container.get_connection_url()
    engine = create_engine(url)

    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    alembic_command.upgrade(cfg, "head")

    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_tables(db_engine):
    """Truncate all data before each integration test for full isolation."""
    with db_engine.connect() as conn:
        conn.execute(text(
            "TRUNCATE transactions, aml_results, blacklisted_accounts RESTART IDENTITY CASCADE"
        ))
        conn.commit()
    yield


@pytest.fixture
def db_session(db_engine):
    """Per-test session."""
    session = Session(db_engine)
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="session")
def integration_settings(postgres_container, db_engine):
    host = postgres_container.get_container_host_ip()
    port = postgres_container.get_exposed_port(5432)
    return Settings(
        postgres_host=host,
        postgres_port=int(port),
        postgres_db="test",
        postgres_user="test",
        postgres_password="test",
        kafka_bootstrap_servers="localhost:9092",
        alert_log_only=True,
    )


@pytest.fixture(scope="session")
def kafka_container():
    with KafkaContainer() as kafka:
        yield kafka


@pytest.fixture(scope="session")
def kafka_bootstrap(kafka_container):
    return kafka_container.get_bootstrap_server()


@pytest.fixture(scope="session")
def kafka_settings(postgres_container, kafka_container, db_engine):
    pg_host = postgres_container.get_container_host_ip()
    pg_port = postgres_container.get_exposed_port(5432)
    return Settings(
        postgres_host=pg_host,
        postgres_port=int(pg_port),
        postgres_db="test",
        postgres_user="test",
        postgres_password="test",
        kafka_bootstrap_servers=kafka_container.get_bootstrap_server(),
        alert_log_only=True,
    )
