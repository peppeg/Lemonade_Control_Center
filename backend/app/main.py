"""
Lemonade Control Center — Backend API
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.capabilities import capabilities
from app.routers import health, lemonade, system, logs, diagnostic


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🍋 {settings.app_name} v{settings.app_version}")
    print(f"   Lemonade URL: {settings.lemonade_url}")
    print(f"   Admin key:    {'configured' if settings.lemonade_admin_api_key else 'not set'}")
    print(f"   Delete:       {'ENABLED ⚠' if settings.enable_delete else 'disabled'}")
    print(f"   Restart:      {'ENABLED ⚠' if settings.enable_restart else 'disabled'}")
    print(f"   Capabilities: {capabilities.probe_timestamp or 'no probe results'}")
    print(f"   Lemonade ver: {capabilities.lemonade_version or 'unknown'}")
    yield
    print("🍋 Shutting down...")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Admin console API for Lemonade local LLM servers",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──
app.include_router(health.router)
app.include_router(lemonade.router)
app.include_router(system.router)
app.include_router(logs.router)
app.include_router(diagnostic.router)
