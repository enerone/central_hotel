"""add check constraint promotions discount_type

Revision ID: 34fb410cf2d1
Revises: 3b4a25aa8d18
Create Date: 2026-03-15 15:12:43.122162

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '34fb410cf2d1'
down_revision: Union[str, Sequence[str], None] = '3b4a25aa8d18'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint(
        "ck_promotions_discount_type",
        "promotions",
        "discount_type IN ('percent', 'fixed')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_promotions_discount_type", "promotions", type_="check")
