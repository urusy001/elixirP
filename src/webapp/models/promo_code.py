from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Numeric,
    func,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from src.webapp.database import Base


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # code is used as FK target from carts.promo_code
    code = Column(String(80), unique=True, index=True, nullable=False)

    # OWNER level
    owner_name = Column(String(255), nullable=False, index=True)
    owner_pct = Column(Numeric(5, 2), nullable=False, default=Decimal("0.00"), server_default="0")
    owner_amount_gained = Column(Numeric(14, 2), nullable=False, default=Decimal("0.00"), server_default="0")

    # LEVEL 1
    lvl1_name = Column(String(255), nullable=True, index=True)
    lvl1_pct = Column(Numeric(5, 2), nullable=False, default=Decimal("0.00"), server_default="0")
    lvl1_amount_gained = Column(Numeric(14, 2), nullable=False, default=Decimal("0.00"), server_default="0")

    # LEVEL 2
    lvl2_name = Column(String(255), nullable=True, index=True)
    lvl2_pct = Column(Numeric(5, 2), nullable=False, default=Decimal("0.00"), server_default="0")
    lvl2_amount_gained = Column(Numeric(14, 2), nullable=False, default=Decimal("0.00"), server_default="0")

    # times used
    times_used = Column(Integer, nullable=False, default=0, server_default="0")

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # reverse relationship (PromoCode -> many Carts)
    carts = relationship(
        "Cart",
        back_populates="promo",
        lazy="selectin",
        foreign_keys="Cart.promo_code",
    )

    __table_args__ = (
        CheckConstraint("times_used >= 0", name="ck_promo_times_used_nonneg"),

        CheckConstraint("owner_pct >= 0 AND owner_pct <= 100", name="ck_owner_pct_0_100"),
        CheckConstraint("lvl1_pct >= 0 AND lvl1_pct <= 100", name="ck_lvl1_pct_0_100"),
        CheckConstraint("lvl2_pct >= 0 AND lvl2_pct <= 100", name="ck_lvl2_pct_0_100"),

        CheckConstraint("owner_amount_gained >= 0", name="ck_owner_amount_nonneg"),
        CheckConstraint("lvl1_amount_gained >= 0", name="ck_lvl1_amount_nonneg"),
        CheckConstraint("lvl2_amount_gained >= 0", name="ck_lvl2_amount_nonneg"),

        Index("ix_promo_owner_levels", "owner_name", "lvl1_name", "lvl2_name"),
    )