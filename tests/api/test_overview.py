import allure
import pytest


@allure.epic("REST API")
@allure.feature("Overview Endpoints")
@pytest.mark.api
class TestOverviewStats:
    @allure.story("Empty DB")
    @allure.title("Stats return all zeros when DB is empty")
    def test_stats_empty_db(self, client):
        resp = client.get("/api/overview/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_transactions"] == 0
        assert data["verified"] == 0
        assert data["suspicious"] == 0
        assert data["detection_rate"] == 0.0

    @allure.story("With data")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Stats reflect seeded data correctly")
    def test_stats_with_data(self, seeded_client):
        resp = seeded_client.get("/api/overview/stats")
        assert resp.status_code == 200
        data = resp.json()

        with allure.step("10 total transactions"):
            assert data["total_transactions"] == 10
        with allure.step("10 verified"):
            assert data["verified"] == 10
        with allure.step("3 suspicious (2 HIGH + 1 BLOCKED)"):
            assert data["suspicious"] == 3
        with allure.step("Detection rate = 30.0%"):
            assert data["detection_rate"] == 30.0


@allure.epic("REST API")
@allure.feature("Overview Endpoints")
@pytest.mark.api
class TestRecentAlerts:
    @allure.story("Only suspicious returned")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("recent-alerts returns only HIGH and BLOCKED transactions")
    def test_returns_only_suspicious(self, seeded_client):
        resp = seeded_client.get("/api/overview/recent-alerts?limit=20")
        assert resp.status_code == 200
        alerts = resp.json()
        assert len(alerts) == 3
        for a in alerts:
            assert a["risk_level"] in ("high", "blocked")

    @allure.story("Limit parameter")
    @allure.title("limit parameter caps the number of alerts returned")
    def test_limit_respected(self, seeded_client):
        resp = seeded_client.get("/api/overview/recent-alerts?limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) <= 2

    @allure.story("Response shape")
    @allure.title("Each alert contains required fields")
    def test_alert_fields(self, seeded_client):
        resp = seeded_client.get("/api/overview/recent-alerts")
        assert resp.status_code == 200
        for alert in resp.json():
            assert "transaction_id" in alert
            assert "account_id" in alert
            assert "amount_usd" in alert
            assert "triggered_rules" in alert
