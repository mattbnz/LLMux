"""
FastAPI application initialization and configuration.
"""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .middleware import log_requests_middleware
from .api_key_middleware import APIKeyMiddleware
from .endpoints import (
    health_router,
    models_router,
    auth_router,
    anthropic_messages_router,
    openai_chat_router,
    management_router,
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="LLMux", version="1.0.0")

# Add middleware (order matters: last added executes first on request)
app.middleware("http")(log_requests_middleware)
app.add_middleware(APIKeyMiddleware)  # API key validation runs first

# Register routers
app.include_router(health_router)
app.include_router(models_router)
app.include_router(auth_router)
app.include_router(anthropic_messages_router)
app.include_router(openai_chat_router)
app.include_router(management_router)

# Mount static files for web UI (if built)
# For SPA routing, we need to:
# 1. Serve static assets from /ui/assets
# 2. Serve index.html for all other /ui/* paths (catch-all for client-side routing)
web_dist_path = Path(__file__).parent.parent / "web" / "dist"
if web_dist_path.exists():
    # Mount static assets directory
    assets_path = web_dist_path / "assets"
    if assets_path.exists():
        app.mount("/ui/assets", StaticFiles(directory=str(assets_path)), name="web-assets")

    # Serve favicon
    @app.get("/ui/favicon.svg")
    async def favicon():
        return FileResponse(web_dist_path / "favicon.svg")

    # Catch-all route for SPA - serves index.html for all /ui/* paths
    # This enables client-side routing (React Router) to work with direct URL access
    @app.get("/ui/{full_path:path}")
    async def serve_spa(full_path: str):
        return FileResponse(web_dist_path / "index.html")

    @app.get("/ui")
    async def serve_spa_root():
        return FileResponse(web_dist_path / "index.html")

    logger.info(f"Web UI mounted at /ui from {web_dist_path}")
else:
    logger.debug(f"Web UI not found at {web_dist_path} - skipping static file mount")

logger.debug("FastAPI application initialized with all routers and middleware")
