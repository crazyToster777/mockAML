from datetime import datetime, timedelta, timezone

import allure
import pytest

from src.database.repository import TransactionRepository
from src.models.transaction import RiskLevel
from tests.factories import make_aml_result, make_transaction


@allure.epic("Data Layer")
@allure.feature("Transaction Repository")
@pytest.mark.integration
class TestTransactionRepository:
    @allure.story("Save and retrieve")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Saved transaction is retrievable via get_recent_transactions")
    def test_save_and_retrieve_transaction(self, db_session):
        repo = TransactionRepository(db_session)
        txn = make_transaction()
        repo.save_transaction(txn)
        db_session.commit()

        recent = repo.get_recent_transactions(txn.account_id, window_seconds=3600)
        assert any(r.transaction_id == txn.transaction_id for r in recent)

    @allure.story("Time window filter")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Transactions outside the time window are not returned")
    def test_get_recent_transactions_window(self, db_session):
        repo = TransactionRepository(db_session)
        old_time = datetime.now(timezone.utc) - timedelta(hours=3)
        txn = make_transaction(timestamp=old_time)
        repo.save_transaction(txn)
        db_session.commit()

        recent = repo.get_recent_transactions(txn.account_id, window_seconds=3600)
        assert all(r.transaction_id != txn.transaction_id for r in recent)

    @allure.story("AML result persistence")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Saved AML result increments count_aml_results")
    def test_save_aml_result(self, db_session):
        repo = TransactionRepository(db_session)
        txn = make_transaction()
        result = make_aml_result(transaction=txn, risk_level=RiskLevel.HIGH)
        repo.save_transaction(txn)
        repo.save_aml_result(result)
        db_session.commit()

        assert repo.count_aml_results() >= 1

    @allure.story("Idempotency")
    @allure.title("Saving the same transaction twice does not create duplicates")
    def test_merge_idempotent(self, db_session):
        repo = TransactionRepository(db_session)
        txn = make_transaction()
        repo.save_transaction(txn)
        db_session.commit()
        count_before = repo.count_transactions()

        repo.save_transaction(txn)
        db_session.commit()

        assert repo.count_transactions() == count_before

    @allure.story("Count")
    @allure.title("count_transactions returns the correct number of saved transactions")
    def test_count_transactions(self, db_session):
        repo = TransactionRepository(db_session)
        before = repo.count_transactions()

        for _ in range(5):
            repo.save_transaction(make_transaction())
        db_session.commit()

        assert repo.count_transactions() == before + 5

    @allure.story("Duplicate detection")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("find_duplicate_transaction_ids detects same transaction_id with two results")
    def test_find_duplicate_transaction_ids(self, db_session):
        repo = TransactionRepository(db_session)
        txn = make_transaction()
        repo.save_transaction(txn)
        repo.save_aml_result(make_aml_result(transaction=txn))
        repo.save_aml_result(make_aml_result(transaction=txn))
        db_session.commit()

        duplicates = repo.find_duplicate_transaction_ids()
        assert txn.transaction_id in duplicates
