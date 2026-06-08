from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from src.database.session import db_session

router = APIRouter(tags=["overview"])


class OverviewStats(BaseModel):
    total_transactions: int
    verified: int
    suspicious: int
    detection_rate: float


class RecentAlert(BaseModel):
    transaction_id: str
    account_id: str
    risk_level: str
    amount_usd: float
    triggered_rules: list[str]
    notes: str
    verified_at: str


@router.get("/overview/stats", response_model=OverviewStats)
def get_stats():
    with db_session() as s:
        total = s.execute(text("SELECT COUNT(*) FROM transactions")).scalar() or 0
        verified = s.execute(text("SELECT COUNT(*) FROM aml_results")).scalar() or 0
        suspicious = s.execute(
            text("SELECT COUNT(*) FROM aml_results WHERE risk_level IN ('high','blocked')")
        ).scalar() or 0
    return OverviewStats(
        total_transactions=total,
        verified=verified,
        suspicious=suspicious,
        detection_rate=round(suspicious / verified * 100, 2) if verified else 0.0,
    )


@router.get("/overview/recent-alerts", response_model=list[RecentAlert])
def get_recent_alerts(limit: int = 10):
    with db_session() as s:
        rows = s.execute(text("""
            SELECT result_id, transaction_id, account_id, risk_level,
                   triggered_rules, amount_usd, notes,
                   TO_CHAR(verified_at AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS') AS verified_at
            FROM aml_results
            WHERE risk_level IN ('high', 'blocked')
            ORDER BY verified_at DESC
            LIMIT :limit
        """), {"limit": limit}).fetchall()
    return [
        RecentAlert(
            transaction_id=r.transaction_id,
            account_id=r.account_id,
            risk_level=r.risk_level,
            amount_usd=float(r.amount_usd),
            triggered_rules=r.triggered_rules or [],
            notes=r.notes or "",
            verified_at=r.verified_at,
        )
        for r in rows
    ]
