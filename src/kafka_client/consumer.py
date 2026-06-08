from datetime import datetime, timezone

import structlog
from confluent_kafka import Consumer as ConfluentConsumer
from confluent_kafka import KafkaError, KafkaException, Producer as ConfluentProducer, TopicPartition

from src.config import Settings, settings as default_settings
from src.models.transaction import Transaction

logger = structlog.get_logger(__name__)


class TransactionConsumer:
    def __init__(self, cfg: Settings = default_settings, group_id: str | None = None):
        self._cfg = cfg
        self._consumer = ConfluentConsumer({
            "bootstrap.servers": cfg.kafka_bootstrap_servers,
            "group.id": group_id or cfg.kafka_consumer_group,
            "auto.offset.reset": cfg.kafka_auto_offset_reset,
            "enable.auto.commit": False,
            "max.poll.interval.ms": 300_000,
        })
        self._dlq_producer = ConfluentProducer({
            "bootstrap.servers": cfg.kafka_bootstrap_servers,
            "acks": "all",
        })

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
            txn = Transaction.from_kafka_payload(msg.value())
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
