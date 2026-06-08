import allure
import pytest


@allure.epic("REST API")
@allure.feature("Analytics Endpoints")
@pytest.mark.api
class TestAnalytics:
    @allure.story("Risk distribution")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("risk-distribution returns correct counts per level")
    def test_risk_distribution_counts(self, seeded_client):
        resp = seeded_client.get("/api/analytics/risk-distribution")
        assert resp.status_code == 200
        data = {item["risk_level"]: item["count"] for item in resp.json()}
        assert data.get("low") == 7
        assert data.get("high") == 2
        assert data.get("blocked") == 1

    @allure.story("Volume over time")
    @allure.title("volume-over-time items contain all risk-level keys")
    def test_volume_over_time_keys(self, seeded_client):
        resp = seeded_client.get("/api/analytics/volume-over-time")
        assert resp.status_code == 200
        items = resp.json()
        if items:
            for item in items:
                for key in ("hour", "low", "medium", "high", "blocked"):
                    assert key in item, f"Missing key: {key}"

    @allure.story("Triggered rules")
    @allure.title("triggered-rules returns rule counts in descending order")
    def test_triggered_rules_sorted(self, seeded_client):
        resp = seeded_client.get("/api/analytics/triggered-rules")
        assert resp.status_code == 200
        rules = resp.json()
        if len(rules) > 1:
            counts = [r["count"] for r in rules]
            assert counts == sorted(counts, reverse=True)

    @allure.story("Triggered rules")
    @allure.title("triggered-rules contains the rules that were actually fired")
    def test_triggered_rules_content(self, seeded_client):
        resp = seeded_client.get("/api/analytics/triggered-rules")
        assert resp.status_code == 200
        rule_names = {r["rule"] for r in resp.json()}
        assert "amount_threshold" in rule_names
        assert "blacklist" in rule_names

    @allure.story("Cumulative suspicious")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("cumulative-suspicious values are monotonically non-decreasing")
    def test_cumulative_suspicious_monotonic(self, seeded_client):
        resp = seeded_client.get("/api/analytics/cumulative-suspicious")
        assert resp.status_code == 200
        values = [item["cumulative"] for item in resp.json()]
        for i in range(1, len(values)):
            assert values[i] >= values[i - 1], "Cumulative values must be non-decreasing"
