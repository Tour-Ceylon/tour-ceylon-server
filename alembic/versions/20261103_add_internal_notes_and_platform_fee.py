"""add booking_inquiries.internal_notes and AdminSettings.platform_fee_percent

Revision ID: 20261103_notes_fee
Revises: 20261102_addons_assignments
Create Date: 2026-11-03 00:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "20261103_notes_fee"
down_revision = "20261102_addons_assignments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("booking_inquiries", sa.Column("internal_notes", sa.Text, nullable=True))
    op.add_column("AdminSettings", sa.Column("platform_fee_percent", sa.Numeric(5, 2), nullable=False, server_default="15"))


def downgrade() -> None:
    op.drop_column("AdminSettings", "platform_fee_percent")
    op.drop_column("booking_inquiries", "internal_notes")
