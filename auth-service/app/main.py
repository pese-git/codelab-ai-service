"""Main FastAPI application"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import logger, settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("Starting Auth Service...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Version: {settings.version}")
    
    # Startup logic
    try:
        # Load RSA keys
        from app.core.security import rsa_key_manager
        rsa_key_manager.load_keys()
        logger.info("✓ RSA keys loaded")
        
        # Initialize database
        from app.models import init_db
        await init_db()
        logger.info("✓ Database initialized")
        
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        raise
    
    yield
    
    # Shutdown logic
    logger.info("Shutting down Auth Service...")
    from app.models import close_db
    await close_db()


# Create FastAPI application
app = FastAPI(
    title="CodeLab Auth Service",
    description="OAuth2 Authorization Server for CodeLab Platform",
    version=settings.version,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse(
        content={
            "status": "healthy",
            "version": settings.version,
            "environment": settings.environment,
        }
    )


@app.get("/")
async def root():
    """Root endpoint"""
    return JSONResponse(
        content={
            "service": "CodeLab Auth Service",
            "version": settings.version,
            "docs": "/docs" if settings.is_development else None,
        }
    )


# Include routers
from app.api.v1 import jwks, oauth

app.include_router(oauth.router, prefix="/oauth", tags=["OAuth2"])
app.include_router(jwks.router, prefix="/.well-known", tags=["JWKS"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
    )
