"""remove_automation_level_from_approval_requests

Revision ID: 042be39878e7
Revises: a5a9b52dd593
Create Date: 2025-11-16 00:48:45.406126

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '042be39878e7'
down_revision = 'a5a9b52dd593'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ApprovalRequest 테이블에서 automation_level 컬럼 제거
    op.drop_column('approval_requests', 'automation_level')


def downgrade() -> None:
    # 롤백 시 automation_level 컬럼 복원
    op.add_column('approval_requests',
        sa.Column('automation_level', sa.Integer(), nullable=True)
    )
