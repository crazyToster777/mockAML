"""
Serialization layer with optional Schema Registry support.

If settings.schema_registry_url is set → Avro (confluent_kafka schema_registry).
Otherwise → JSON (current behavior, zero extra dependencies at runtime).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.config import Settings

_TRANSACTION_AVRO_SCHEMA = """
{
  "type": "record",
  "name": "Transaction",
  "namespace": "aml",
  "fields": [
    {"name": "transaction_id", "type": "string"},
    {"name": "account_id",     "type": "string"},
    {"name": "counterparty_account_id", "type": "string"},
    {"name": "amount_usd",     "type": "string"},
    {"name": "transaction_type", "type": "string"},
    {"name": "timestamp",      "type": "string"},
    {"name": "metadata",       "type": {"type": "map", "values": "string"}, "default": {}}
  ]
}
"""


def make_serializer(cfg: "Settings"):
    """Return (serialize_fn, deserialize_fn) pair for Transaction."""
    if cfg.schema_registry_url:
        return _make_avro_pair(cfg)
    return _json_serialize, _json_deserialize


def _json_serialize(transaction) -> bytes:
    return transaction.to_kafka_payload()


def _json_deserialize(data: bytes):
    from src.models.transaction import Transaction
    return Transaction.from_kafka_payload(data)


def _make_avro_pair(cfg: "Settings"):
    from confluent_kafka.schema_registry import Schema, SchemaRegistryClient
    from confluent_kafka.schema_registry.avro import AvroDeserializer, AvroSerializer
    from confluent_kafka.serialization import SerializationContext, MessageField

    registry = SchemaRegistryClient({"url": cfg.schema_registry_url})
    schema = Schema(_TRANSACTION_AVRO_SCHEMA, schema_type="AVRO")

    def _to_dict(txn, ctx):
        return {
            "transaction_id": txn.transaction_id,
            "account_id": txn.account_id,
            "counterparty_account_id": txn.counterparty_account_id,
            "amount_usd": str(txn.amount_usd),
            "transaction_type": str(txn.transaction_type),
            "timestamp": txn.timestamp.isoformat(),
            "metadata": txn.metadata,
        }

    def _from_dict(d, ctx):
        from decimal import Decimal
        from datetime import datetime
        from src.models.transaction import Transaction, TransactionType
        return Transaction(
            transaction_id=d["transaction_id"],
            account_id=d["account_id"],
            counterparty_account_id=d["counterparty_account_id"],
            amount_usd=Decimal(d["amount_usd"]),
            transaction_type=TransactionType(d["transaction_type"]),
            timestamp=datetime.fromisoformat(d["timestamp"]),
            metadata=dict(d.get("metadata", {})),
        )

    avro_ser = AvroSerializer(registry, schema, _to_dict)
    avro_deser = AvroDeserializer(registry, schema, _from_dict)
    topic = cfg.kafka_transactions_topic

    def serialize(txn) -> bytes:
        ctx = SerializationContext(topic, MessageField.VALUE)
        return avro_ser(txn, ctx)

    def deserialize(data: bytes):
        ctx = SerializationContext(topic, MessageField.VALUE)
        return avro_deser(data, ctx)

    return serialize, deserialize
