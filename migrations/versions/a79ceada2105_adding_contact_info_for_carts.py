"""adding contact info for carts

Revision ID: a79ceada2105
Revises: 37a4a1166144
Create Date: 2026-01-24 17:05:53.998075
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a79ceada2105"
down_revision: Union[str, Sequence[str], None] = "37a4a1166144"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_STR = "Не указан"


def upgrade() -> None:
                                           
    op.add_column(
        "carts",
        sa.Column("phone", sa.String(), nullable=True, server_default=DEFAULT_STR),
    )
    op.add_column(
        "carts",
        sa.Column("email", sa.String(), nullable=True, server_default=DEFAULT_STR),
    )

                                                                           
                                                    
    op.execute(
        sa.text(
            """
            UPDATE carts c
            SET
                phone = COALESCE(NULLIF(u.phone, ''), NULLIF(u.tg_phone, ''), :d),
                email = COALESCE(NULLIF(u.email, ''), :d)
            FROM users u
            WHERE u.tg_id = c.user_id
            """
        ).bindparams(sa.bindparam("d", DEFAULT_STR))
    )

                                                                                    
    op.execute(
        sa.text(
            """
            UPDATE carts
            SET phone = COALESCE(phone, :d),
                email = COALESCE(email, :d)
            """
        ).bindparams(sa.bindparam("d", DEFAULT_STR))
    )

                                                            
    op.alter_column("carts", "phone", nullable=False, server_default=DEFAULT_STR)
    op.alter_column("carts", "email", nullable=False, server_default=DEFAULT_STR)


def downgrade() -> None:
    op.drop_column("carts", "email")
    op.drop_column("carts", "phone")