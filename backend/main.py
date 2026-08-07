from fastapi import FastAPI

app = FastAPI(
    title="Furniture Optimization API",
    version="1.0.0",
    description="Backend API for the Furniture Production Optimization System"
)


@app.get("/")
def root():
    return {
        "message": "Furniture Optimization API is running 🚀"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }