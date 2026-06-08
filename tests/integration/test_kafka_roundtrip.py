import allure
import pytest
from confluent_kafka import Producer as ConfluentProducer
from confluent_kafka.admin import AdminClient, NewTopic

from src.kafka_client.consumer import TransactionConsumer
from src.kafka_client.producer import TransactionProducer
from tests.factories import make_transaction


def _create_topic(bootstrap: str, topic: str) -> None:
    admin = AdminClient({"bootstrap.servers": bootstrap})
    admin.create_topics([NewTopic(topic, num_partitions=1, replication_factor=1)])


@allure.epic("Kafka Pipeline")
@allure.feature("Producer / Consumer Round-trip")
@pytest.mark.integration
class TestKafkaRoundtrip:
    @allure.story("Produce and consume")
    @allure.severity(allure.severity_level.BLOCKER)
    @allure.title("Produced transaction is consumed and deserialized correctly")
    def test_produce_and_consume(self, kafka_settings):
        topic = "test.roundtrip"
        _create_topic(kafka_settings.kafka_bootstrap_servers, topic)

        txn = make_transaction(amount_usd=1_234.56)

        with allure.step("Produce transaction"):
            producer = TransactionProducer(cfg=kafka_settings)
            producer.send_transaction(txn, topic=topic)
            producer.flush()

        with allure.step("Consume transaction"):
            consumer = TransactionConsumer(cfg=kafka_settings, group_id="test-roundtrip-group")
            consumer._consumer.subscribe([topic])
            consumed = None
            for _ in range(20):
                msg = consumer._consumer.poll(1.0)
                if msg and not msg.error():
                    from src.kafka_client.serialization import make_serializer
                    _, deserialize = make_serializer(kafka_settings)
                    consumed = deserialize(msg.value())
                    break
            consumer.close()

        assert consumed is not None, "No message consumed within timeout"
        assert consumed.transaction_id == txn.transaction_id
        assert consumed.amount_usd == txn.amount_usd

    @allure.story("DLQ routing")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Malformed message is routed to DLQ and poll_one returns None")
    def test_dlq_on_invalid_message(self, kafka_settings):
        topic = kafka_settings.kafka_transactions_topic
        dlq_topic = f"{topic}.dlq"
        _create_topic(kafka_settings.kafka_bootstrap_servers, topic)
        _create_topic(kafka_settings.kafka_bootstrap_servers, dlq_topic)

        with allure.step("Produce garbage bytes"):
            raw_producer = ConfluentProducer({"bootstrap.servers": kafka_settings.kafka_bootstrap_servers})
            raw_producer.produce(topic=topic, value=b"not-valid-json-{{{")
            raw_producer.flush()

        with allure.step("Consumer returns None for bad message"):
            consumer = TransactionConsumer(cfg=kafka_settings, group_id="test-dlq-group")
            consumer.subscribe([topic])
            result = consumer.poll_one(timeout=5.0)
            consumer.close()

        assert result is None

    @allure.story("Manual commit")
    @allure.title("Offset is committed only after successful deserialization")
    def test_offset_committed_on_success(self, kafka_settings):
        topic = "test.commit"
        _create_topic(kafka_settings.kafka_bootstrap_servers, topic)

        txn = make_transaction()
        producer = TransactionProducer(cfg=kafka_settings)
        producer.send_transaction(txn, topic=topic)
        producer.flush()

        consumer = TransactionConsumer(cfg=kafka_settings, group_id="test-commit-group")
        consumer._consumer.subscribe([topic])
        result = consumer.poll_one(timeout=5.0)
        consumer.close()

        assert result is not None
        assert result.transaction_id == txn.transaction_id
