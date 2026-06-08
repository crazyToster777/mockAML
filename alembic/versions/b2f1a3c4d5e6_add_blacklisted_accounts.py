"""add_blacklisted_accounts

Revision ID: b2f1a3c4d5e6
Revises: 4e89ccba3183
Create Date: 2026-06-08 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2f1a3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "4e89ccba3183"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "blacklisted_accounts",
        sa.Column("account_id", sa.String(50), primary_key=True),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(50), nullable=False, server_default="manual"),
    )


def downgrade() -> None:
    op.drop_table("blacklisted_accounts")
