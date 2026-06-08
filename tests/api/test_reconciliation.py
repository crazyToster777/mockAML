from unittest.mock import patch

import allure
import pytest

from src.aml.reconciliation import ReconciliationReport


@allure.epic("REST API")
@allure.feature("Reconciliation Endpoint")
@pytest.mark.api
class TestReconciliationEndpoint:
    @allure.story("Response shape")
    @allure.title("GET /api/reconciliation returns all required fields")
    def test_response_fields(self, client):
        mock_report = ReconciliationReport(
            kafka_total_messages=0,
            db_transaction_count=0,
            db_result_count=0,
            missing_in_db=0,
            unverified_in_db=0,
            duplicate_result_ids=[],
        )
        with patch("src.api.routers.reconciliation.ReconciliationService") as MockSvc:
            MockSvc.return_value.run.return_value = mock_report
            resp = client.get("/api/reconciliation")

        assert resp.status_code == 200
        data = resp.json()
        for field in (
            "is_healthy", "kafka_total_messages", "db_transaction_count",
            "db_result_count", "missing_in_db", "unverified_in_db", "duplicate_result_ids"
        ):
            assert field in data, f"Missing field: {field}"

    @allure.story("Healthy state")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("is_healthy=True when all counts match")
    def test_healthy_response(self, client):
        mock_report = ReconciliationReport(
            kafka_total_messages=5,
            db_transaction_count=5,
            db_result_count=5,
            missing_in_db=0,
            unverified_in_db=0,
            duplicate_result_ids=[],
        )
        with patch("src.api.routers.reconciliation.ReconciliationService") as MockSvc:
            MockSvc.return_value.run.return_value = mock_report
            resp = client.get("/api/reconciliation")

        assert resp.json()["is_healthy"] is True

    @allure.story("Unhealthy state")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("is_healthy=False and missing_in_db populated when Kafka ahead of DB")
    def test_unhealthy_response(self, client):
        mock_report = ReconciliationReport(
            kafka_total_messages=10,
            db_transaction_count=7,
            db_result_count=7,
            missing_in_db=3,
            unverified_in_db=0,
            duplicate_result_ids=[],
        )
        with patch("src.api.routers.reconciliation.ReconciliationService") as MockSvc:
            MockSvc.return_value.run.return_value = mock_report
            resp = client.get("/api/reconciliation")

        data = resp.json()
        assert data["is_healthy"] is False
        assert data["missing_in_db"] == 3
