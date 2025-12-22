from typing import Union

from .category import *
from .feature import *
from .product import *
from .unit import *
from .user import *
from .usertokenusage import *
from .cart import *
from .cart_item import *
from .favourite import *
from .tg_category import *
from .used_code import *
from .promo_code import *

__all__ = [
    'CategoryUpdate', 'CategoryBase', 'CategoryRead', 'CategoryCreate',
    'ProductUpdate', 'ProductBase', 'ProductRead', 'ProductCreate',
    'UnitUpdate', 'UnitBase', 'UnitRead', 'UnitCreate',
    'FeatureUpdate', 'FeatureBase', 'FeatureRead', 'FeatureCreate',
    'UserUpdate', 'UserBase', 'UserRead', 'UserCreate',
    'UserTokenUsageUpdate', 'UserTokenUsageRead', 'UserTokenUsageBase', 'UserTokenUsageCreate',
    'CartCreate', 'CartUpdate', 'CartItemCreate', 'CartItemUpdate', 'CartBase', 'CartItemBase', 'CartRead',
    'FavouriteOut', 'FavouriteCreate', 'FavouriteDelete', 'FavouriteBase',
    'TgCategoryCreate', 'TgCategoryUpdate', 'TgCategoryBase', 'TgCategoryRead',
    'UsedCodeBase', 'UsedCodeRead', 'UsedCodeCreate', 'UsedCodeUpdate',
    'PromoCodeOut', 'PromoCodeCreate', 'PromoCodeUpdate', 'PromoCodeBase',
    'PriceT', 'AvailabilityDestination', 'AvailabilityRequest', 'VerifyOrderIn', 'VerifyOrderOut',
]

class AvailabilityDestination(BaseModel):
    platform_station_id: Optional[str] = None
    full_address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class AvailabilityRequest(BaseModel):
    delivery_mode: Literal["self_pickup", "time_interval"]
    destination: AvailabilityDestination
    send_unix: bool = True


PriceT = Union[int, None, Literal["old", "not_found", "low"]]

class VerifyOrderIn(BaseModel): code: Union[str, int] = Field(..., description="Код заказа/сделки, который ищем в amoCRM (№{code} )")
class VerifyOrderOut(BaseModel):
    status: Literal["ok", "not_found", "no_email", "smtp_failed"]
    price: PriceT
    email: Optional[str] = None
    verification_code: Optional[str] = None