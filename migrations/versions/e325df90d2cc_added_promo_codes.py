"""added promo_codes

Revision ID: e325df90d2cc
Revises: 5ef16b3a83d8
Create Date: 2025-12-20 18:23:44.784525

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


                                        
revision: str = 'e325df90d2cc'
down_revision: Union[str, Sequence[str], None] = '5ef16b3a83d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
                                                                 
    op.create_table('promo_codes',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('code', sa.String(length=80), nullable=False),
    sa.Column('owner_name', sa.String(length=255), nullable=False),
    sa.Column('owner_pct', sa.Numeric(precision=5, scale=2), server_default='0', nullable=False),
    sa.Column('owner_amount_gained', sa.Numeric(precision=14, scale=2), server_default='0', nullable=False),
    sa.Column('lvl1_name', sa.String(length=255), nullable=True),
    sa.Column('lvl1_pct', sa.Numeric(precision=5, scale=2), server_default='0', nullable=False),
    sa.Column('lvl1_amount_gained', sa.Numeric(precision=14, scale=2), server_default='0', nullable=False),
    sa.Column('lvl2_name', sa.String(length=255), nullable=True),
    sa.Column('lvl2_pct', sa.Numeric(precision=5, scale=2), server_default='0', nullable=False),
    sa.Column('lvl2_amount_gained', sa.Numeric(precision=14, scale=2), server_default='0', nullable=False),
    sa.Column('times_used', sa.Integer(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('lvl1_amount_gained >= 0', name='ck_lvl1_amount_nonneg'),
    sa.CheckConstraint('lvl1_pct >= 0 AND lvl1_pct <= 100', name='ck_lvl1_pct_0_100'),
    sa.CheckConstraint('lvl2_amount_gained >= 0', name='ck_lvl2_amount_nonneg'),
    sa.CheckConstraint('lvl2_pct >= 0 AND lvl2_pct <= 100', name='ck_lvl2_pct_0_100'),
    sa.CheckConstraint('owner_amount_gained >= 0', name='ck_owner_amount_nonneg'),
    sa.CheckConstraint('owner_pct >= 0 AND owner_pct <= 100', name='ck_owner_pct_0_100'),
    sa.CheckConstraint('times_used >= 0', name='ck_promo_times_used_nonneg'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_promo_codes_code'), 'promo_codes', ['code'], unique=True)
    op.create_index(op.f('ix_promo_codes_lvl1_name'), 'promo_codes', ['lvl1_name'], unique=False)
    op.create_index(op.f('ix_promo_codes_lvl2_name'), 'promo_codes', ['lvl2_name'], unique=False)
    op.create_index(op.f('ix_promo_codes_owner_name'), 'promo_codes', ['owner_name'], unique=False)
    op.create_index('ix_promo_owner_levels', 'promo_codes', ['owner_name', 'lvl1_name', 'lvl2_name'], unique=False)
    op.add_column('carts', sa.Column('promo_code', sa.String(length=80), nullable=True))
    op.create_index(op.f('ix_carts_promo_code'), 'carts', ['promo_code'], unique=False)
    op.create_foreign_key(None, 'carts', 'promo_codes', ['promo_code'], ['code'], ondelete='SET NULL')
                                  


def downgrade() -> None:
    """Downgrade schema."""
                                                                 
    op.drop_constraint(None, 'carts', type_='foreignkey')
    op.drop_index(op.f('ix_carts_promo_code'), table_name='carts')
    op.drop_column('carts', 'promo_code')
    op.drop_index('ix_promo_owner_levels', table_name='promo_codes')
    op.drop_index(op.f('ix_promo_codes_owner_name'), table_name='promo_codes')
    op.drop_index(op.f('ix_promo_codes_lvl2_name'), table_name='promo_codes')
    op.drop_index(op.f('ix_promo_codes_lvl1_name'), table_name='promo_codes')
    op.drop_index(op.f('ix_promo_codes_code'), table_name='promo_codes')
    op.drop_table('promo_codes')
                                  
