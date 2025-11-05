"""C3 OAuth Routes - OAuth/OIDC authentication endpoints."""
from src.c3_oauth_routes.oauth_routes import create_oauth_router

__all__ = ["create_oauth_router"]
