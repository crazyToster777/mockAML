import allure
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.aml.verifier import AMLVerifier
from src.database.models import AMLResultRecord, TransactionRecord
from src.models.transaction import RiskLevel
from tests.factories import make_transaction


@allure.epic("AML Rules Engine")
@allure.feature("AML Verifier")
@pytest.mark.integration
class TestAMLVerifier:
    def _read_result(self, db_engine, transaction_id: str) -> AMLResultRecord | None:
        """Read committed result using a fresh session."""
        with Session(db_engine) as s:
            return s.execute(
                select(AMLResultRecord).where(AMLResultRecord.transaction_id == transaction_id)
            ).scalars().first()

    def _read_transaction(self, db_engine, transaction_id: str) -> TransactionRecord | None:
        with Session(db_engine) as s:
            return s.execute(
                select(TransactionRecord).where(TransactionRecord.transaction_id == transaction_id)
            ).scalars().first()

    @allure.story("Clean transaction")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("500 USD transaction → LOW risk saved to DB")
    def test_process_clean_transaction(self, db_engine, integration_settings):
        verifier = AMLVerifier(cfg=integration_settings)
        txn = make_transaction(amount_usd=500.0)
        verifier.process_transaction(txn)

        result = self._read_result(db_engine, txn.transaction_id)
        assert result is not None
        assert result.risk_level == RiskLevel.LOW.value

    @allure.story("High amount")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("15,000 USD transaction → HIGH risk saved to DB")
    def test_process_high_amount(self, db_engine, integration_settings):
        verifier = AMLVerifier(cfg=integration_settings)
        txn = make_transaction(amount_usd=15_000.0)
        verifier.process_transaction(txn)

        result = self._read_result(db_engine, txn.transaction_id)
        assert result is not None
        assert result.risk_level == RiskLevel.HIGH.value
        assert "amount_threshold" in result.triggered_rules

    @allure.story("Blacklisted account")
    @allure.severity(allure.severity_level.BLOCKER)
    @allure.title("Sanctioned counterparty → BLOCKED risk saved to DB")
    def test_process_blacklisted(self, db_engine, integration_settings):
        verifier = AMLVerifier(cfg=integration_settings)
        txn = make_transaction(counterparty_account_id="SANCTIONED001")
        verifier.process_transaction(txn)

        result = self._read_result(db_engine, txn.transaction_id)
        assert result is not None
        assert result.risk_level == RiskLevel.BLOCKED.value

    @allure.story("Dual record persistence")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("process_transaction saves records to both transactions and aml_results")
    def test_saves_both_records(self, db_engine, integration_settings):
        verifier = AMLVerifier(cfg=integration_settings)
        txn = make_transaction(amount_usd=1_000.0)
        verifier.process_transaction(txn)

        assert self._read_transaction(db_engine, txn.transaction_id) is not None, "Missing transactions record"
        assert self._read_result(db_engine, txn.transaction_id) is not None, "Missing aml_results record"
