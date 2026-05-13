"""restore wishlist refactor revision marker

Revision ID: 20260430_refactor_wishlist_for_multi_item_support
Revises: 20260402_add_listing_coordinates
Create Date: 2026-04-30 00:00:00

This revision is present in deployed databases, but the migration file was
missing from the repository. Keep it as a no-op bridge so Alembic can continue
from the deployed revision to newer schema changes.
"""


# revision identifiers, used by Alembic.
revision = "20260430_refactor_wishlist_for_multi_item_support"
down_revision = "20260402_add_listing_coordinates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
