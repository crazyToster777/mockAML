"""Test object factories with sensible defaults."""
from datetime import datetime, timezone
from decimal import Decimal

from src.models.transaction import AMLVerificationResult, RiskLevel, Transaction, TransactionType


def make_transaction(
    account_id: str = "ACCT000001",
    counterparty_account_id: str = "ACCT000002",
    amount_usd: float = 500.0,
    transaction_type: TransactionType = TransactionType.WIRE_TRANSFER,
    timestamp: datetime | None = None,
    **kwargs,
) -> Transaction:
    return Transaction(
        account_id=account_id,
        counterparty_account_id=counterparty_account_id,
        amount_usd=Decimal(str(amount_usd)),
        transaction_type=transaction_type,
        timestamp=timestamp or datetime.now(timezone.utc),
        **kwargs,
    )


def make_aml_result(
    transaction: Transaction | None = None,
    risk_level: RiskLevel = RiskLevel.LOW,
    triggered_rules: list[str] | None = None,
    notes: str = "",
) -> AMLVerificationResult:
    txn = transaction or make_transaction()
    return AMLVerificationResult(
        transaction_id=txn.transaction_id,
        account_id=txn.account_id,
        risk_level=risk_level,
        triggered_rules=triggered_rules or [],
        amount_usd=txn.amount_usd,
        notes=notes,
    )
