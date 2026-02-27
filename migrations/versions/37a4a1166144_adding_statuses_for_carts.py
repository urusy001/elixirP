"""adding statuses for carts

Revision ID: 37a4a1166144
Revises: 840930dda000
Create Date: 2026-01-14 14:09:22.297203

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


                                        
revision: str = '37a4a1166144'
down_revision: Union[str, Sequence[str], None] = '840930dda000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
                                                                 
    op.add_column('carts', sa.Column('promo_gains', sa.Numeric(precision=8, scale=2), server_default='0', nullable=False))
    op.add_column('carts', sa.Column('is_paid', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('carts', sa.Column('is_canceled', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('carts', sa.Column('is_shipped', sa.Boolean(), server_default='false', nullable=False))
    op.create_index(op.f('ix_carts_is_canceled'), 'carts', ['is_canceled'], unique=False)
    op.create_index(op.f('ix_carts_is_paid'), 'carts', ['is_paid'], unique=False)
    op.create_index(op.f('ix_carts_is_shipped'), 'carts', ['is_shipped'], unique=False)
                                  


def downgrade() -> None:
    """Downgrade schema."""
                                                                 
    op.drop_index(op.f('ix_carts_is_shipped'), table_name='carts')
    op.drop_index(op.f('ix_carts_is_paid'), table_name='carts')
    op.drop_index(op.f('ix_carts_is_canceled'), table_name='carts')
    op.drop_column('carts', 'is_shipped')
    op.drop_column('carts', 'is_canceled')
    op.drop_column('carts', 'is_paid')
    op.drop_column('carts', 'promo_gains')
                                  
