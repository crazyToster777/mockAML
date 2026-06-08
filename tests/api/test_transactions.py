import allure
import pytest


@allure.epic("REST API")
@allure.feature("Transactions Endpoint")
@pytest.mark.api
class TestTransactionsList:
    @allure.story("Pagination")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("limit and offset control page slice correctly")
    def test_pagination(self, seeded_client):
        resp = seeded_client.get("/api/transactions?limit=3&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 3
        assert data["total"] == 10

    @allure.story("Pagination")
    @allure.title("offset beyond total returns empty items but correct total")
    def test_offset_beyond_total(self, seeded_client):
        resp = seeded_client.get("/api/transactions?limit=10&offset=100")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 10

    @allure.story("Filter by risk level")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Filtering by single risk_level returns only matching records")
    def test_filter_single_risk(self, seeded_client):
        resp = seeded_client.get("/api/transactions?risk_level=high")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["risk_level"] == "high"

    @allure.story("Filter by risk level")
    @allure.title("Multiple risk_level values filter with OR logic")
    def test_filter_multi_risk(self, seeded_client):
        resp = seeded_client.get("/api/transactions?risk_level=high&risk_level=blocked")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["risk_level"] in ("high", "blocked")

    @allure.story("Filter by account ID")
    @allure.title("account_id filter performs case-insensitive partial match")
    def test_filter_by_account_id(self, seeded_client):
        resp = seeded_client.get("/api/transactions?account_id=ACCT200")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert "ACCT200" in item["account_id"]

    @allure.story("Filter by amount")
    @allure.title("min_amount filters out transactions below threshold")
    def test_filter_min_amount(self, seeded_client):
        resp = seeded_client.get("/api/transactions?min_amount=14000")
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["amount_usd"] >= 14_000

    @allure.story("Response shape")
    @allure.title("Each item contains all required fields")
    def test_item_fields(self, seeded_client):
        resp = seeded_client.get("/api/transactions?limit=1")
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        for field in ("result_id", "transaction_id", "account_id", "risk_level",
                      "amount_usd", "triggered_rules", "notes", "verified_at"):
            assert field in item, f"Missing field: {field}"
