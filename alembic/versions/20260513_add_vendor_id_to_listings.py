"""add vendors and vendor relationships

Revision ID: 20260513_add_vendor_id_to_listings
Revises: 20260430_refactor_wishlist_for_multi_item_support, 20260502_add_structured_package_fields
Create Date: 2026-05-13 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260513_add_vendor_id_to_listings"
down_revision = (
    "20260430_refactor_wishlist_for_multi_item_support",
    "20260502_add_structured_package_fields",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "vendors" not in tables:
        op.create_table(
            "vendors",
            sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("email", sa.String(), nullable=False),
            sa.Column("phone", sa.String(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("contact_person", sa.String(), nullable=True),
            sa.Column("address", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email", name="uq_vendors_email"),
        )
        op.create_index("ix_vendors_id", "vendors", ["id"])
        op.create_index("ix_vendors_name", "vendors", ["name"])
        op.create_index("ix_vendors_email", "vendors", ["email"], unique=True)

    listing_columns = {column["name"] for column in inspector.get_columns("listings")}
    if "vendor_id" not in listing_columns:
        op.add_column("listings", sa.Column("vendor_id", sa.UUID(as_uuid=True), nullable=True))
        op.create_index("ix_listings_vendor_id", "listings", ["vendor_id"])
        op.create_foreign_key(
            "fk_listings_vendor_id",
            "listings",
            "vendors",
            ["vendor_id"],
            ["id"],
        )

    package_columns = {column["name"] for column in inspector.get_columns("Packages")}
    if "vendor_id" not in package_columns:
        op.add_column("Packages", sa.Column("vendor_id", sa.UUID(as_uuid=True), nullable=True))
        op.create_index("ix_Packages_vendor_id", "Packages", ["vendor_id"])
        op.create_foreign_key(
            "fk_packages_vendor_id",
            "Packages",
            "vendors",
            ["vendor_id"],
            ["id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "Packages" in tables:
        package_columns = {column["name"] for column in inspector.get_columns("Packages")}
        if "vendor_id" in package_columns:
            op.drop_constraint("fk_packages_vendor_id", "Packages", type_="foreignkey")
            op.drop_index("ix_Packages_vendor_id", table_name="Packages")
            op.drop_column("Packages", "vendor_id")

    if "listings" in tables:
        listing_columns = {column["name"] for column in inspector.get_columns("listings")}
        if "vendor_id" in listing_columns:
            op.drop_constraint("fk_listings_vendor_id", "listings", type_="foreignkey")
            op.drop_index("ix_listings_vendor_id", table_name="listings")
            op.drop_column("listings", "vendor_id")

    if "vendors" in tables:
        op.drop_index("ix_vendors_email", table_name="vendors")
        op.drop_index("ix_vendors_name", table_name="vendors")
        op.drop_index("ix_vendors_id", table_name="vendors")
        op.drop_table("vendors")
