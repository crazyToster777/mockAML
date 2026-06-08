import logging
from datetime import datetime, timezone

import structlog
from confluent_kafka import Consumer as ConfluentConsumer
from confluent_kafka import KafkaError, KafkaException, Producer as ConfluentProducer, TopicPartition
from tenacity import before_log, retry, stop_after_attempt, wait_exponential

from src.config import Settings, settings as default_settings
from src.models.transaction import Transaction

logger = structlog.get_logger(__name__)
_stdlib_logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(10),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    before=before_log(_stdlib_logger, logging.WARNING),
    reraise=True,
)
def _create_confluent_consumer(cfg: Settings, group_id: str) -> ConfluentConsumer:
    consumer = ConfluentConsumer({
        "bootstrap.servers": cfg.kafka_bootstrap_servers,
        "group.id": group_id,
        "auto.offset.reset": cfg.kafka_auto_offset_reset,
        "enable.auto.commit": False,
        "max.poll.interval.ms": 300_000,
    })
    consumer.list_topics(timeout=5)
    return consumer


class TransactionConsumer:
    def __init__(self, cfg: Settings = default_settings, group_id: str | None = None):
        self._cfg = cfg
        effective_group = group_id or cfg.kafka_consumer_group
        self._consumer = _create_confluent_consumer(cfg, effective_group)
        self._dlq_producer = ConfluentProducer({
            "bootstrap.servers": cfg.kafka_bootstrap_servers,
            "acks": "all",
        })
        from src.kafka_client.serialization import make_serializer
        _, self._deserialize = make_serializer(cfg)

    def subscribe(self, topics: list[str] | None = None) -> None:
        self._consumer.subscribe(topics or [self._cfg.kafka_transactions_topic])

    def poll_one(self, timeout: float = 5.0) -> Transaction | None:
        msg = self._consumer.poll(timeout)
        if msg is None:
            return None
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                return None
            raise KafkaException(msg.error())
        try:
            txn = self._deserialize(msg.value())
            self._consumer.commit(message=msg, asynchronous=False)
            return txn
        except Exception as exc:
            logger.error(
                "deserialisation_failed",
                error=str(exc),
                topic=msg.topic(),
                partition=msg.partition(),
                offset=msg.offset(),
            )
            self._send_to_dlq(msg, exc)
            self._consumer.commit(message=msg, asynchronous=False)
            return None

    def _send_to_dlq(self, original_msg, exc: Exception) -> None:
        dlq_topic = f"{self._cfg.kafka_transactions_topic}.dlq"
        try:
            self._dlq_producer.produce(
                topic=dlq_topic,
                value=original_msg.value(),
                headers={
                    "error": str(exc),
                    "original_topic": original_msg.topic(),
                    "original_partition": str(original_msg.partition()),
                    "original_offset": str(original_msg.offset()),
                    "failed_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            self._dlq_producer.poll(0)
            logger.warning(
                "message_sent_to_dlq",
                dlq_topic=dlq_topic,
                original_offset=original_msg.offset(),
            )
        except Exception as dlq_exc:
            logger.error("dlq_send_failed", error=str(dlq_exc))

    def get_topic_end_offsets(self, topic: str) -> dict[int, int]:
        metadata = self._consumer.list_topics(topic, timeout=10)
        partitions = [
            TopicPartition(topic, p)
            for p in metadata.topics[topic].partitions
        ]
        result = {}
        for tp in partitions:
            lo, hi = self._consumer.get_watermark_offsets(tp, timeout=5)
            result[tp.partition] = hi
        return result

    def close(self) -> None:
        self._dlq_producer.flush(timeout=5.0)
        self._consumer.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
