"""
路由汇总
"""

from .search import router as search_router
from .questions import router as questions_router
from .pending import router as pending_router
from .admin import router as admin_router

__all__ = ['search_router', 'questions_router', 'pending_router', 'admin_router']
