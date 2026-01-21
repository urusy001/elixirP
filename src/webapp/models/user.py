from sqlalchemy import Column, BigInteger, String, DateTime, Double, func
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from src.tg_methods import normalize_phone
from src.webapp.database import Base


class User(Base):
    __tablename__ = "users"

    tg_id = Column(BigInteger, primary_key=True, index=True, autoincrement=False)
    tg_ref_id = Column(BigInteger, index=True, autoincrement=False, nullable=True, default=None)
    tg_phone = Column(String, nullable=True, index=True, default=None)

    photo_url = Column(String, nullable=True, default=None)
    name = Column(String, nullable=True, default=None)
    surname = Column(String, nullable=True, default=None)
    email = Column(String, unique=True, nullable=True, default=None)
    phone = Column(String, unique=True, nullable=True, default=None)

    premium_requests = Column(Double, nullable=False, default=0)
    premium_until = Column(DateTime(timezone=True), nullable=True, default=None)

    thread_id = Column(String, nullable=True, default=None)
    input_tokens = Column(BigInteger, nullable=False, default=0)
    output_tokens = Column(BigInteger, nullable=False, default=0)

    # Blocking system
    blocked_until = Column(DateTime(timezone=True), nullable=True, default=None)

    carts = relationship(
        "Cart",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    favourites = relationship(
        "Favourite",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @hybrid_property
    def full_name(self): return f"{self.name or ''} {self.surname or ''}" or "Без имени"

    @full_name.expression
    def full_name(cls): return func.concat(cls.name or '', " ", cls.surname or '') or "Без имени"

    @property
    def contact_info(self) -> str:
        return (f"ID ТГ: {self.tg_id}, "
                f"Номер ТГ: {normalize_phone(self.tg_phone) if self.tg_phone else 'Отсутствует'}, "
                f"Почта: {self.email or 'Отсутствует'}, "
                f"Номер телефона: {normalize_phone(self.phone) if self.phone else 'Отсутствует'}")