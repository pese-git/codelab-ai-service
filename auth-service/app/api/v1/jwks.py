"""JWKS endpoints"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.jwks_service import jwks_service

router = APIRouter()


@router.get("/jwks.json")
async def get_jwks():
    """
    Get JWKS (JSON Web Key Set)
    
    Returns public keys for JWT validation by Resource Servers.
    This endpoint should be cached by clients.
    
    Returns:
        JWKS with public keys
    """
    jwks = jwks_service.get_jwks()
    
    return JSONResponse(
        content=jwks,
        headers={
            "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
            "Content-Type": "application/json",
        },
    )
