from pydantic import BaseModel, Field

from .category import Category
from .feature import Feature
from .product import Product
from .unit import Unit
from .user import User
from .user_token_usage import UserTokenUsage, BotEnum
from .cart_item import CartItem
from .cart import Cart
from .favourite import Favourite
from .tg_category import TgCategory
from .used_code import UsedCode
from .promo_code import PromoCode

__all__ = ['Category', 'Product', 'Unit', 'Feature', 'User', 'UserTokenUsage', 'BotEnum', 'PVZRequest', 'CartItem', 'Cart', 'Favourite', 'TgCategory', 'UsedCode']

class PVZRequest(BaseModel):
    latitude: float | None = Field(None, description="Latitude (if geo_id not provided)")
    longitude: float | None = Field(None, description="Longitude (if geo_id not provided)")
    radius: float | None = Field(10000, description="Search radius in meters")
    geo_id: int | None = Field(None, description="Yandex geo_id of locality (preferred)")
