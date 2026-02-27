"""added promo_discount_pct

Revision ID: d878ab301493
Revises: e325df90d2cc
Create Date: 2025-12-20 18:33:34.342317

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


                                        
revision: str = 'd878ab301493'
down_revision: Union[str, Sequence[str], None] = 'e325df90d2cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
                                                                 
    op.add_column('promo_codes', sa.Column('discount_pct', sa.Numeric(precision=5, scale=2), server_default='0', nullable=False))
                                  


def downgrade() -> None:
    """Downgrade schema."""
                                                                 
    op.drop_column('promo_codes', 'discount_pct')
                                  
