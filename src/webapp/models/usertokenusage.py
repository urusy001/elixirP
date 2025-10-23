from datetime import date
from sqlalchemy import Column, BigInteger, Date, Float, ForeignKey
from sqlalchemy.orm import relationship, validates
from src.webapp.database import Base


class UserTokenUsage(Base):
    __tablename__ = "user_token_usage"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.tg_id", ondelete="CASCADE"), index=True)

    date = Column(Date, index=True, default=date.today)

    # Token counts
    input_tokens = Column(BigInteger, default=0)
    output_tokens = Column(BigInteger, default=0)

    # Calculated automatically
    input_cost_usd = Column(Float, default=0.0)
    output_cost_usd = Column(Float, default=0.0)

    user = relationship("User", backref="token_usage")

    # --- Constants for pricing ---
    INPUT_RATE_FRESH = 0.4 / 1_000_000
    INPUT_RATE_CACHED = 0.1 / 1_000_000
    OUTPUT_RATE = 1.6 / 1_000_000
    CACHED_RATIO = 0.15  # 15% cached

    @validates("input_tokens")
    def _calculate_input_cost(self, key, value):
        """Automatically compute input cost whenever input_tokens changes."""
        fresh = value * (1 - self.CACHED_RATIO)
        cached = value * self.CACHED_RATIO
        self.input_cost_usd = round(fresh * self.INPUT_RATE_FRESH + cached * self.INPUT_RATE_CACHED, 6)
        return value

    @validates("output_tokens")
    def _calculate_output_cost(self, key, value):
        """Automatically compute output cost whenever output_tokens changes."""
        self.output_cost_usd = round(value * self.OUTPUT_RATE, 6)
        return value