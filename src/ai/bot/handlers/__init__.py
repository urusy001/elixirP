__all__ = ['professor_user_router', 'professor_admin_router', 'new_user_router', 'dose_user_router', 'dose_admin_router', 'new_admin_router']

from .admin import professor_admin_router, dose_admin_router, new_admin_router
from .user import professor_user_router as professor_user_router, dose_user_router as dose_user_router
from .shop_user import new_user_router
