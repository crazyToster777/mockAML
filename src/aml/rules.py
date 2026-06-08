import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import structlog

from src.models.transaction import AMLVerificationResult, RiskLevel, Transaction

logger = structlog.get_logger(__name__)

BLACKLISTED_ACCOUNTS: frozenset[str] = frozenset({
    "SANCTIONED001",
    "OFAC_BLOCKED_002",
    "TERROR_FINANCE_003",
})


@dataclass
class RuleResult:
    triggered: bool
    rule_name: str
    risk_contribution: RiskLevel
    note: str = ""


class AMLRule(ABC):
    @abstractmethod
    def evaluate(
        self,
        transaction: Transaction,
        recent_transactions: list[Transaction],
    ) -> RuleResult:
        ...


class AmountThresholdRule(AMLRule):
    """Flags transactions >= CTR threshold (Bank Secrecy Act $10,000)."""

    def __init__(self, threshold_usd: float = 10_000.0):
        self.threshold = Decimal(str(threshold_usd))

    def evaluate(self, transaction: Transaction, recent_transactions: list[Transaction]) -> RuleResult:
        triggered = transaction.amount_usd >= self.threshold
        return RuleResult(
            triggered=triggered,
            rule_name="amount_threshold",
            risk_contribution=RiskLevel.HIGH if triggered else RiskLevel.LOW,
            note=f"Amount {transaction.amount_usd} >= threshold {self.threshold}" if triggered else "",
        )


class BlacklistRule(AMLRule):
    """Blocks transactions to/from sanctioned accounts.

    Seed set (BLACKLISTED_ACCOUNTS) is always active. Additionally refreshes from
    the blacklisted_accounts DB table every ttl_seconds (default 5 min).
    On DB failure the stale cache is kept — the seed set ensures a hard floor.
    """

    def __init__(self, cfg=None, ttl_seconds: int = 300):
        self._cfg = cfg
        self._ttl = ttl_seconds
        self._cache: frozenset[str] = BLACKLISTED_ACCOUNTS
        self._cached_at: datetime | None = None
        self._lock = threading.Lock()

    def _get_blacklist(self) -> frozenset[str]:
        now = datetime.now(timezone.utc)
        if self._cached_at is not None and (now - self._cached_at).total_seconds() < self._ttl:
            return self._cache
        with self._lock:
            if self._cached_at is not None and (now - self._cached_at).total_seconds() < self._ttl:
                return self._cache
            try:
                from sqlalchemy import select

                from src.database.models import BlacklistedAccount
                from src.database.session import db_session
                with db_session(self._cfg) as session:
                    rows = session.execute(select(BlacklistedAccount.account_id)).scalars().all()
                self._cache = BLACKLISTED_ACCOUNTS | frozenset(rows)
                self._cached_at = now
                logger.debug("blacklist_refreshed", total=len(self._cache))
            except Exception as exc:
                logger.warning("blacklist_refresh_failed", error=str(exc))
                if self._cached_at is None:
                    self._cached_at = now
        return self._cache

    def evaluate(self, transaction: Transaction, recent_transactions: list[Transaction]) -> RuleResult:
        blacklist = self._get_blacklist()
        hit = (
            transaction.account_id in blacklist
            or transaction.counterparty_account_id in blacklist
        )
        return RuleResult(
            triggered=hit,
            rule_name="blacklist",
            risk_contribution=RiskLevel.BLOCKED if hit else RiskLevel.LOW,
            note="Blacklist hit for account" if hit else "",
        )


class VelocityRule(AMLRule):
    """Flags accounts exceeding N transactions within a rolling time window."""

    def __init__(self, max_transactions: int = 10, window_seconds: int = 3600):
        self.max_transactions = max_transactions
        self.window = timedelta(seconds=window_seconds)

    def evaluate(self, transaction: Transaction, recent_transactions: list[Transaction]) -> RuleResult:
        cutoff = transaction.timestamp - self.window
        window_txns = [
            t for t in recent_transactions
            if t.account_id == transaction.account_id and t.timestamp >= cutoff
        ]
        count = len(window_txns)
        triggered = count >= self.max_transactions
        return RuleResult(
            triggered=triggered,
            rule_name="velocity",
            risk_contribution=RiskLevel.MEDIUM if triggered else RiskLevel.LOW,
            note=f"{count} transactions in {self.window} window" if triggered else "",
        )


class StructuringRule(AMLRule):
    """Detects structuring — multiple transactions just below CTR threshold to avoid reporting."""

    def __init__(self, threshold_usd: float = 10_000.0, window_seconds: int = 86400):
        self.threshold = Decimal(str(threshold_usd))
        self.band_low = self.threshold * Decimal("0.8")
        self.window = timedelta(seconds=window_seconds)

    def evaluate(self, transaction: Transaction, recent_transactions: list[Transaction]) -> RuleResult:
        if not (self.band_low <= transaction.amount_usd < self.threshold):
            return RuleResult(triggered=False, rule_name="structuring", risk_contribution=RiskLevel.LOW)

        cutoff = transaction.timestamp - self.window
        band_txns = [
            t for t in recent_transactions
            if (
                t.account_id == transaction.account_id
                and t.timestamp >= cutoff
                and self.band_low <= t.amount_usd < self.threshold
            )
        ]
        triggered = len(band_txns) >= 2
        return RuleResult(
            triggered=triggered,
            rule_name="structuring",
            risk_contribution=RiskLevel.HIGH if triggered else RiskLevel.LOW,
            note=f"Possible structuring: {len(band_txns) + 1} sub-threshold txns in 24h" if triggered else "",
        )


@dataclass
class RuleEngine:
    rules: list[AMLRule] = field(default_factory=list)

    @classmethod
    def default(cls, cfg=None) -> "RuleEngine":
        from src.config import settings as default_settings
        c = cfg or default_settings
        return cls(rules=[
            AmountThresholdRule(threshold_usd=c.amount_threshold_usd),
            BlacklistRule(cfg=c),
            VelocityRule(
                max_transactions=c.velocity_max_transactions,
                window_seconds=c.velocity_window_seconds,
            ),
            StructuringRule(),
        ])

    def evaluate(
        self,
        transaction: Transaction,
        recent_transactions: list[Transaction],
    ) -> AMLVerificationResult:
        results = [rule.evaluate(transaction, recent_transactions) for rule in self.rules]
        triggered = [r for r in results if r.triggered]
        risk_level = self._aggregate_risk(results)
        return AMLVerificationResult(
            transaction_id=transaction.transaction_id,
            account_id=transaction.account_id,
            risk_level=risk_level,
            triggered_rules=[r.rule_name for r in triggered],
            amount_usd=transaction.amount_usd,
            notes="; ".join(r.note for r in triggered if r.note),
        )

    @staticmethod
    def _aggregate_risk(results: list[RuleResult]) -> RiskLevel:
        priority = {RiskLevel.BLOCKED: 4, RiskLevel.HIGH: 3, RiskLevel.MEDIUM: 2, RiskLevel.LOW: 1}
        return max(
            (r.risk_contribution for r in results),
            key=lambda lvl: priority[lvl],
            default=RiskLevel.LOW,
        )
