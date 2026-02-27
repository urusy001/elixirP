
from .cart_web import CartWebRead
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
    'CartCreate', 'CartUpdate', 'CartItemCreate', 'CartItemUpdate', 'CartItemBase', 'CartRead', 'CartWebRead',
    'FavouriteOut', 'FavouriteCreate', 'FavouriteDelete', 'FavouriteBase',
    'TgCategoryCreate', 'TgCategoryUpdate', 'TgCategoryBase', 'TgCategoryRead',
    'UsedCodeBase', 'UsedCodeRead', 'UsedCodeCreate', 'UsedCodeUpdate',
    'PromoCodeOut', 'PromoCodeCreate', 'PromoCodeUpdate', 'PromoCodeBase',
    'PriceT', 'AvailabilityDestination', 'AvailabilityRequest', 'VerifyOrderIn', 'VerifyOrderOut',
]

class AvailabilityDestination(BaseModel):
    platform_station_id: str | None = None
    full_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None

class AvailabilityRequest(BaseModel):
    delivery_mode: Literal["self_pickup", "time_interval"]
    destination: AvailabilityDestination
    send_unix: bool = True

PriceT = int | None | Literal["old", "not_found", "low"]

class VerifyOrderIn(BaseModel): code: str | int = Field(..., description="Код заказа/сделки, который ищем в amoCRM (№{code} )")
class VerifyOrderOut(BaseModel):
    status: Literal["ok", "not_found", "no_email", "smtp_failed", "low"]
    price: PriceT
    email: str | None = None
    verification_code: str | None = None