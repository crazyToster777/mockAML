import allure
import pytest
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlalchemy import inspect


@allure.epic("Data Layer")
@allure.feature("Alembic Migrations")
@pytest.mark.integration
class TestMigrations:
    @allure.story("Upgrade head")
    @allure.severity(allure.severity_level.BLOCKER)
    @allure.title("alembic upgrade head runs without errors")
    def test_upgrade_head(self, postgres_container):
        url = postgres_container.get_connection_url()
        cfg = AlembicConfig("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", url)
        # db_engine fixture already ran upgrade; running again must be idempotent
        alembic_command.upgrade(cfg, "head")

    @allure.story("Required tables")
    @allure.severity(allure.severity_level.BLOCKER)
    @allure.title("All required tables exist after migration")
    def test_tables_exist(self, db_engine):
        inspector = inspect(db_engine)
        tables = inspector.get_table_names()
        with allure.step("Check transactions table"):
            assert "transactions" in tables
        with allure.step("Check aml_results table"):
            assert "aml_results" in tables
        with allure.step("Check blacklisted_accounts table"):
            assert "blacklisted_accounts" in tables

    @allure.story("Column presence")
    @allure.title("transactions table has required columns")
    def test_transactions_columns(self, db_engine):
        inspector = inspect(db_engine)
        cols = {c["name"] for c in inspector.get_columns("transactions")}
        for required in ("transaction_id", "account_id", "amount_usd", "transaction_type", "kafka_offset"):
            assert required in cols, f"Missing column: {required}"

    @allure.story("Column presence")
    @allure.title("aml_results table has required columns")
    def test_aml_results_columns(self, db_engine):
        inspector = inspect(db_engine)
        cols = {c["name"] for c in inspector.get_columns("aml_results")}
        for required in ("result_id", "transaction_id", "account_id", "risk_level", "verified_at"):
            assert required in cols, f"Missing column: {required}"
