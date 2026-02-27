"""xyz

Revision ID: 3fb5ec99b0c4
Revises: 
Create Date: 2025-12-16 13:15:40.310073

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


                                        
revision: str = '3fb5ec99b0c4'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
                                                                 
    op.alter_column('carts', 'name',
               existing_type=sa.VARCHAR(),
               nullable=True)
                                  


def downgrade() -> None:
    """Downgrade schema."""
                                                                 
    op.alter_column('carts', 'name',
               existing_type=sa.VARCHAR(),
               nullable=False)
                                  
