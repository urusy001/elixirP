"""added promo_gains

Revision ID: c4def29cb91a
Revises: fbd8b39a868e
Create Date: 2025-12-21 22:15:15.072162

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


                                        
revision: str = 'c4def29cb91a'
down_revision: Union[str, Sequence[str], None] = 'fbd8b39a868e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
                                                                 
    op.drop_constraint(op.f('product_tg_categories_tg_category_id_fkey'), 'product_tg_categories', type_='foreignkey')
    op.drop_constraint(op.f('product_tg_categories_product_onec_id_fkey'), 'product_tg_categories', type_='foreignkey')
    op.create_foreign_key(None, 'product_tg_categories', 'products', ['product_onec_id'], ['onec_id'], ondelete='RESTRICT')
    op.create_foreign_key(None, 'product_tg_categories', 'tg_categories', ['tg_category_id'], ['id'], ondelete='RESTRICT')
                                  


def downgrade() -> None:
    """Downgrade schema."""
                                                                 
    op.drop_constraint(None, 'product_tg_categories', type_='foreignkey')
    op.drop_constraint(None, 'product_tg_categories', type_='foreignkey')
    op.create_foreign_key(op.f('product_tg_categories_product_onec_id_fkey'), 'product_tg_categories', 'products', ['product_onec_id'], ['onec_id'], ondelete='CASCADE')
    op.create_foreign_key(op.f('product_tg_categories_tg_category_id_fkey'), 'product_tg_categories', 'tg_categories', ['tg_category_id'], ['id'], ondelete='CASCADE')
                                  
