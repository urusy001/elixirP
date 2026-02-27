"""added premium until

Revision ID: 07397c2ca89e
Revises: 5710822b18aa
Create Date: 2025-12-17 23:23:09.664018

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


                                        
revision: str = '07397c2ca89e'
down_revision: Union[str, Sequence[str], None] = '5710822b18aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
                                                                 
    op.alter_column('carts', 'yandex_request_id',
               existing_type=sa.BIGINT(),
               type_=sa.String(),
               existing_nullable=True)
                                  


def downgrade() -> None:
    """Downgrade schema."""
                                                                 
    op.alter_column('carts', 'yandex_request_id',
               existing_type=sa.String(),
               type_=sa.BIGINT(),
               existing_nullable=True)
                                  
