"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.database import init_db
from app.api import search, paper


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup: Initialize database (gracefully handles failures)
    print("Starting Best Papers Finder API...")
    await init_db()
    print("✓ API ready")
    yield
    # Shutdown: Cleanup if needed
    print("Shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title="Best Papers Finder",
        description="Find the top 20 research papers for any field",
        version="1.0.0",
        lifespan=lifespan,
    )
    
    # Configure CORS
    # Parse CORS origins from environment variable (comma-separated)
    cors_origins = settings.cors_origins.split(",") if settings.cors_origins else ["*"]
    # Allow all origins in production if "*" is specified
    if "*" in cors_origins:
        allow_origins = ["*"]
    else:
        allow_origins = [origin.strip() for origin in cors_origins]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(search.router, tags=["search"])
    app.include_router(paper.router, tags=["paper"])
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy"}
    
    return app


app = create_app()
