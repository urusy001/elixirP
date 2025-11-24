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
    category_onec_id = Column(String, ForeignKey("categories.onec_id", ondelete="SET NULL"), nullable=True, index=True)

    # Relationships
    category = relationship("Category", back_populates="products")
    features = relationship("Feature", back_populates="product", cascade="all, delete-orphan")

    def __str__(self) -> str:
        print(self.expiration or '1', self.usage or '0')
        return (f"<b>{self.name}</b>\n"
                f"Артикул: <i>{self.code}</i>\n"
                f"\n"
                f"{self.description if self.description else ''}\n\n"
                f"<b>Дозировки:</b>\n{'\n'.join([f'{feature.name} — {feature.price}' for feature in self.features])}")
