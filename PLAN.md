# AML Verification Service — Project Plan

## Context

Build a production-grade Python project demonstrating end-to-end AML (Anti-Money Laundering)
verification using Kafka and PostgreSQL. The project showcases automated test suites (pytest + Allure),
data quality checks, reconciliation, and monitoring — all owned end-to-end by a QA engineer.

Stack: Python 3.13, confluent-kafka, SQLAlchemy 2.0, PostgreSQL 16, testcontainers.

---

## Architecture

```
financial transaction → Kafka topic (aml.transactions)
  → AMLVerifier (consumer) → rule engine → PostgreSQL
  → aml.results Kafka topic (optional output)
  → AlertService (webhook / log)

ReconciliationService: compares Kafka high-watermark offsets vs DB row counts to detect data loss
```

---

## Directory Structure

```
kafka/
├── docker-compose.yml              ← Kafka + Zookeeper + PostgreSQL (confluentinc 7.6.0, pg 16)
├── requirements.txt
├── pyproject.toml                  ← pytest config, markers, ruff, mypy
├── .env.example
├── main.py                         ← CLI: produce / verify / reconcile
├── src/
│   ├── config.py                   ← pydantic-settings, single settings singleton
│   ├── models/
│   │   └── transaction.py          ← Transaction + AMLVerificationResult (Pydantic v2, Decimal)
│   ├── kafka_client/
│   │   ├── producer.py             ← acks=all, idempotent, partition by account_id
│   │   └── consumer.py             ← manual commit, get_topic_end_offsets for reconciliation
│   ├── database/
│   │   ├── models.py               ← SQLAlchemy 2.0 ORM (TransactionRecord + AMLResultRecord)
│   │   ├── session.py              ← engine factory, db_session context manager
│   │   └── repository.py          ← session.merge() for idempotent upserts
│   └── aml/
│       ├── rules.py                ← pure rule engine: AmountThreshold, Blacklist, Velocity, Structuring
│       ├── verifier.py             ← orchestrates: consume → rules → persist → alert
│       ├── reconciliation.py       ← ReconciliationReport dataclass, watermark vs DB count
│       └── alert_service.py        ← log-only in tests, httpx webhook in prod
└── tests/
    ├── conftest.py                 ← testcontainers fixtures (session-scoped), SAVEPOINT rollback
    ├── factories.py                ← Faker-based: make_transaction, make_high_value, make_velocity_burst
    ├── unit/
    │   └── test_aml_rules.py
    ├── integration/
    │   ├── test_kafka_flow.py
    │   └── test_db_repository.py
    ├── e2e/
    │   └── test_aml_pipeline.py
    └── data_quality/
        └── test_reconciliation.py
```

---

## Dependencies

```
# Kafka
confluent-kafka~=2.4

# Database
sqlalchemy~=2.0
psycopg2-binary~=2.9
alembic~=1.13

# Data validation
pydantic~=2.7
pydantic-settings~=2.3

# Testing
pytest~=8.2
allure-pytest~=2.13
testcontainers~=4.7
testcontainers[kafka]~=4.7
testcontainers[postgresql]~=4.7

# Utilities
faker~=25.0
structlog~=24.2
httpx~=0.27
tenacity~=8.3
python-dotenv~=1.0
```

---

## AML Rules

All rules are **pure functions** — no I/O, fully unit-testable without containers.

| Rule | Trigger | Risk Level |
|------|---------|------------|
| `AmountThresholdRule` | amount ≥ $10,000 (BSA Currency Transaction Report threshold) | HIGH |
| `BlacklistRule` | account or counterparty in OFAC/sanctions set | BLOCKED |
| `VelocityRule` | > N transactions for same account within rolling time window | MEDIUM |
| `StructuringRule` | 3+ transactions in 80–99% of threshold band within 24h | HIGH |

`RuleEngine.evaluate()` composes all rules and returns the maximum risk level across triggered rules.

---

## Test Layers

| Marker | What it tests | Containers |
|--------|--------------|------------|
| `unit` | Rule engine: thresholds, blacklist, velocity, structuring, aggregation | None |
| `integration` | Kafka round-trip, DB CRUD, idempotent upserts, ordering | testcontainers |
| `e2e` | Full pipeline: produce → consume → verify → DB result check | testcontainers |
| `data_quality` | Reconciliation healthy/unhealthy, duplicate detection, data loss | testcontainers |

Run subsets:
```bash
pytest -m unit                        # fast, no Docker
pytest -m "integration or e2e"        # requires Docker
pytest -m data_quality
pytest                                # full suite + Allure report
```

---

## Key Design Decisions

**`session.merge()` not `session.add()`**
Kafka at-least-once delivery means the verifier may process the same message twice after a crash.
`merge()` is an upsert — the second processing is a no-op, not a `UniqueViolation`.

**Per-test Kafka consumer groups**
Each test gets `group_id=f"test-group-{uuid4()}"` to prevent offset sharing between tests. Without
this, two tests in the same run would share offsets and miss messages the other produced.

**`session.begin_nested()` (SAVEPOINT) in `db_session` fixture**
SAVEPOINT rollback takes <1ms vs 500ms for DROP/CREATE between tests. Each test gets a clean DB
state without the overhead of schema recreation.

**Reconciliation via Kafka watermark offsets**
`sum(high_watermark per partition)` = total messages ever produced to the topic. Compare against
`COUNT(*)` in DB to detect data loss with no external counter needed.

**`Decimal` for money**
`float` arithmetic is unsuitable for financial calculations. `Decimal` maps to PostgreSQL
`NUMERIC(20,4)` and is handled natively by Pydantic v2.

**Partition by `account_id`**
All transactions for the same account land on the same Kafka partition, guaranteeing ordering
required for velocity and structuring rule correctness.

---

## Implementation Order

| Phase | Files |
|-------|-------|
| 1. Foundation | `requirements.txt`, `docker-compose.yml`, `.env.example`, `src/config.py`, `src/models/transaction.py` |
| 2. Database | `src/database/models.py`, `session.py`, `repository.py` |
| 3. Kafka | `src/kafka_client/producer.py`, `consumer.py` |
| 4. AML logic | `src/aml/rules.py`, `alert_service.py`, `verifier.py`, `reconciliation.py` |
| 5. Tests | `tests/factories.py`, `conftest.py`, then unit → integration → e2e → data_quality |
| 6. Entrypoint | `main.py`, `pyproject.toml` |

---

## Verification

```bash
# Start local infrastructure
docker-compose up -d

# Install dependencies
pip install -r requirements.txt

# Run unit tests (no Docker needed)
pytest -m unit -v

# Run all tests with Allure reporting
pytest --alluredir=allure-results -v
allure serve allure-results

# Manual pipeline walkthrough
python main.py produce --count 20
python main.py verify --max-messages 20
python main.py reconcile          # exits 0 if healthy, 1 if data loss detected
```
