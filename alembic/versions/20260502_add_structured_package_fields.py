"""add structured package fields

Revision ID: 20260502_add_structured_package_fields
Revises: 20260402_add_listing_coordinates
Create Date: 2026-05-02 00:00:00

This revision is stamped in deployed databases but was missing locally. The
operations are guarded so existing databases can continue while fresh or
partially migrated databases still receive the package columns used by the app.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260502_add_structured_package_fields"
down_revision = "20260402_add_listing_coordinates"
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, existing_columns: set[str], column: sa.Column) -> None:
    if column.name not in existing_columns:
        op.add_column(table_name, column)
        existing_columns.add(column.name)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "Packages" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("Packages")}
    _add_column_if_missing("Packages", columns, sa.Column("summary", sa.Text(), nullable=True))
    _add_column_if_missing("Packages", columns, sa.Column("nights", sa.Integer(), nullable=True))
    _add_column_if_missing("Packages", columns, sa.Column("trip_style", sa.String(), nullable=True))
    _add_column_if_missing("Packages", columns, sa.Column("start_location", sa.String(), nullable=True))
    _add_column_if_missing("Packages", columns, sa.Column("end_location", sa.String(), nullable=True))
    _add_column_if_missing("Packages", columns, sa.Column("destinations", sa.JSON(), nullable=True))
    _add_column_if_missing("Packages", columns, sa.Column("highlights", sa.JSON(), nullable=True))
    _add_column_if_missing("Packages", columns, sa.Column("exclusions", sa.JSON(), nullable=True))
    _add_column_if_missing("Packages", columns, sa.Column("quick_facts", sa.JSON(), nullable=True))
    _add_column_if_missing("Packages", columns, sa.Column("structured_itinerary", sa.JSON(), nullable=True))
    _add_column_if_missing("Packages", columns, sa.Column("listing_refs", sa.JSON(), nullable=True))

    if "media_assets" in tables and "cover_media_id" not in columns:
        op.add_column("Packages", sa.Column("cover_media_id", sa.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            "fk_packages_cover_media_id",
            "Packages",
            "media_assets",
            ["cover_media_id"],
            ["id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "Packages" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("Packages")}
    if "cover_media_id" in columns:
        op.drop_constraint("fk_packages_cover_media_id", "Packages", type_="foreignkey")
        op.drop_column("Packages", "cover_media_id")

    for column_name in (
        "listing_refs",
        "structured_itinerary",
        "quick_facts",
        "exclusions",
        "highlights",
        "destinations",
        "end_location",
        "start_location",
        "trip_style",
        "nights",
        "summary",
    ):
        if column_name in columns:
            op.drop_column("Packages", column_name)
