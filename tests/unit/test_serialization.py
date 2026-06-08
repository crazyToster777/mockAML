import allure
import pytest

from src.kafka_client.serialization import make_serializer
from src.config import Settings
from tests.factories import make_transaction


@pytest.fixture
def json_serializer():
    cfg = Settings(schema_registry_url="")
    serialize, deserialize = make_serializer(cfg)
    return serialize, deserialize


@allure.epic("Kafka Pipeline")
@allure.feature("Message Serialization")
@pytest.mark.unit
class TestJsonSerialization:
    @allure.story("Round-trip")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Transaction serializes and deserializes back to identical object")
    def test_roundtrip(self, json_serializer):
        serialize, deserialize = json_serializer
        original = make_transaction(amount_usd=1_234.56)

        raw = serialize(original)
        restored = deserialize(raw)

        assert restored.transaction_id == original.transaction_id
        assert restored.account_id == original.account_id
        assert restored.amount_usd == original.amount_usd
        assert restored.transaction_type == original.transaction_type

    @allure.story("Output type")
    @allure.title("Serialized output is bytes")
    def test_serialize_returns_bytes(self, json_serializer):
        serialize, _ = json_serializer
        raw = serialize(make_transaction())
        assert isinstance(raw, bytes)

    @allure.story("Decimal precision")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Decimal precision is preserved after round-trip")
    def test_decimal_precision_preserved(self, json_serializer):
        serialize, deserialize = json_serializer
        txn = make_transaction(amount_usd=9_999.99)
        restored = deserialize(serialize(txn))
        assert str(restored.amount_usd) == str(txn.amount_usd)

    @allure.story("Invalid input")
    @allure.title("Garbage bytes raise an exception on deserialize")
    def test_invalid_bytes_raises(self, json_serializer):
        _, deserialize = json_serializer
        with pytest.raises(Exception):
            deserialize(b"this is not valid json {{{")
