__all__ = [
    'product_router', 'cart_router', 'search_router', 'yandex_router', 'favourite_router', 'promo_codes_router',
    'cdek_router', 'payments_router', 'users_router', 'webhooks_router', 'auth_router', 'categories_router'
]

from .cart import router as cart_router
from .delivery import yandex_router, cdek_router
from .payments import router as payments_router
from .product import router as product_router
from .search import router as search_router
from .users import router as users_router
from .webhooks import router as webhooks_router
from .auth import router as auth_router
from .favourite import router as favourite_router
from .categories import router as categories_router
from .promocodes import router as promo_codes_router