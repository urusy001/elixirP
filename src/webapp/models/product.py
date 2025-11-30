from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from src.webapp.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    onec_id = Column(String, primary_key=True, index=True, unique=True)
    name = Column(String(96), nullable=False)
    code = Column(String(16), nullable=False)
    description = Column(String, nullable=True)
    usage = Column(String, nullable=True)
    expiration = Column(String, nullable=True)
    category_onec_id = Column(
        String,
        ForeignKey("categories.onec_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    category = relationship("Category", back_populates="products")
    features = relationship("Feature", back_populates="product", cascade="all, delete-orphan")

    cart_items = relationship(
        "CartItem",
        back_populates="product",
        foreign_keys="CartItem.product_onec_id",
        lazy="selectin",
        passive_deletes=True,   # 👈 доверяем БД делать CASCADE
    )

    def __str__(self) -> str:
        expiration_text = f"<b>ИНСТРУКЦИИ К ХРАНЕНИЮ</b>\n{self.expiration or 'Не имеются или <i>указаны выше</i>'}"
        usage_text = f"<b>ИНСТРУКЦИИ К ПРИМЕНЕНИЮ</b>\n{self.usage or 'Не имеются или <i>указаны выше</i>'}"
        description_text = f"<b>ОПИСАНИЕ</b>\n{self.description or 'Не имеется'}"
        prices_text = '\n'.join([f'{feature.name} — {feature.price}₽' for feature in self.features])

        return (f"<b>{self.name}</b>\n"
                f"Артикул: <i>{self.code}</i>\n"
                f"\n\n"
                f"{description_text}\n\n"
                f"{usage_text}\n\n"
                f"{expiration_text}\n\n"
                f"<b>ДОЗИРОВКИ И ЦЕНЫ:</b>\n"
                f"{prices_text}")
