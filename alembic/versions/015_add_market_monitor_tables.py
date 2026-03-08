"""Add market monitor tables

Revision ID: 015_add_market_monitor_tables
Revises: 014_add_portfolio_models
Create Date: 2026-03-07 12:00:00.000000

This migration adds two tables for market breadth monitoring:
1. monitor_universe - Tracked symbols with metadata (sector, industry, market cap)
2. breadth_snapshots - Daily breadth scan results stored as JSONB
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "015_add_market_monitor_tables"
down_revision = "014_add_portfolio_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create market monitor tables."""

    # Create monitor_universe table
    op.create_table(
        "monitor_universe",
        sa.Column("symbol", sa.String(10), primary_key=True),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("market_cap", sa.BigInteger, nullable=True),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("industry", sa.String(200), nullable=True),
        sa.Column(
            "refreshed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # Create indexes on monitor_universe
    op.create_index("idx_monitor_universe_sector", "monitor_universe", ["sector"])
    op.create_index(
        "idx_monitor_universe_market_cap", "monitor_universe", ["market_cap"]
    )

    # Create breadth_snapshots table
    op.create_table(
        "breadth_snapshots",
        sa.Column("date", sa.Date, primary_key=True),
        sa.Column(
            "universe",
            sa.String(50),
            nullable=False,
            server_default="large_cap_1b",
        ),
        sa.Column("scans", postgresql.JSONB, nullable=False),
        sa.Column("theme_tracker", postgresql.JSONB, nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    """Drop market monitor tables."""
    op.drop_table("breadth_snapshots")
    op.drop_table("monitor_universe")
