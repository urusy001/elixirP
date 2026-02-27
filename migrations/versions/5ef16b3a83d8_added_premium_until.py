"""added premium until

Revision ID: 5ef16b3a83d8
Revises: 07397c2ca89e
Create Date: 2025-12-18 15:27:23.452289

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


                                        
revision: str = '5ef16b3a83d8'
down_revision: Union[str, Sequence[str], None] = '07397c2ca89e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
                                                                 
    op.add_column('carts', sa.Column('status', sa.String(), nullable=True))
                                  


def downgrade() -> None:
    """Downgrade schema."""
                                                                 
    op.drop_column('carts', 'status')
                                  
