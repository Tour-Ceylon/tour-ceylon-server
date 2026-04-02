"""add listing coordinates

Revision ID: 20260402_add_listing_coordinates
Revises:
Create Date: 2026-04-02 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260402_add_listing_coordinates"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("listings", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("listings", sa.Column("longitude", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("listings", "longitude")
    op.drop_column("listings", "latitude")
