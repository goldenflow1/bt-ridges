"""Alembic revision entrypoint; implementation lives beside env.py."""
from migrations.ready_jobs import (
    branch_labels,
    depends_on,
    down_revision,
    downgrade,
    revision,
    upgrade,
)

__all__ = ["branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade"]
