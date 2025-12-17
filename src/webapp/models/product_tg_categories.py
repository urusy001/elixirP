from sqlalchemy import Table, Column, Integer, String, ForeignKey
from src.webapp.database import Base

product_tg_categories = Table(
    "product_tg_categories",
    Base.metadata,
    Column(
        "product_onec_id",
        String,
        ForeignKey("products.onec_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tg_category_id",
        Integer,
        ForeignKey("tg_categories.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)