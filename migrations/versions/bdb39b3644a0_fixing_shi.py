"""fixing shi

Revision ID: bdb39b3644a0
Revises: c4def29cb91a
Create Date: 2025-12-21 22:37:27.151140

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


                                        
revision: str = 'bdb39b3644a0'
down_revision: Union[str, Sequence[str], None] = 'c4def29cb91a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.drop_constraint(
        "product_tg_categories_product_onec_id_fkey",
        "product_tg_categories",
        type_="foreignkey",
    )
    op.drop_constraint(
        "product_tg_categories_tg_category_id_fkey",
        "product_tg_categories",
        type_="foreignkey",
    )

    op.create_foreign_key(
        "product_tg_categories_product_onec_id_fkey",
        "product_tg_categories",
        "products",
        ["product_onec_id"],
        ["onec_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "product_tg_categories_tg_category_id_fkey",
        "product_tg_categories",
        "tg_categories",
        ["tg_category_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade():
    op.drop_constraint(
        "product_tg_categories_product_onec_id_fkey",
        "product_tg_categories",
        type_="foreignkey",
    )
    op.drop_constraint(
        "product_tg_categories_tg_category_id_fkey",
        "product_tg_categories",
        type_="foreignkey",
    )

    op.create_foreign_key(
        "product_tg_categories_product_onec_id_fkey",
        "product_tg_categories",
        "products",
        ["product_onec_id"],
        ["onec_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "product_tg_categories_tg_category_id_fkey",
        "product_tg_categories",
        "tg_categories",
        ["tg_category_id"],
        ["id"],
        ondelete="CASCADE",
    )