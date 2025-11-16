from typing import Optional
from pydantic import BaseModel, Field

from .category import Category
from .feature import Feature
from .giveaway import Giveaway
from .participant import Participant
from .product import Product
from .unit import Unit
from .user import User
from .usertokenusage import UserTokenUsage, BotEnum
from .bag import Bag
from .bag_items import BagItem
from .cart import Cart

__all__ = ['Category', 'Product', 'Unit', 'Feature', 'User', 'UserTokenUsage', 'Giveaway', 'Participant', 'BotEnum', 'PVZRequest', 'Bag', 'BagItem', 'Cart']

class PVZRequest(BaseModel):
    latitude: Optional[float] = Field(None, description="Latitude (if geo_id not provided)")
    longitude: Optional[float] = Field(None, description="Longitude (if geo_id not provided)")
    radius: Optional[float] = Field(10000, description="Search radius in meters")
    geo_id: Optional[int] = Field(None, description="Yandex geo_id of locality (preferred)")
