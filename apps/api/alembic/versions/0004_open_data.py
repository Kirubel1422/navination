"""Open data layer: a local index of government open-data catalogues, snapshots of the curated
datasets behind service insights, a sync log, and anonymous navigation events (published back as
an open dataset). Additive.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "od_datasets",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("portal", sa.String(length=24), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("entity", sa.String(length=200), nullable=False),
        sa.Column("theme", sa.String(length=40), nullable=True),
        sa.Column("last_updated", sa.Date(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_od_datasets_portal", "od_datasets", ["portal"])
    op.create_table(
        "od_snapshots",
        sa.Column("key", sa.String(length=80), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("publisher", sa.String(length=200), nullable=False),
        sa.Column("portal", sa.String(length=24), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("resource_name", sa.Text(), nullable=False),
        sa.Column("source_updated", sa.Date(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("columns", sa.JSON(), nullable=False),
        sa.Column("rows", sa.JSON(), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
    )
    op.create_table(
        "od_sync_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("datasets_indexed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("snapshots_ok", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("snapshots_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.create_table(
        "nav_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("topic", sa.String(length=80), nullable=True),
        sa.Column("locale", sa.String(length=4), nullable=False),
        sa.Column("results", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("seconds", sa.Integer(), nullable=True),
    )
    op.create_index("ix_nav_events_day", "nav_events", ["day"])


def downgrade() -> None:
    op.drop_index("ix_nav_events_day", table_name="nav_events")
    op.drop_table("nav_events")
    op.drop_table("od_sync_runs")
    op.drop_table("od_snapshots")
    op.drop_index("ix_od_datasets_portal", table_name="od_datasets")
    op.drop_table("od_datasets")
