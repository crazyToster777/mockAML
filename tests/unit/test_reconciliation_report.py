import allure
import pytest

from src.aml.reconciliation import ReconciliationReport


def _report(**kwargs) -> ReconciliationReport:
    defaults = dict(
        kafka_total_messages=0,
        db_transaction_count=0,
        db_result_count=0,
        missing_in_db=0,
        unverified_in_db=0,
        duplicate_result_ids=[],
    )
    return ReconciliationReport(**{**defaults, **kwargs})


@allure.epic("Reconciliation")
@allure.feature("Health Check Logic")
@pytest.mark.unit
class TestReconciliationReportHealth:
    @allure.story("Healthy state")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("All-zero report is healthy")
    def test_healthy_report(self):
        assert _report().is_healthy is True

    @allure.story("Missing records")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("missing_in_db > 0 → not healthy")
    def test_missing_in_db(self):
        assert _report(missing_in_db=1).is_healthy is False

    @allure.story("Unverified records")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("unverified_in_db > 0 → not healthy")
    def test_unverified_in_db(self):
        assert _report(unverified_in_db=1).is_healthy is False

    @allure.story("Duplicate IDs")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Non-empty duplicate_result_ids → not healthy")
    def test_duplicate_ids(self):
        assert _report(duplicate_result_ids=["abc-123"]).is_healthy is False

    @allure.story("Multiple issues")
    @allure.title("Multiple issues still produce a single is_healthy=False")
    def test_multiple_issues(self):
        report = _report(
            missing_in_db=5,
            unverified_in_db=2,
            duplicate_result_ids=["x", "y"],
        )
        assert report.is_healthy is False

    @allure.story("Counts preserved")
    @allure.title("Report stores kafka and DB counts as provided")
    def test_counts_stored(self):
        report = _report(
            kafka_total_messages=100,
            db_transaction_count=95,
            db_result_count=90,
        )
        assert report.kafka_total_messages == 100
        assert report.db_transaction_count == 95
        assert report.db_result_count == 90
