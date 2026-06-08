from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import text

from src.database.session import db_session

router = APIRouter(tags=["transactions"])


class TransactionRow(BaseModel):
    result_id: str
    transaction_id: str
    account_id: str
    risk_level: str
    amount_usd: float
    triggered_rules: list[str]
    notes: str
    verified_at: str


class TransactionsPage(BaseModel):
    items: list[TransactionRow]
    total: int


@router.get("/transactions", response_model=TransactionsPage)
def list_transactions(
    limit: int = Query(50, le=500),
    offset: int = 0,
    risk_level: list[str] = Query(default=["low", "medium", "high", "blocked"]),
    account_id: str = "",
    min_amount: float = 0.0,
):
    risk_placeholders = ", ".join(f":r{i}" for i in range(len(risk_level)))
    risk_params = {f"r{i}": v for i, v in enumerate(risk_level)}

    filters = f"risk_level IN ({risk_placeholders})"
    params: dict = {**risk_params, "limit": limit, "offset": offset, "min_amount": min_amount}

    if account_id:
        filters += " AND account_id ILIKE :account_id"
        params["account_id"] = f"%{account_id}%"
    if min_amount:
        filters += " AND amount_usd >= :min_amount"

    with db_session() as s:
        total = s.execute(
            text(f"SELECT COUNT(*) FROM aml_results WHERE {filters}"), params
        ).scalar() or 0

        rows = s.execute(text(f"""
            SELECT result_id, transaction_id, account_id, risk_level,
                   triggered_rules, amount_usd, notes,
                   TO_CHAR(verified_at AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS') AS verified_at
            FROM aml_results
            WHERE {filters}
            ORDER BY verified_at DESC
            LIMIT :limit OFFSET :offset
        """), params).fetchall()

    return TransactionsPage(
        total=total,
        items=[
            TransactionRow(
                result_id=r.result_id,
                transaction_id=r.transaction_id,
                account_id=r.account_id,
                risk_level=r.risk_level,
                amount_usd=float(r.amount_usd),
                triggered_rules=r.triggered_rules or [],
                notes=r.notes or "",
                verified_at=r.verified_at,
            )
            for r in rows
        ],
    )
