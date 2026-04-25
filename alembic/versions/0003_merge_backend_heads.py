"""merge control-plane and metadata heads

Revision ID: 0003_merge_backend_heads
Revises: 0001_control_plane_mvp, 0002_metadata_compat
Create Date: 2026-04-24
"""

from __future__ import annotations

revision = "0003_merge_backend_heads"
down_revision = ("0001_control_plane_mvp", "0002_metadata_compat")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
