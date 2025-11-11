"""Remove automation_level column from chat_sessions

Revision ID: a5a9b52dd593
Revises: 44f8edc1fcd4
Create Date: 2025-11-09 18:44:47.241719

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a5a9b52dd593'
down_revision = '44f8edc1fcd4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    automation_level 컬럼 제거

    hitl_config로 완전히 전환되었으므로 레거시 automation_level 컬럼을 삭제합니다.
    """
    # automation_level 컬럼 제거
    op.drop_column('chat_sessions', 'automation_level')


def downgrade() -> None:
    """
    automation_level 컬럼 복구 (롤백용)

    문제 발생 시 이전 상태로 복구합니다.
    """
    # automation_level 컬럼 재추가 (기본값: 2 = Copilot)
    op.add_column(
        'chat_sessions',
        sa.Column('automation_level', sa.Integer(), nullable=False, server_default='2')
    )
