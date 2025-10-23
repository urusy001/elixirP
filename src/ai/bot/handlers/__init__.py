__all__ = ['user_router', 'admin_router']

from .user import router as user_router
from .admin import router as admin_router