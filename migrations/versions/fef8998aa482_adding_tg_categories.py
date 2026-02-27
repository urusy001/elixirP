"""adding tg categories

Revision ID: fef8998aa482
Revises: bb2251f3cc81
Create Date: 2025-12-16 18:42:19.741696

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


                                        
revision: str = 'fef8998aa482'
down_revision: Union[str, Sequence[str], None] = 'bb2251f3cc81'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
                                                                 
    pass
                                  


def downgrade() -> None:
    """Downgrade schema."""
                                                                 
    pass
                                  
