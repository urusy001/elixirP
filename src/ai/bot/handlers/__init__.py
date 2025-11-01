__all__ = ['professor_user_router', 'professor_admin_router', 'new_user_router', 'new_admin_router', 'dose_user_router',
           'dose_admin_router']

from .admin import router as professor_admin_router, router2 as new_admin_router, router3 as dose_admin_router
from .user import router as professor_user_router, router2 as new_user_router, router3 as dose_user_router
