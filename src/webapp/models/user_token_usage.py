from datetime import date as dt_date
from enum import Enum
from sqlalchemy import BigInteger, Date, Enum as SAEnum, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from src.webapp.database import Base


class BotEnum(str, Enum):
    dose = "dose"
    professor = "professor"
    new = "new"


class UserTokenUsage(Base):
    __tablename__ = "user_token_usage"
    __table_args__ = (UniqueConstraint("user_id", "date", "bot", name="uq_user_date_bot"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.tg_id", ondelete="CASCADE"), index=True)
    date: Mapped[dt_date] = mapped_column(Date, index=True, default=dt_date.today)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    input_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    output_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    total_requests: Mapped[int] = mapped_column(BigInteger, default=0)
    bot: Mapped[BotEnum] = mapped_column(SAEnum(BotEnum, name="bot_enum"), index=True, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="token_usage")

    INPUT_RATE_FRESH = 0.4 / 1_000_000
    INPUT_RATE_CACHED = 0.1 / 1_000_000
    OUTPUT_RATE = 1.6 / 1_000_000
    CACHED_RATIO = 0.15

    @validates("input_tokens")
    def _calculate_input_cost(self, key: str, value: int) -> int:
        fresh = value * (1 - self.CACHED_RATIO)
        cached = value * self.CACHED_RATIO
        self.input_cost_usd = round(fresh * self.INPUT_RATE_FRESH + cached * self.INPUT_RATE_CACHED, 6)
        return value

    @validates("output_tokens")
    def _calculate_output_cost(self, key: str, value: int) -> int:
        self.output_cost_usd = round(value * self.OUTPUT_RATE, 6)
        return value
