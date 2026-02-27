"""added premium until

Revision ID: 3289bacafc2b
Revises: d65678384de8
Create Date: 2025-12-17 14:57:53.086068

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


                                        
revision: str = '3289bacafc2b'
down_revision: Union[str, Sequence[str], None] = 'd65678384de8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
                                                                 
    op.add_column('users', sa.Column('premium_until', sa.DateTime(timezone=True), nullable=True))
                                  


def downgrade() -> None:
    """Downgrade schema."""
                                                                 
    op.drop_column('users', 'premium_until')
                                  
