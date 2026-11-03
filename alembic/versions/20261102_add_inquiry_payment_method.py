"""add booking_inquiries.payment_method

Revision ID: 20261102_inquiry_payment_method
Revises: 20261031_add_payments
Create Date: 2026-11-02 00:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "20261102_inquiry_payment_method"
down_revision = "20261031_add_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("booking_inquiries", sa.Column("payment_method", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("booking_inquiries", "payment_method")
