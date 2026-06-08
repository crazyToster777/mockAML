from fastapi import APIRouter
from pydantic import BaseModel

from src.aml.reconciliation import ReconciliationService

router = APIRouter(tags=["reconciliation"])


class ReconciliationReport(BaseModel):
    is_healthy: bool
    kafka_total_messages: int
    db_transaction_count: int
    db_result_count: int
    missing_in_db: int
    unverified_in_db: int
    duplicate_result_ids: list[str]


@router.get("/reconciliation", response_model=ReconciliationReport)
def run_reconciliation():
    report = ReconciliationService().run()
    return ReconciliationReport(
        is_healthy=report.is_healthy,
        kafka_total_messages=report.kafka_total_messages,
        db_transaction_count=report.db_transaction_count,
        db_result_count=report.db_result_count,
        missing_in_db=report.missing_in_db,
        unverified_in_db=report.unverified_in_db,
        duplicate_result_ids=report.duplicate_result_ids,
    )
