from dataclasses import dataclass

import structlog

from src.config import Settings, settings as default_settings
from src.database.repository import TransactionRepository
from src.database.session import db_session
from src.kafka_client.consumer import TransactionConsumer

logger = structlog.get_logger(__name__)


@dataclass
class ReconciliationReport:
    kafka_total_messages: int
    db_transaction_count: int
    db_result_count: int
    missing_in_db: int
    unverified_in_db: int
    duplicate_result_ids: list[str]

    @property
    def is_healthy(self) -> bool:
        return (
            self.missing_in_db == 0
            and self.unverified_in_db == 0
            and len(self.duplicate_result_ids) == 0
        )


class ReconciliationService:
    def __init__(self, cfg: Settings = default_settings):
        self._cfg = cfg

    def run(self) -> ReconciliationReport:
        consumer = TransactionConsumer(self._cfg, group_id="reconciliation-group")
        try:
            consumer.subscribe()
            offsets = consumer.get_topic_end_offsets(self._cfg.kafka_transactions_topic)
            kafka_total = sum(offsets.values())
        finally:
            consumer.close()

        with db_session(self._cfg) as session:
            repo = TransactionRepository(session)
            db_txn_count = repo.count_transactions()
            db_result_count = repo.count_aml_results()
            duplicates = repo.find_duplicate_transaction_ids()

        report = ReconciliationReport(
            kafka_total_messages=kafka_total,
            db_transaction_count=db_txn_count,
            db_result_count=db_result_count,
            missing_in_db=max(0, kafka_total - db_txn_count),
            unverified_in_db=max(0, db_txn_count - db_result_count),
            duplicate_result_ids=duplicates,
        )

        if not report.is_healthy:
            logger.warning("reconciliation_failed", report=str(report))
        else:
            logger.info("reconciliation_passed", report=str(report))

        return report
