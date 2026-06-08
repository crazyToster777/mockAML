from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from src.database.session import db_session

router = APIRouter(tags=["analytics"])


class RiskCount(BaseModel):
    risk_level: str
    count: int


class VolumePoint(BaseModel):
    hour: str
    low: int
    medium: int
    high: int
    blocked: int


class RuleCount(BaseModel):
    rule: str
    count: int


class CumulativePoint(BaseModel):
    verified_at: str
    cumulative: int


@router.get("/analytics/risk-distribution", response_model=list[RiskCount])
def risk_distribution():
    with db_session() as s:
        rows = s.execute(text("""
            SELECT risk_level, COUNT(*) AS count
            FROM aml_results
            GROUP BY risk_level
            ORDER BY count DESC
        """)).fetchall()
    return [RiskCount(risk_level=r.risk_level, count=r.count) for r in rows]


@router.get("/analytics/volume-over-time", response_model=list[VolumePoint])
def volume_over_time():
    with db_session() as s:
        rows = s.execute(text("""
            SELECT DATE_TRUNC('hour', verified_at) AS hour,
                   COUNT(*) FILTER (WHERE risk_level = 'low')     AS low,
                   COUNT(*) FILTER (WHERE risk_level = 'medium')  AS medium,
                   COUNT(*) FILTER (WHERE risk_level = 'high')    AS high,
                   COUNT(*) FILTER (WHERE risk_level = 'blocked') AS blocked
            FROM aml_results
            GROUP BY 1
            ORDER BY 1
        """)).fetchall()
    return [
        VolumePoint(
            hour=r.hour.isoformat(),
            low=r.low or 0,
            medium=r.medium or 0,
            high=r.high or 0,
            blocked=r.blocked or 0,
        )
        for r in rows
    ]


@router.get("/analytics/triggered-rules", response_model=list[RuleCount])
def triggered_rules():
    with db_session() as s:
        rows = s.execute(text("""
            SELECT UNNEST(triggered_rules) AS rule, COUNT(*) AS count
            FROM aml_results
            WHERE triggered_rules <> '{}'
            GROUP BY 1
            ORDER BY count DESC
        """)).fetchall()
    return [RuleCount(rule=r.rule, count=r.count) for r in rows]


@router.get("/analytics/cumulative-suspicious", response_model=list[CumulativePoint])
def cumulative_suspicious():
    with db_session() as s:
        rows = s.execute(text("""
            SELECT TO_CHAR(verified_at AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS') AS verified_at,
                   ROW_NUMBER() OVER (ORDER BY verified_at) AS cumulative
            FROM aml_results
            WHERE risk_level IN ('high', 'blocked')
            ORDER BY verified_at
        """)).fetchall()
    return [CumulativePoint(verified_at=r.verified_at, cumulative=r.cumulative) for r in rows]
