from datetime import datetime, timezone
from decimal import Decimal

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.kafka_client.producer import TransactionProducer
from src.models.transaction import Transaction, TransactionType

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/produce", tags=["produce"])

_BLACKLISTED = frozenset({"SANCTIONED001", "OFAC_BLOCKED_002", "TERROR_FINANCE_003"})

_producer: TransactionProducer | None = None


def _get_producer() -> TransactionProducer:
    global _producer
    if _producer is None:
        _producer = TransactionProducer()
    return _producer


class BulkRequest(BaseModel):
    count: int = Field(10, ge=1, le=100)
    include_suspicious: bool = True


class BulkResponse(BaseModel):
    produced: int


class SingleRequest(BaseModel):
    account_id: str
    counterparty_account_id: str
    amount_usd: float = Field(gt=0)
    transaction_type: TransactionType


class SingleResponse(BaseModel):
    transaction_id: str
    warnings: list[str]


@router.post("/bulk", response_model=BulkResponse)
def produce_bulk(req: BulkRequest) -> BulkResponse:
    types = list(TransactionType)
    try:
        producer = _get_producer()
        for i in range(req.count):
            amount = Decimal(str(100 + (i * 97) % 15000))
            counterparty = f"ACCT{(i + 1):06d}"
            if req.include_suspicious and i == req.count // 2:
                amount = Decimal("15000.00")
            if req.include_suspicious and i == req.count - 1:
                counterparty = "SANCTIONED001"
            producer.send_transaction(Transaction(
                account_id=f"ACCT{i:06d}",
                counterparty_account_id=counterparty,
                amount_usd=amount,
                transaction_type=types[i % len(types)],
                timestamp=datetime.now(timezone.utc),
            ))
        producer.flush()
    except Exception as exc:
        logger.error("bulk_produce_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
    return BulkResponse(produced=req.count)


@router.post("/single", response_model=SingleResponse)
def produce_single(req: SingleRequest) -> SingleResponse:
    warnings: list[str] = []
    if req.amount_usd >= 10_000:
        warnings.append("Amount ≥ $10,000 — triggers amount_threshold rule.")
    if req.counterparty_account_id.upper() in _BLACKLISTED:
        warnings.append("Counterparty is blacklisted — will be BLOCKED.")
    try:
        txn = Transaction(
            account_id=req.account_id,
            counterparty_account_id=req.counterparty_account_id,
            amount_usd=Decimal(str(req.amount_usd)),
            transaction_type=req.transaction_type,
            timestamp=datetime.now(timezone.utc),
        )
        producer = _get_producer()
        producer.send_transaction(txn)
        producer.flush()
    except Exception as exc:
        logger.error("single_produce_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
    return SingleResponse(transaction_id=txn.transaction_id, warnings=warnings)
