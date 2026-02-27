"""added used code

Revision ID: d65678384de8
Revises: 0265d09edf20
Create Date: 2025-12-16 21:01:33.661361

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


                                        
revision: str = 'd65678384de8'
down_revision: Union[str, Sequence[str], None] = '0265d09edf20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
                                                                 
    op.create_table('used_codes',
    sa.Column('id', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('code', sa.String(), nullable=False),
    sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.tg_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code', name='uq_used_codes_code')
    )
    op.create_index(op.f('ix_used_codes_code'), 'used_codes', ['code'], unique=False)
    op.create_index(op.f('ix_used_codes_id'), 'used_codes', ['id'], unique=False)
    op.create_index(op.f('ix_used_codes_user_id'), 'used_codes', ['user_id'], unique=False)
    op.create_index('ix_used_codes_user_id_code', 'used_codes', ['user_id', 'code'], unique=False)
                                  


def downgrade() -> None:
    """Downgrade schema."""
                                                                 
    op.drop_index('ix_used_codes_user_id_code', table_name='used_codes')
    op.drop_index(op.f('ix_used_codes_user_id'), table_name='used_codes')
    op.drop_index(op.f('ix_used_codes_id'), table_name='used_codes')
    op.drop_index(op.f('ix_used_codes_code'), table_name='used_codes')
    op.drop_table('used_codes')
                                  
