"""OAuth and OpenID Connect routes for Claude MCP integration."""

import logging
import secrets
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, Body
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)

# Store registered clients (in production, use a database)
registered_clients = {}


def create_oauth_router():
    """Create OAuth router for authentication flows.

    Returns:
        APIRouter: Configured router with OAuth/OIDC endpoints
    """
    router = APIRouter(tags=["oauth", "auth"])

    @router.get("/.well-known/oauth-authorization-server")
    async def oauth_server_metadata():
        """OAuth server metadata with DCR support."""
        return {
            "issuer": "http://localhost:8000",
            "authorization_endpoint": "http://localhost:8000/oauth/authorize",
            "token_endpoint": "http://localhost:8000/oauth/token",
            "registration_endpoint": "http://localhost:8000/oauth/register",  # DCR endpoint
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],  # PKCE support
            "token_endpoint_auth_methods_supported": ["none"],
            "revocation_endpoint": "http://localhost:8000/oauth/revoke",
            "scopes_supported": ["openid", "profile", "email"],
        }

    @router.get("/.well-known/openid-configuration")
    async def openid_config():
        """OpenID configuration - tells Claude no auth needed."""
        return {
            "issuer": "http://localhost:8000",
            "authorization_endpoint": "http://localhost:8000/authorize",
            "token_endpoint": "http://localhost:8000/token",
            "userinfo_endpoint": "http://localhost:8000/userinfo",
            "response_types_supported": ["none"],
            "grant_types_supported": ["none"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["none"],
        }

    @router.post("/oauth/register")
    async def register_client(request: Dict[str, Any]):
        """Dynamic Client Registration endpoint (RFC 7591)."""
        client_id = f"client_{secrets.token_urlsafe(16)}"
        client_secret = secrets.token_urlsafe(32)

        # Store client registration
        registered_clients[client_id] = {
            "client_id": client_id,
            "client_secret": client_secret,
            "client_name": request.get("client_name", "Claude"),
            "redirect_uris": request.get("redirect_uris", ["https://claude.ai/api/mcp/auth_callback"]),
            "grant_types": request.get("grant_types", ["authorization_code"]),
            "response_types": request.get("response_types", ["code"]),
            "scope": request.get("scope", "openid profile email"),
            "token_endpoint_auth_method": request.get("token_endpoint_auth_method", "none"),
        }

        # Return client registration response
        return {
            "client_id": client_id,
            "client_secret": client_secret,
            "client_id_issued_at": int(datetime.utcnow().timestamp()),
            "client_secret_expires_at": 0,  # Never expires
            "redirect_uris": registered_clients[client_id]["redirect_uris"],
            "grant_types": registered_clients[client_id]["grant_types"],
            "response_types": registered_clients[client_id]["response_types"],
            "client_name": registered_clients[client_id]["client_name"],
            "scope": registered_clients[client_id]["scope"],
            "token_endpoint_auth_method": registered_clients[client_id]["token_endpoint_auth_method"],
        }

    @router.get("/oauth/authorize")
    async def authorize_get(
        client_id: str,
        redirect_uri: str,
        response_type: str = "code",
        scope: str = "openid profile email",
        state: Optional[str] = None,
        code_challenge: Optional[str] = None,
        code_challenge_method: Optional[str] = None,
    ):
        """Authorization endpoint - auto-approves for local use."""
        # Generate authorization code
        auth_code = secrets.token_urlsafe(32)

        # Build redirect URL with code
        redirect_url = f"{redirect_uri}?code={auth_code}"
        if state:
            redirect_url += f"&state={state}"

        # Return HTML that auto-redirects (simulating user approval)
        html_content = f"""
        <html>
        <head>
            <meta http-equiv="refresh" content="0; url={redirect_url}">
        </head>
        <body>
            <p>Authorizing... Redirecting to Claude...</p>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)

    @router.post("/oauth/authorize")
    async def authorize_post(request: Dict[str, Any]):
        """Authorization endpoint POST - for form submissions."""
        return await authorize_get(
            client_id=request.get("client_id"),
            redirect_uri=request.get("redirect_uri"),
            response_type=request.get("response_type", "code"),
            scope=request.get("scope", "openid profile email"),
            state=request.get("state"),
            code_challenge=request.get("code_challenge"),
            code_challenge_method=request.get("code_challenge_method"),
        )

    @router.post("/oauth/token")
    async def token(request: Dict[str, Any] = Body(...)):
        """Token endpoint - returns access token."""
        # For simplicity, always return a valid token (no real auth)
        return {
            "access_token": f"access_{secrets.token_urlsafe(32)}",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": f"refresh_{secrets.token_urlsafe(32)}",
            "scope": request.get("scope", "openid profile email"),
        }

    @router.post("/oauth/revoke")
    async def revoke_token(request: Dict[str, Any]):
        """Token revocation endpoint."""
        # For local use, just return success
        return {"revoked": True}

    @router.get("/userinfo")
    async def userinfo():
        """Fake userinfo endpoint."""
        return {
            "sub": "local-user",
            "name": "Local User",
            "preferred_username": "local",
        }

    @router.get("/")
    async def root():
        """Root endpoint with MCP protocol info."""
        return {
            "name": "Hephaestus MCP Server",
            "version": "1.0.0",
            "protocol_version": "1.0",
            "description": "Model Context Protocol server for AI agent orchestration",
            "capabilities": {
                "tools": True,
                "resources": True,
                "prompts": False,
                "auth": {
                    "type": "none",
                    "required": False
                }
            },
            "endpoints": [
                "/create_task",
                "/update_task_status",
                "/save_memory",
                "/agent_status",
                "/task_progress",
                "/health",
                "/ws",
                "/sse",
                "/tools",
                "/resources",
            ],
        }

    return router
