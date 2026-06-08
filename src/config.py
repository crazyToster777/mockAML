from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Docker secrets монтируются как файлы в /run/secrets/<name>
# pydantic-settings читает их автоматически если secrets_dir задан
_SECRETS_DIR = Path("/run/secrets") if Path("/run/secrets").exists() else None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",          # локальная разработка
        env_file_encoding="utf-8",
        secrets_dir=_SECRETS_DIR,  # Docker / Kubernetes secrets в проде
        extra="ignore",
    )

    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_transactions_topic: str = "aml.transactions"
    kafka_results_topic: str = "aml.results"
    kafka_consumer_group: str = "aml-verifier-group"
    kafka_auto_offset_reset: str = "earliest"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "aml_db"
    postgres_user: str = "aml_user"
    postgres_password: str = "aml_password"  # в проде — переопределяется из /run/secrets/postgres_password

    amount_threshold_usd: float = 10_000.0
    velocity_max_transactions: int = 10
    velocity_window_seconds: int = 3600

    alert_webhook_url: str = "http://localhost:8888/alerts"
    alert_log_only: bool = True

    schema_registry_url: str = ""  # пусто = Schema Registry отключён, используется JSON

    health_port: int = 8080

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
