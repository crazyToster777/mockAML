import structlog
from confluent_kafka import KafkaException
from confluent_kafka import Producer as ConfluentProducer

from src.config import Settings, settings as default_settings
from src.models.transaction import Transaction

logger = structlog.get_logger(__name__)


def _delivery_callback(err, msg):
    if err:
        logger.error("kafka_delivery_failed", error=str(err), topic=msg.topic())
    else:
        logger.debug(
            "kafka_delivery_success",
            topic=msg.topic(),
            partition=msg.partition(),
            offset=msg.offset(),
        )


class TransactionProducer:
    def __init__(self, cfg: Settings = default_settings):
        self._cfg = cfg
        self._producer = ConfluentProducer({
            "bootstrap.servers": cfg.kafka_bootstrap_servers,
            "acks": "all",
            "retries": 5,
            "retry.backoff.ms": 300,
            "enable.idempotence": True,
        })

    def send_transaction(self, transaction: Transaction, topic: str | None = None) -> None:
        topic = topic or self._cfg.kafka_transactions_topic
        try:
            self._producer.produce(
                topic=topic,
                key=transaction.account_id.encode("utf-8"),
                value=transaction.to_kafka_payload(),
                on_delivery=_delivery_callback,
            )
            self._producer.poll(0)
        except KafkaException as exc:
            logger.error(
                "kafka_produce_failed",
                error=str(exc),
                transaction_id=transaction.transaction_id,
            )
            raise

    def flush(self, timeout: float = 10.0) -> None:
        remaining = self._producer.flush(timeout=timeout)
        if remaining > 0:
            logger.warning("kafka_flush_incomplete", remaining=remaining)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.flush()
