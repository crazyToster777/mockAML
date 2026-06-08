import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator


class TransactionType(StrEnum):
    WIRE_TRANSFER = "wire_transfer"
    ACH = "ach"
    CASH_DEPOSIT = "cash_deposit"
    CASH_WITHDRAWAL = "cash_withdrawal"
    CRYPTO_EXCHANGE = "crypto_exchange"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKED = "blocked"


class Transaction(BaseModel):
    transaction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    account_id: str
    counterparty_account_id: str
    amount_usd: Annotated[Decimal, Field(gt=Decimal("0"), decimal_places=2)]
    transaction_type: TransactionType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("account_id", "counterparty_account_id")
    @classmethod
    def validate_account_format(cls, v: str) -> str:
        if not v or len(v) < 6:
            raise ValueError(f"account_id must be at least 6 chars, got: {v!r}")
        return v.upper()

    def to_kafka_payload(self) -> bytes:
        return self.model_dump_json(exclude_none=True).encode("utf-8")

    @classmethod
    def from_kafka_payload(cls, data: bytes) -> "Transaction":
        return cls.model_validate_json(data)


class AMLVerificationResult(BaseModel):
    result_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    transaction_id: str
    account_id: str
    risk_level: RiskLevel
    triggered_rules: list[str] = Field(default_factory=list)
    amount_usd: Decimal
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str = ""

    @property
    def is_suspicious(self) -> bool:
        return self.risk_level in (RiskLevel.HIGH, RiskLevel.BLOCKED)
