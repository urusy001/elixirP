"""changed80

Revision ID: 840930dda000
Revises: bdb39b3644a0
Create Date: 2026-01-04 02:44:43.911776

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


                                        
revision: str = '840930dda000'
down_revision: Union[str, Sequence[str], None] = 'bdb39b3644a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
                                                                 
    op.alter_column('promo_codes', 'code',
               existing_type=sa.VARCHAR(length=80),
               type_=sa.String(length=255),
               existing_nullable=False)
                                  


def downgrade() -> None:
    """Downgrade schema."""
                                                                 
    op.alter_column('promo_codes', 'code',
               existing_type=sa.String(length=255),
               type_=sa.VARCHAR(length=80),
               existing_nullable=False)
                                  
