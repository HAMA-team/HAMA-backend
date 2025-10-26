"""Add artifacts table

Revision ID: 44f8edc1fcd4
Revises: 236a4dc5d173
Create Date: 2025-10-27 01:34:31.670642

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '44f8edc1fcd4'
down_revision = '236a4dc5d173'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # artifacts 테이블 생성
    op.create_table(
        'artifacts',
        sa.Column('artifact_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('artifact_type', sa.String(length=50), nullable=False),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('preview', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=True),
        sa.Column('deleted_at', sa.TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint('artifact_id')
    )

    # 인덱스 생성
    op.create_index('ix_artifacts_user_id', 'artifacts', ['user_id'], unique=False)
    op.create_index('ix_artifacts_artifact_type', 'artifacts', ['artifact_type'], unique=False)
    op.create_index('ix_artifacts_created_at', 'artifacts', ['created_at'], unique=False)


def downgrade() -> None:
    # 인덱스 삭제
    op.drop_index('ix_artifacts_created_at', table_name='artifacts')
    op.drop_index('ix_artifacts_artifact_type', table_name='artifacts')
    op.drop_index('ix_artifacts_user_id', table_name='artifacts')

    # 테이블 삭제
    op.drop_table('artifacts')
