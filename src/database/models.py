from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TransactionRecord(Base):
    __tablename__ = "transactions"

    transaction_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    counterparty_account_id: Mapped[str] = mapped_column(String(50), nullable=False)
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    kafka_offset: Mapped[int | None] = mapped_column(nullable=True)
    kafka_partition: Mapped[int | None] = mapped_column(nullable=True)


class AMLResultRecord(Base):
    __tablename__ = "aml_results"

    result_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    triggered_rules: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, server_default="{}")
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class BlacklistedAccount(Base):
    __tablename__ = "blacklisted_accounts"

    account_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="manual")
