from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from src.webapp.database import Base
from src.webapp.models.product_tg_categories import product_tg_categories


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # IMPORTANT: onec_id must NOT be primary_key if you already have id PK
    onec_id = Column(String, nullable=False, unique=True, index=True)

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
        passive_deletes=True,
    )

    favourited_by = relationship(
        "Favourite",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    # MANY-TO-MANY with TgCategory
    tg_categories = relationship(
        "TgCategory",
        secondary=product_tg_categories,
        back_populates="products",
        lazy="selectin",
    )

    def __str__(self) -> str:
        expiration_text = f"<b>ИНСТРУКЦИИ К ХРАНЕНИЮ</b>\n{self.expiration or 'Не имеются или <i>указаны выше</i>'}"
        usage_text = f"<b>ИНСТРУКЦИИ К ПРИММЕНЕНИЮ</b>\n{self.usage or 'Не имеются или <i>указаны выше</i>'}"
        description_text = f"<b>ОПИСАНИЕ</b>\n{self.description or 'Не имеется'}"
        prices_text = "\n".join([f"{feature.name} — {feature.price}₽" for feature in self.features])
        from src.helpers import normalize_html_for_telegram
        return normalize_html_for_telegram(
            f"<b>{self.name}</b>\n"
            f"Артикул: <i>{self.code}</i>\n"
            f"\n\n"
            f"{description_text}\n\n"
            f"{usage_text}\n\n"
            f"{expiration_text}\n\n"
            f"<b>ДОЗИРОВКИ И ЦЕНЫ:</b>\n"
            f"{prices_text}"
        )