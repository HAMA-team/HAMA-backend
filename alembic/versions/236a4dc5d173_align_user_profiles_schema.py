"""align_user_profiles_schema

Revision ID: 236a4dc5d173
Revises: 1b4c9dc1c3bf
Create Date: 2025-10-26 21:51:29.283984

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "236a4dc5d173"
down_revision = "1b4c9dc1c3bf"
branch_labels = None
depends_on = None


NEW_COLUMNS = [
    ("expertise_level", sa.Column("expertise_level", sa.String(length=50), nullable=False, server_default="intermediate")),
    ("investment_style", sa.Column("investment_style", sa.String(length=50), nullable=False, server_default="moderate")),
    ("risk_tolerance", sa.Column("risk_tolerance", sa.String(length=50), nullable=False, server_default="medium")),
    ("avg_trades_per_day", sa.Column("avg_trades_per_day", sa.Float(), nullable=True, server_default=text("1.0"))),
    ("preferred_sectors", sa.Column("preferred_sectors", sa.JSON(), nullable=True, server_default=text("'[]'::jsonb"))),
    ("trading_style", sa.Column("trading_style", sa.String(length=50), nullable=True, server_default="long_term")),
    ("portfolio_concentration", sa.Column("portfolio_concentration", sa.Float(), nullable=True, server_default=text("0.5"))),
    ("technical_level", sa.Column("technical_level", sa.String(length=50), nullable=False, server_default="intermediate")),
    ("preferred_depth", sa.Column("preferred_depth", sa.String(length=50), nullable=False, server_default="detailed")),
    ("wants_explanations", sa.Column("wants_explanations", sa.Boolean(), nullable=False, server_default=sa.text("true"))),
    ("wants_analogies", sa.Column("wants_analogies", sa.Boolean(), nullable=False, server_default=sa.text("false"))),
    ("llm_generated_profile", sa.Column("llm_generated_profile", sa.String(), nullable=True)),
    ("created_at", sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"))),
    ("last_updated", sa.Column("last_updated", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"))),
]


def _create_latest_user_profiles_table() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("expertise_level", sa.String(length=50), nullable=False, server_default="intermediate"),
        sa.Column("investment_style", sa.String(length=50), nullable=False, server_default="moderate"),
        sa.Column("risk_tolerance", sa.String(length=50), nullable=False, server_default="medium"),
        sa.Column("avg_trades_per_day", sa.Float(), nullable=True, server_default=text("1.0")),
        sa.Column("preferred_sectors", sa.JSON(), nullable=True, server_default=text("'[]'::jsonb")),
        sa.Column("trading_style", sa.String(length=50), nullable=True, server_default="long_term"),
        sa.Column("portfolio_concentration", sa.Float(), nullable=True, server_default=text("0.5")),
        sa.Column("technical_level", sa.String(length=50), nullable=False, server_default="intermediate"),
        sa.Column("preferred_depth", sa.String(length=50), nullable=False, server_default="detailed"),
        sa.Column("wants_explanations", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("wants_analogies", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("llm_generated_profile", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("last_updated", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()

    if "user_profiles" not in tables:
        _create_latest_user_profiles_table()
        return

    columns = {col["name"] for col in inspector.get_columns("user_profiles")}

    # Already migrated table: ensure any missing columns are added
    if "expertise_level" in columns:
        for name, column in NEW_COLUMNS:
            if name not in columns:
                op.add_column("user_profiles", column.copy())
        # Remove legacy columns if they linger
        legacy_columns = {
            "profile_id",
            "investment_goal",
            "investment_horizon",
            "automation_level",
            "initial_capital",
            "monthly_contribution",
            "max_single_stock_ratio",
            "max_sector_ratio",
            "updated_at",
        }
        for legacy in legacy_columns & columns:
            op.drop_column("user_profiles", legacy)
        return

    # Legacy schema detected → migrate data
    op.rename_table("user_profiles", "user_profiles_legacy")
    _create_latest_user_profiles_table()

    op.execute(
        """
        INSERT INTO user_profiles (
            user_id,
            expertise_level,
            investment_style,
            risk_tolerance,
            avg_trades_per_day,
            preferred_sectors,
            trading_style,
            portfolio_concentration,
            technical_level,
            preferred_depth,
            wants_explanations,
            wants_analogies,
            llm_generated_profile,
            created_at,
            last_updated
        )
        SELECT
            legacy.user_id,
            'intermediate'::varchar(50) AS expertise_level,
            CASE
                WHEN legacy.investment_goal ILIKE '%growth%' OR legacy.investment_goal ILIKE '%aggressive%' THEN 'aggressive'
                WHEN legacy.investment_goal ILIKE '%income%' OR legacy.investment_goal ILIKE '%conservative%' THEN 'conservative'
                WHEN legacy.investment_goal ILIKE '%balanced%' OR legacy.investment_goal ILIKE '%moderate%' THEN 'moderate'
                WHEN legacy.investment_goal IS NULL OR legacy.investment_goal = '' THEN 'moderate'
                ELSE 'moderate'
            END AS investment_style,
            COALESCE(NULLIF(legacy.risk_tolerance, ''), 'medium') AS risk_tolerance,
            1.0 AS avg_trades_per_day,
            '[]'::jsonb AS preferred_sectors,
            CASE
                WHEN legacy.investment_horizon ILIKE '%short%' THEN 'short_term'
                WHEN legacy.investment_horizon ILIKE '%mid%' OR legacy.investment_horizon ILIKE '%medium%' THEN 'long_term'
                WHEN legacy.investment_horizon ILIKE '%long%' THEN 'long_term'
                ELSE 'long_term'
            END AS trading_style,
            COALESCE(legacy.max_single_stock_ratio::double precision, 0.5) AS portfolio_concentration,
            'intermediate'::varchar(50) AS technical_level,
            'detailed'::varchar(50) AS preferred_depth,
            true AS wants_explanations,
            false AS wants_analogies,
            NULL::varchar AS llm_generated_profile,
            COALESCE(legacy.created_at, timezone('utc', now())) AS created_at,
            COALESCE(legacy.updated_at, legacy.created_at, timezone('utc', now())) AS last_updated
        FROM user_profiles_legacy AS legacy
        ON CONFLICT (user_id) DO NOTHING
        """
    )

    op.drop_table("user_profiles_legacy")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()

    if "user_profiles" not in tables:
        return

    columns = {col["name"] for col in inspector.get_columns("user_profiles")}

    if "profile_id" in columns and "investment_goal" in columns:
        # Already downgraded schema
        return

    op.rename_table("user_profiles", "user_profiles_new")
    op.create_table(
        "user_profiles",
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("risk_tolerance", sa.String(length=20)),
        sa.Column("investment_goal", sa.String(length=50)),
        sa.Column("investment_horizon", sa.String(length=20)),
        sa.Column("automation_level", sa.Integer()),
        sa.Column("initial_capital", sa.Numeric(15, 2)),
        sa.Column("monthly_contribution", sa.Numeric(15, 2)),
        sa.Column("max_single_stock_ratio", sa.Numeric(5, 4)),
        sa.Column("max_sector_ratio", sa.Numeric(5, 4)),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )

    op.execute(
        """
        INSERT INTO user_profiles (
            profile_id,
            user_id,
            risk_tolerance,
            investment_goal,
            investment_horizon,
            automation_level,
            initial_capital,
            monthly_contribution,
            max_single_stock_ratio,
            max_sector_ratio,
            created_at,
            updated_at
        )
        SELECT
            new.user_id AS profile_id,
            new.user_id,
            new.risk_tolerance,
            CASE
                WHEN new.investment_style = 'aggressive' THEN 'growth'
                WHEN new.investment_style = 'conservative' THEN 'income'
                WHEN new.investment_style = 'moderate' THEN 'balanced'
                ELSE 'balanced'
            END,
            CASE
                WHEN new.trading_style = 'short_term' THEN 'short_term'
                ELSE 'long_term'
            END,
            2,
            NULL,
            NULL,
            new.portfolio_concentration,
            NULL,
            new.created_at,
            new.last_updated
        FROM user_profiles_new AS new
        ON CONFLICT (user_id) DO NOTHING
        """
    )

    op.drop_table("user_profiles_new")
