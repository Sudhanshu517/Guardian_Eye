from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os
import asyncio

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

    # Kick off model warm-up in the background so models are ready before
    # the first real request arrives. The server stays responsive immediately.
    async def _background_warmup():
        try:
            print("🤖 [warmup] Starting background model warm-up...")
            from .services.yolo_service import get_yolo_service
            yolo = get_yolo_service()
            results = await asyncio.to_thread(yolo.warmup)
            loaded = [k for k, v in results.items() if v in ("loaded", "already_cached")]
            skipped = [k for k, v in results.items() if "skipped" in v]
            failed = [k for k, v in results.items() if v == "failed"]
            print(f"✅ [warmup] Done. Loaded={len(loaded)} Skipped={len(skipped)} Failed={len(failed)}")
            if failed:
                print(f"⚠️  [warmup] Failed models: {failed}")
        except Exception as exc:
            print(f"❌ [warmup] Background warm-up error: {exc}")

    asyncio.create_task(_background_warmup())

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
        "https://guardian-eye-beta.vercel.app",
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
