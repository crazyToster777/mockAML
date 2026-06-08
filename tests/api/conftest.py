import pytest
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer

import src.database.session as db_session_module
from src.api.main import app
from src.database.repository import TransactionRepository
from src.models.transaction import RiskLevel
from tests.factories import make_aml_result, make_transaction


@pytest.fixture(scope="session")
def api_postgres():
    with PostgresContainer("postgres:17-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def api_engine(api_postgres):
    url = api_postgres.get_connection_url()
    engine = create_engine(url)
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    alembic_command.upgrade(cfg, "head")
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_api_tables(api_engine):
    """Truncate all data before each API test."""
    with api_engine.connect() as conn:
        conn.execute(text(
            "TRUNCATE transactions, aml_results, blacklisted_accounts RESTART IDENTITY CASCADE"
        ))
        conn.commit()
    yield


@pytest.fixture(autouse=True)
def patch_session_factory(api_engine):
    """Point the global session factory to the test DB for all API tests."""
    original = db_session_module._SessionFactory
    db_session_module._SessionFactory = sessionmaker(bind=api_engine, expire_on_commit=False)
    yield
    db_session_module._SessionFactory = original


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def seed_db(api_engine):
    """Seed 7 LOW, 2 HIGH, 1 BLOCKED records."""
    with Session(api_engine) as session:
        repo = TransactionRepository(session)
        for i in range(7):
            txn = make_transaction(account_id=f"ACCT10{i:04d}", amount_usd=200.0 + i * 50)
            repo.save_transaction(txn)
            repo.save_aml_result(make_aml_result(transaction=txn, risk_level=RiskLevel.LOW))
        for i in range(2):
            txn = make_transaction(account_id=f"ACCT20{i:04d}", amount_usd=15_000.0)
            repo.save_transaction(txn)
            repo.save_aml_result(make_aml_result(
                transaction=txn, risk_level=RiskLevel.HIGH,
                triggered_rules=["amount_threshold"],
            ))
        txn = make_transaction(account_id="ACCT300001", counterparty_account_id="SANCTIONED001")
        repo.save_transaction(txn)
        repo.save_aml_result(make_aml_result(
            transaction=txn, risk_level=RiskLevel.BLOCKED, triggered_rules=["blacklist"],
        ))
        session.commit()


@pytest.fixture
def seeded_client(client, seed_db):
    return client
