from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Double, String, func, literal
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.tg_methods import normalize_phone
from src.webapp.database import Base


class User(Base):
    __tablename__ = "users"

    tg_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True, autoincrement=False)
    tg_ref_id: Mapped[int | None] = mapped_column(BigInteger, index=True, autoincrement=False, nullable=True, default=None)
    tg_phone: Mapped[str | None] = mapped_column(String, nullable=True, index=True, default=None)
    photo_url: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    name: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    surname: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    email: Mapped[str | None] = mapped_column(String, unique=True, nullable=True, default=None)
    phone: Mapped[str | None] = mapped_column(String, unique=True, nullable=True, default=None)
    premium_requests: Mapped[float] = mapped_column(Double, nullable=False, default=0)
    premium_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    thread_id: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    input_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    carts: Mapped[list["Cart"]] = relationship("Cart", back_populates="user", cascade="all, delete-orphan")
    favourites: Mapped[list["Favourite"]] = relationship("Favourite", back_populates="user", cascade="all, delete-orphan")
    token_usage: Mapped[list["UserTokenUsage"]] = relationship("UserTokenUsage", back_populates="user")

    @hybrid_property
    def full_name(self) -> str:
        n = (self.name or "").strip()
        s = (self.surname or "").strip()
        full = f"{n} {s}".strip()
        return full or "Без имени"

    @full_name.expression
    def full_name(cls):
        full = func.trim(func.concat(func.coalesce(cls.name, ""), literal(" "), func.coalesce(cls.surname, "")))
        return func.coalesce(func.nullif(full, ""), literal("Без имени"))

    @property
    def contact_info(self) -> str: return f"ID ТГ: {self.tg_id}, Номер ТГ: {normalize_phone(self.tg_phone) if self.tg_phone else 'Отсутствует'}, Почта: {self.email or 'Отсутствует'}, Номер телефона для покупок: {normalize_phone(self.phone) if self.phone else 'Отсутствует'}"
