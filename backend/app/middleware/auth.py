"""
SevaSetu — Firebase Authentication Middleware
Validates Firebase ID tokens on mutating routes (POST, PATCH, DELETE).

Architecture:
  GET requests → pass through (public read access for dashboard)
  POST/PATCH/DELETE → require a valid Firebase ID token in Authorization header
  System routes (/api/system/*) → require auth in production only
  Health/docs → always public

Opt-in enforcement:
  Set FIREBASE_CREDENTIALS_PATH in .env to activate.
  If unset, auth is completely skipped (dev mode).
"""

import logging
from typing import Optional

from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ─── Firebase initialization ────────────────────────────────────────────────
_firebase_app = None
_auth_module = None

if settings.FIREBASE_CREDENTIALS_PATH:
    try:
        import firebase_admin
        from firebase_admin import credentials, auth
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        _firebase_app = firebase_admin.initialize_app(cred)
        _auth_module = auth
        logger.info("🔐 Firebase auth initialized — mutating routes are protected")
    except Exception as e:
        logger.warning(f"⚠️ Firebase init failed: {e} — auth disabled")
else:
    logger.info("🔓 No FIREBASE_CREDENTIALS_PATH — auth disabled (dev mode)")


# ─── Public paths that NEVER require auth ────────────────────────────────────
PUBLIC_PATHS = {
    "/", "/health", "/docs", "/redoc", "/openapi.json",
    "/ws/chat",  # WebSocket has its own auth
}

# Read-only methods that don't require auth
READ_METHODS = {"GET", "HEAD", "OPTIONS"}


def _is_public(path: str, method: str) -> bool:
    """Determine if a request should skip auth."""
    # Always public
    if path in PUBLIC_PATHS:
        return True
    # Static files, docs
    if path.startswith(("/docs", "/redoc", "/openapi")):
        return True
    # GET requests are public (read access)
    if method in READ_METHODS:
        return True
    return False


async def verify_firebase_token(token: str) -> Optional[dict]:
    """
    Verify a Firebase ID token and return the decoded claims.
    Returns None if verification fails.
    """
    if not _auth_module:
        return None

    try:
        decoded = _auth_module.verify_id_token(token)
        return decoded
    except _auth_module.ExpiredIdTokenError:
        logger.warning("Firebase token expired")
        raise HTTPException(status_code=401, detail="Token expired")
    except _auth_module.RevokedIdTokenError:
        logger.warning("Firebase token revoked")
        raise HTTPException(status_code=401, detail="Token revoked")
    except _auth_module.InvalidIdTokenError as e:
        logger.warning(f"Invalid Firebase token: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"Firebase token verification error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")


class FirebaseAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces Firebase ID token authentication on mutating routes.
    
    Behavior:
    - If FIREBASE_CREDENTIALS_PATH is not set: all requests pass through (dev mode)
    - If set: POST/PATCH/DELETE requests must include a valid Bearer token
    - GET/HEAD/OPTIONS always pass through (public read access)
    - Health/docs endpoints always pass through
    
    IMPORTANT: Auth failures return JSONResponse (not raise HTTPException)
    so that CORSMiddleware can still attach CORS headers to the response.
    """

    async def dispatch(self, request: Request, call_next):
        from starlette.responses import JSONResponse

        # Skip auth entirely if Firebase is not configured (dev mode)
        if not _firebase_app:
            response = await call_next(request)
            return response

        path = request.url.path
        method = request.method

        # Skip auth for public/read-only paths
        if _is_public(path, method):
            response = await call_next(request)
            return response

        # ── Dev bypass: allow unauthenticated mutating requests in dev ────
        # This lets the frontend work without Firebase login during development
        if getattr(settings, 'FIREBASE_DEV_BYPASS', False):
            request.state.firebase_uid = "dev-user"
            request.state.firebase_email = "dev@sevasetu.local"
            response = await call_next(request)
            return response

        # ── Enforce auth on mutating routes ──────────────────────────────
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            # Return JSONResponse instead of raising HTTPException
            # so CORS middleware can still add Access-Control headers
            return JSONResponse(
                status_code=401,
                content={"detail": "Authorization header required for mutating operations"},
            )

        # Extract Bearer token
        parts = auth_header.split(" ")
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid Authorization header format. Use: Bearer <token>"},
            )

        # Verify token
        try:
            decoded = await verify_firebase_token(parts[1])
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
            )

        # Attach user info to request state for downstream handlers
        request.state.firebase_uid = decoded.get("uid")
        request.state.firebase_email = decoded.get("email")

        response = await call_next(request)
        return response

