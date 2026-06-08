import signal
import structlog

from src.aml.alert_service import AlertService
from src.aml.rules import RuleEngine
from src.config import Settings, settings as default_settings
from src.database.repository import TransactionRepository
from src.database.session import db_session
from src.kafka_client.consumer import TransactionConsumer
from src.models.transaction import Transaction

logger = structlog.get_logger(__name__)


class AMLVerifier:
    def __init__(self, cfg: Settings = default_settings):
        self._cfg = cfg
        self._rule_engine = RuleEngine.default(cfg)
        self._alert_service = AlertService(cfg)
        self._running = False

    def _handle_shutdown(self, signum, _frame) -> None:
        sig_name = signal.Signals(signum).name
        logger.info("shutdown_signal_received", signal=sig_name)
        self._running = False

    def process_transaction(
        self,
        transaction: Transaction,
        kafka_offset: int | None = None,
        kafka_partition: int | None = None,
    ) -> None:
        with db_session(self._cfg) as session:
                repo = TransactionRepository(session)
                repo.save_transaction(transaction, kafka_offset=kafka_offset, kafka_partition=kafka_partition)

                recent = repo.get_recent_transactions(
                    transaction.account_id,
                    window_seconds=self._cfg.velocity_window_seconds,
                )

                result = self._rule_engine.evaluate(transaction, recent)
                repo.save_aml_result(result)

        logger.info(
            "transaction_verified",
            transaction_id=transaction.transaction_id,
            risk_level=result.risk_level,
            triggered_rules=result.triggered_rules,
        )

        if result.is_suspicious:
            self._alert_service.send_alert(transaction, result)

    def run(self, max_messages: int | None = None) -> None:
        self._running = True
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

        consumer = TransactionConsumer(self._cfg)
        consumer.subscribe()
        processed = 0
        logger.info("aml_verifier_started", topic=self._cfg.kafka_transactions_topic)

        try:
            while self._running:
                txn = consumer.poll_one(timeout=1.0)
                if txn:
                    self.process_transaction(txn)
                    processed += 1
                    if max_messages and processed >= max_messages:
                        break
        finally:
            # всегда закрываем consumer корректно — коммитит последний offset
            consumer.close()
            logger.info("aml_verifier_stopped", processed=processed)
