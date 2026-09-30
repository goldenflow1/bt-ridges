import sqlalchemy as sa
from alembic import op

revision = '0002_ready_jobs'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_jobs_ready', 'jobs', ['tenant_id', 'created_at', 'id'],
                    postgresql_where=sa.text("status = 'waiting' AND deleted_at IS NULL"))


def downgrade():
    op.drop_index('ix_jobs_ready', table_name='jobs')
