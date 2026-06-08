from unittest.mock import MagicMock, patch

import allure
import pytest


@allure.epic("REST API")
@allure.feature("Produce Endpoints")
@pytest.mark.api
class TestProduceBulk:
    @allure.story("Bulk produce")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("POST /api/produce/bulk returns correct produced count")
    def test_bulk_returns_count(self, client):
        mock_producer = MagicMock()
        with patch("src.api.routers.produce._get_producer", return_value=mock_producer):
            resp = client.post("/api/produce/bulk", json={"count": 5, "include_suspicious": False})
        assert resp.status_code == 200
        assert resp.json()["produced"] == 5

    @allure.story("Bulk produce")
    @allure.title("Bulk produce calls send_transaction N times")
    def test_bulk_calls_producer_n_times(self, client):
        mock_producer = MagicMock()
        with patch("src.api.routers.produce._get_producer", return_value=mock_producer):
            client.post("/api/produce/bulk", json={"count": 3, "include_suspicious": False})
        assert mock_producer.send_transaction.call_count == 3

    @allure.story("Bulk validation")
    @allure.title("count=0 returns 422 validation error")
    def test_bulk_count_zero_rejected(self, client):
        resp = client.post("/api/produce/bulk", json={"count": 0})
        assert resp.status_code == 422

    @allure.story("Bulk validation")
    @allure.title("count > 100 returns 422 validation error")
    def test_bulk_count_over_limit_rejected(self, client):
        resp = client.post("/api/produce/bulk", json={"count": 101})
        assert resp.status_code == 422


@allure.epic("REST API")
@allure.feature("Produce Endpoints")
@pytest.mark.api
class TestProduceSingle:
    def _payload(self, **kwargs):
        defaults = {
            "account_id": "ACCT100001",
            "counterparty_account_id": "ACCT200001",
            "amount_usd": 500.0,
            "transaction_type": "wire_transfer",
        }
        return {**defaults, **kwargs}

    @allure.story("Single produce")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Clean transaction produces with empty warnings list")
    def test_single_clean_no_warnings(self, client):
        mock_producer = MagicMock()
        with patch("src.api.routers.produce._get_producer", return_value=mock_producer):
            resp = client.post("/api/produce/single", json=self._payload())
        assert resp.status_code == 200
        data = resp.json()
        assert "transaction_id" in data
        assert data["warnings"] == []

    @allure.story("Warnings")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("amount >= 10,000 produces amount_threshold warning")
    def test_high_amount_warning(self, client):
        mock_producer = MagicMock()
        with patch("src.api.routers.produce._get_producer", return_value=mock_producer):
            resp = client.post("/api/produce/single", json=self._payload(amount_usd=12_000.0))
        assert resp.status_code == 200
        warnings = resp.json()["warnings"]
        assert any("amount_threshold" in w for w in warnings)

    @allure.story("Warnings")
    @allure.severity(allure.severity_level.BLOCKER)
    @allure.title("Blacklisted counterparty produces BLOCKED warning")
    def test_blacklisted_counterparty_warning(self, client):
        mock_producer = MagicMock()
        with patch("src.api.routers.produce._get_producer", return_value=mock_producer):
            resp = client.post(
                "/api/produce/single",
                json=self._payload(counterparty_account_id="SANCTIONED001"),
            )
        assert resp.status_code == 200
        warnings = resp.json()["warnings"]
        assert any("BLOCKED" in w for w in warnings)

    @allure.story("Validation")
    @allure.title("account_id shorter than 6 chars returns 422")
    def test_short_account_id_rejected(self, client):
        resp = client.post("/api/produce/single", json=self._payload(account_id="A1"))
        assert resp.status_code == 422

    @allure.story("Validation")
    @allure.title("Invalid transaction_type returns 422")
    def test_invalid_txn_type_rejected(self, client):
        resp = client.post("/api/produce/single", json=self._payload(transaction_type="invalid"))
        assert resp.status_code == 422
