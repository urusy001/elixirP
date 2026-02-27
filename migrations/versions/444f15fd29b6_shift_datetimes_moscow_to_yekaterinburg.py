"""shift_datetimes_moscow_to_yekaterinburg

Revision ID: 444f15fd29b6
Revises: a79ceada2105
Create Date: 2026-02-15 15:40:52.080288

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


                                        
revision: str = '444f15fd29b6'
down_revision: Union[str, Sequence[str], None] = 'a79ceada2105'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DATETIME_COLUMNS: dict[str, tuple[str, ...]] = {
    "users": ("premium_until", "blocked_until"),
    "carts": ("created_at", "updated_at"),
    "cart_items": ("created_at", "updated_at"),
    "tg_categories": ("created_at", "updated_at"),
    "promo_codes": ("created_at", "updated_at"),
}


def _shift_datetime_columns(hours: int) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name, columns in _DATETIME_COLUMNS.items():
        if not inspector.has_table(table_name):
            continue

        existing_columns = {col["name"] for col in inspector.get_columns(table_name)}
        for column_name in columns:
            if column_name not in existing_columns:
                continue

            op.execute(
                sa.text(
                    f'''
                    UPDATE "{table_name}"
                    SET "{column_name}" = "{column_name}" + (:hours * INTERVAL '1 hour')
                    WHERE "{column_name}" IS NOT NULL
                    '''
                ).bindparams(hours=hours)
            )


def upgrade() -> None:
    """Upgrade schema."""
                                                          
    _shift_datetime_columns(hours=2)


def downgrade() -> None:
    """Downgrade schema."""
    _shift_datetime_columns(hours=-2)
