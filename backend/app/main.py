from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from .config import settings
from .database import Database
from .routes import incidents, alerts, dashboard, cameras, vehicles, processing



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    # Startup
    print("🚀 Starting GuardianEye Backend...")
    await Database.connect_db()

    # Create necessary directories
    os.makedirs(settings.evidence_dir, exist_ok=True)
    os.makedirs(os.path.join(settings.base_dir, "uploads"), exist_ok=True)
    print(f"📁 Evidence directory: {settings.evidence_dir}")
    print(f"📁 Uploads directory: {os.path.join(settings.base_dir, 'uploads')}")

    yield

    # Shutdown
    print("🛑 Shutting down GuardianEye Backend...")
    await Database.close_db()


app = FastAPI(
    title="GuardianEye API",
    description="Automated Traffic Violation Detection System - Backend API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Configuration — must be added AFTER the real app instance is created
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure evidence directory exists before mounting
os.makedirs(settings.evidence_dir, exist_ok=True)
app.mount("/evidence", StaticFiles(directory=settings.evidence_dir), name="evidence")

# Serve demo videos (backend/videos/) for live feed page
videos_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "videos")
os.makedirs(videos_dir, exist_ok=True)
app.mount("/videos", StaticFiles(directory=videos_dir), name="videos")


# Include routers
app.include_router(processing.router)  # Processing (upload & AI) - First for priority
app.include_router(incidents.router)
app.include_router(alerts.router)
app.include_router(dashboard.router)
app.include_router(cameras.router)
app.include_router(vehicles.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "GuardianEye API",
        "version": "1.0.0",
        "description": "Automated Traffic Violation Detection System",
        "status": "operational",
        "docs": "/docs",
        "endpoints": {
            "processing": "/api/process",  # NEW: Image upload & AI processing
            "incidents": "/api/incidents",
            "alerts": "/api/alerts",
            "dashboard": "/api/dashboard",
            "cameras": "/api/cameras",
            "vehicles": "/api/vehicles"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": "connected" if Database.client else "disconnected"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
