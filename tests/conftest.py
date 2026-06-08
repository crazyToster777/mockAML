import pytest
from src.config import Settings


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Settings with safe defaults for tests — no real infra needed for unit tests."""
    return Settings(
        kafka_bootstrap_servers="localhost:9092",
        postgres_host="localhost",
        postgres_db="aml_test",
        postgres_user="aml_user",
        postgres_password="aml_password",
        amount_threshold_usd=10_000.0,
        velocity_max_transactions=10,
        velocity_window_seconds=3600,
        alert_log_only=True,
    )
