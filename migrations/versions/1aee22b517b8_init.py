from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '1aee22b517b8'
down_revision = None  # or your previous head if not first
branch_labels = None
depends_on = None

ENUM_NAME = 'bot_enum'
TABLE = 'user_token_usage'
COL = 'bot'
UC_NAME = 'uq_user_date_bot'
IX_NAME = 'ix_user_token_usage_bot'

def upgrade():
    bind = op.get_bind()

    # 1) Create enum type (idempotent)
    bot_enum = postgresql.ENUM('dose', 'professor', 'new', name=ENUM_NAME)
    bot_enum.create(bind, checkfirst=True)

    # 2) Add column as nullable first (so we can backfill)
    op.add_column(
        TABLE,
        sa.Column(COL, sa.Enum(name=ENUM_NAME), nullable=True)
    )

    # 3) Backfill existing rows to 'professor'
    op.execute(f"UPDATE {TABLE} SET {COL} = 'professor' WHERE {COL} IS NULL")

    # 3.1) (Optional) Deduplicate before unique constraint if you might have multiple rows per (user_id,date)
    # op.execute(\"\"\"
    # WITH grouped AS (
    #   SELECT
    #     MIN(id) AS keep_id,
    #     user_id, date, bot,
    #     SUM(input_tokens) AS sum_in,
    #     SUM(output_tokens) AS sum_out,
    #     SUM(input_cost_usd) AS sum_in_cost,
    #     SUM(output_cost_usd) AS sum_out_cost
    #   FROM user_token_usage
    #   GROUP BY user_id, date, bot
    #   HAVING COUNT(*) > 1
    # )
    # UPDATE user_token_usage u
    # SET input_tokens = g.sum_in,
    #     output_tokens = g.sum_out,
    #     input_cost_usd = g.sum_in_cost,
    #     output_cost_usd = g.sum_out_cost
    # FROM grouped g
    # WHERE u.id = g.keep_id;
    # DELETE FROM user_token_usage u
    # USING (
    #   SELECT user_id, date, bot, MIN(id) AS keep_id
    #   FROM user_token_usage
    #   GROUP BY user_id, date, bot
    # ) keep
    # WHERE u.user_id = keep.user_id AND u.date = keep.date AND u.bot = keep.bot AND u.id <> keep.keep_id;
    # \"\"\")

    # 4) Make column NOT NULL
    op.alter_column(TABLE, COL, existing_type=sa.Enum(name=ENUM_NAME), nullable=False)

    # 5) Index + unique constraint
    op.create_index(IX_NAME, TABLE, [COL])
    op.create_unique_constraint(UC_NAME, TABLE, ['user_id', 'date', COL])


def downgrade():
    # Reverse order: drop unique, index, column, enum type
    op.drop_constraint(UC_NAME, TABLE, type_='unique')
    op.drop_index(IX_NAME, table_name=TABLE)
    op.drop_column(TABLE, COL)

    bot_enum = postgresql.ENUM('dose', 'professor', 'new', name=ENUM_NAME)
    op.execute('DROP TYPE IF EXISTS ' + ENUM_NAME)