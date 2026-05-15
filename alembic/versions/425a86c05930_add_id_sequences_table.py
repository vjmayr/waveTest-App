"""add id_sequences table

Revision ID: 425a86c05930
Revises: 955fe0dd8cdf
Create Date: 2026-05-15 08:38:35.371230

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '425a86c05930'
down_revision: Union[str, Sequence[str], None] = '955fe0dd8cdf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Schema
    op.create_table('id_sequences',
        sa.Column('prefix', sa.String(length=8), nullable=False),
        sa.Column('next_value', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('prefix')
    )

    # 2. Seed from existing tables. For each (table, id_column, prefix) we
    # compute MAX(int(suffix)) over the existing rows whose id starts with
    # the prefix, and write that into id_sequences.next_value so the very
    # next allocation is max+1 (i.e. contiguous with what already exists).
    bind = op.get_bind()
    seeds = [
        ("CLI", "clients",             "client_id"),
        ("SYS", "systems",             "system_id"),
        ("PRJ", "projects",            "project_id"),
        ("PT",  "project_types",       "type_id"),
        ("AL",  "audit_log",           "audit_id"),
        ("RR",  "risk_register",       "risk_id"),
        ("HOP", "oversight_plans",     "plan_id"),
        ("CSP", "cybersecurity_plans", "plan_id"),
        ("SUS", "sustainability_records", "record_id"),
        ("INC", "incident_reports",    "incident_id"),
        ("RTE", "explanation_requests", "request_id"),
        ("MC",  "model_cards",         "card_id"),
        ("PI",  "project_inputs",      "input_id"),
    ]
    for prefix, table, col in seeds:
        # SQLite's SUBSTR is 1-indexed; CAST '' AS INTEGER returns 0.
        max_n = bind.execute(sa.text(
            f"SELECT COALESCE("
            f"  MAX(CAST(SUBSTR({col}, {len(prefix) + 1}) AS INTEGER)), 0"
            f") FROM {table} WHERE {col} LIKE :p"
        ), {"p": f"{prefix}%"}).scalar() or 0
        bind.execute(sa.text(
            "INSERT INTO id_sequences (prefix, next_value) VALUES (:p, :v)"
        ), {"p": prefix, "v": int(max_n)})


def downgrade() -> None:
    op.drop_table('id_sequences')
