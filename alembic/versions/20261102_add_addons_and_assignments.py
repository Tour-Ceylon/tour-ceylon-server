"""add listing_addons and inquiry_assignments

Revision ID: 20261102_addons_assignments
Revises: 20261102_inquiry_payment_method
Create Date: 2026-11-02 00:10:00
"""

from alembic import op
import sqlalchemy as sa

revision = "20261102_addons_assignments"
down_revision = "20261102_inquiry_payment_method"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "listing_addons",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("listing_id", sa.Uuid(as_uuid=True), sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("room_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("base_currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_listing_addons_listing_id", "listing_addons", ["listing_id"])

    op.create_table(
        "inquiry_assignments",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("inquiry_id", sa.Uuid(as_uuid=True), sa.ForeignKey("booking_inquiries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assignee_type", sa.String(10), nullable=False),
        sa.Column("driver_id", sa.Uuid(as_uuid=True), sa.ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("guide_name", sa.String(150), nullable=True),
        sa.Column("guide_phone", sa.String(40), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="assigned"),
        sa.Column("assigned_by", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("assignee_type IN ('guide', 'driver')", name="ck_inquiry_assignments_type"),
        sa.CheckConstraint("status IN ('assigned', 'cancelled')", name="ck_inquiry_assignments_status"),
        sa.CheckConstraint(
            "(assignee_type = 'driver' AND driver_id IS NOT NULL) OR (assignee_type = 'guide' AND guide_name IS NOT NULL)",
            name="ck_inquiry_assignments_assignee",
        ),
    )
    op.create_index("ix_inquiry_assignments_inquiry_id", "inquiry_assignments", ["inquiry_id"])
    op.create_index("ix_inquiry_assignments_driver_id", "inquiry_assignments", ["driver_id"])
    op.create_index("ix_inquiry_assignments_status", "inquiry_assignments", ["status"])


def downgrade() -> None:
    op.drop_table("inquiry_assignments")
    op.drop_table("listing_addons")
