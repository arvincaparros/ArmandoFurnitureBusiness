import os

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database.connection import engine

from app.routers.auth import router as auth_router
from app.routers.products import router as products_router
from app.routers.resources import router as resources_router
from app.routers.product_resources import router as product_resources_router
from app.routers.production import router as production_router
from app.routers.cycle_resources import router as cycle_resources_router
from app.routers.allocations import router as allocations_router
from app.routers.optimization import router as optimization_router
from app.routers.dashboard import router as dashboard_router
from app.routers.forecast import router as forecast_router
from app.routers.transactions import router as transactions_router
from app.routers.resource_utilization import router as resource_utilization_router

app = FastAPI(
    title="Furniture Optimization API",
    version="1.0.0",
    description="Backend API for the Furniture Production Optimization System",
)

# Frontend runs on Vite's default dev server port (no custom port is
# configured anywhere in frontend/vite.config.ts or package.json).
# JWT auth uses an Authorization header, not cookies, so credentials
# don't need to be allowed across origins for this architecture.
#
# FRONTEND_URL is optional and additive only - the two dev origins
# above always remain allowed, so local development behavior is
# unchanged whether or not the variable is set. It exists so the
# Docker client deployment (frontend served from a different origin,
# e.g. http://localhost:3000) can be allowed without hardcoding a
# second port here - see docker-compose.client.yml.
_cors_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

_frontend_url = os.getenv("FRONTEND_URL")

if _frontend_url and _frontend_url not in _cors_origins:
    _cors_origins.append(_frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router)
app.include_router(products_router)
app.include_router(resources_router)
app.include_router(product_resources_router)
app.include_router(production_router)
app.include_router(cycle_resources_router)
app.include_router(allocations_router)
app.include_router(optimization_router)
app.include_router(dashboard_router)
app.include_router(forecast_router)
app.include_router(transactions_router)
app.include_router(resource_utilization_router)

@app.get("/")
def root():
    return {
        "message": "Furniture Optimization API is running 🚀"
    }


@app.get("/health")
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "healthy",
            "database": "connected",
        }

    except Exception as error:
        # A dict return defaults to HTTP 200 regardless of content, so
        # an HTTP-status-based health check (Koyeb, Docker HEALTHCHECK,
        # docker-compose.client.yml's own healthcheck) would otherwise
        # see 200 OK and report "healthy" even with the database down.
        # An explicit 503 makes this endpoint usable by all of them.
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(error),
            },
        )