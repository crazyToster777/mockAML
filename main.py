"""
AML Verification Service

Usage:
    python main.py produce --count 20
    python main.py verify
    python main.py verify --max-messages 20
    python main.py reconcile
"""
import argparse
import sys
from datetime import datetime, timezone
from decimal import Decimal

from src.aml.reconciliation import ReconciliationService
from src.aml.verifier import AMLVerifier
from src.kafka_client.producer import TransactionProducer
from src.models.transaction import Transaction, TransactionType


def _make_sample_transaction(i: int) -> Transaction:
    types = list(TransactionType)
    return Transaction(
        account_id=f"ACCT{i:06d}",
        counterparty_account_id=f"ACCT{(i + 1):06d}",
        amount_usd=Decimal(str(100 + (i * 97) % 15000)),
        transaction_type=types[i % len(types)],
        timestamp=datetime.now(timezone.utc),
    )


def cmd_produce(count: int) -> None:
    with TransactionProducer() as producer:
        for i in range(count):
            txn = _make_sample_transaction(i)
            producer.send_transaction(txn)
    print(f"Produced {count} transactions.")


def cmd_verify(max_messages: int | None = None) -> None:
    AMLVerifier().run(max_messages=max_messages)


def cmd_reconcile() -> None:
    report = ReconciliationService().run()
    print(report)
    sys.exit(0 if report.is_healthy else 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="AML Verification Service")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("produce", help="Produce synthetic transactions to Kafka")
    p.add_argument("--count", type=int, default=10)

    v = sub.add_parser("verify", help="Run the AML verifier consumer loop")
    v.add_argument("--max-messages", type=int, default=None)

    sub.add_parser("reconcile", help="Check Kafka vs DB consistency")

    args = parser.parse_args()
    if args.command == "produce":
        cmd_produce(args.count)
    elif args.command == "verify":
        cmd_verify(args.max_messages)
    elif args.command == "reconcile":
        cmd_reconcile()


if __name__ == "__main__":
    main()
