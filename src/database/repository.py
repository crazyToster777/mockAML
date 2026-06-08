from datetime import datetime, timedelta, timezone
from decimal import Decimal

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.database.models import AMLResultRecord, TransactionRecord
from src.models.transaction import AMLVerificationResult, RiskLevel, Transaction

logger = structlog.get_logger(__name__)


class TransactionRepository:
    def __init__(self, session: Session):
        self.session = session

    def save_transaction(
        self,
        txn: Transaction,
        kafka_offset: int | None = None,
        kafka_partition: int | None = None,
    ) -> None:
        record = TransactionRecord(
            transaction_id=txn.transaction_id,
            account_id=txn.account_id,
            counterparty_account_id=txn.counterparty_account_id,
            amount_usd=txn.amount_usd,
            transaction_type=txn.transaction_type.value,
            timestamp=txn.timestamp,
            kafka_offset=kafka_offset,
            kafka_partition=kafka_partition,
        )
        self.session.merge(record)

    def save_aml_result(self, result: AMLVerificationResult) -> None:
        record = AMLResultRecord(
            result_id=result.result_id,
            transaction_id=result.transaction_id,
            account_id=result.account_id,
            risk_level=result.risk_level.value,
            triggered_rules=result.triggered_rules,
            amount_usd=result.amount_usd,
            verified_at=result.verified_at,
            notes=result.notes,
        )
        self.session.merge(record)

    def get_recent_transactions(self, account_id: str, window_seconds: int = 3600) -> list[Transaction]:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
        stmt = (
            select(TransactionRecord)
            .where(TransactionRecord.account_id == account_id)
            .where(TransactionRecord.timestamp >= cutoff)
            .order_by(TransactionRecord.timestamp.asc())
        )
        rows = self.session.execute(stmt).scalars().all()
        return [
            Transaction(
                transaction_id=r.transaction_id,
                account_id=r.account_id,
                counterparty_account_id=r.counterparty_account_id,
                amount_usd=r.amount_usd,
                transaction_type=r.transaction_type,
                timestamp=r.timestamp,
            )
            for r in rows
        ]

    def count_transactions(self) -> int:
        return self.session.execute(select(func.count()).select_from(TransactionRecord)).scalar_one()

    def count_aml_results(self) -> int:
        return self.session.execute(select(func.count()).select_from(AMLResultRecord)).scalar_one()

    def get_suspicious_transactions(self, since: datetime | None = None) -> list[AMLResultRecord]:
        stmt = select(AMLResultRecord).where(
            AMLResultRecord.risk_level.in_([RiskLevel.HIGH.value, RiskLevel.BLOCKED.value])
        )
        if since:
            stmt = stmt.where(AMLResultRecord.verified_at >= since)
        return list(self.session.execute(stmt).scalars().all())

    def find_duplicate_transaction_ids(self) -> list[str]:
        stmt = (
            select(AMLResultRecord.transaction_id)
            .group_by(AMLResultRecord.transaction_id)
            .having(func.count(AMLResultRecord.transaction_id) > 1)
        )
        return list(self.session.execute(stmt).scalars().all())
