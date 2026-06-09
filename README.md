# AML Transaction Verification Service

A real-time Anti-Money Laundering (AML) system that monitors financial transactions for suspicious activity.

## What it does

Transactions are ingested via Kafka and automatically scored against a set of AML rules — amount thresholds, blacklisted counterparties, velocity checks, and structuring patterns. Results are stored in PostgreSQL and exposed through a React dashboard where you can monitor alerts, risk distribution, and transaction history in real time.

## AML Rules

| Rule | Description |
|------|-------------|
| Amount Threshold | Flags transactions ≥ $10,000 |
| Blacklist | Flags transactions involving blocked accounts |
| Velocity | Flags accounts with > 10 transactions within 1 hour |
| Structuring | Flags 3+ transactions just below $10k within 1 hour (smurfing) |

Risk levels: `LOW` → `MEDIUM` → `HIGH` → `BLOCKED`

## Live Demo

**Dashboard:** https://aml.toster.games

**Test Report:** https://aml.toster.games/allure-report/

## Tech Stack

- **Backend:** Python, FastAPI, SQLAlchemy, Alembic
- **Messaging:** Apache Kafka (KRaft, no Zookeeper)
- **Database:** PostgreSQL 17
- **Frontend:** React, TypeScript, Vite
- **Infrastructure:** Docker Compose, nginx, Cloudflare
- **Testing:** pytest, testcontainers, allure
- **CI/CD:** GitHub Actions

## Testing

The project has 94 tests across three layers:

- **Unit** — pure logic, no dependencies
- **Integration** — real Postgres and Kafka via testcontainers
- **API** — full HTTP tests via FastAPI TestClient

Coverage: **84%** (threshold: 80%)

CI pipeline runs on manual trigger, generates an Allure report and publishes it to the live demo URL.

## Quick Start

```bash
git clone <repo-url>
cd mockAML
cp .env.example .env
make up
```

Open http://localhost:3000/ — dashboard is ready in ~30s while Kafka initializes.

To produce test transactions:

```bash
docker compose exec api python main.py produce --count 20
```
