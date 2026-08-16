from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
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
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(error),
        }