from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.webapp.models import Product


class ProductPhotos(InlineKeyboardMarkup):
    def __init__(self, product: Product):
        buttons = [InlineKeyboardButton(text=feature.name, callback_data=f"shop_admin:{product.onec_id}:photo:{feature.onec_id}") for feature in product.features]
        super().__init__(inline_keyboard=[
            [InlineKeyboardButton(text="Основное", callback_data=f"shop_admin:{product.onec_id}:photo:main")],
            [buttons[i: i+2] for i in range(0, len(buttons), 2)]
        ])
