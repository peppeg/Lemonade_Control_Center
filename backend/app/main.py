"""
Lemonade Control Center — Backend API
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.capabilities import capabilities
from app.middleware.access_control import LccAccessControlMiddleware
from app.routers import health, lemonade, system, logs, diagnostic, diagnostics, metrics, profiles, security, setup, settings as settings_router
from app.services.metrics.collector import start_collector, stop_collector
from app.services.security import is_loopback_host


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🍋 {settings.app_name} v{settings.app_version}")
    print(f"   Lemonade URL: {settings.lemonade_url}")
    print(f"   Admin key:    {'configured' if settings.lemonade_admin_api_key else 'not set'}")
    print(f"   Delete:       {'ENABLED ⚠' if settings.enable_delete else 'disabled'}")
    print(f"   Restart:      {'ENABLED ⚠' if settings.enable_restart else 'disabled'}")
    print(f"   Bench Lab:    {'ENABLED' if settings.enable_bench_lab else 'disabled'}")
    print(f"   Frontend:     {'served by FastAPI' if settings.serve_frontend else 'disabled'}")
    print(f"   App bind:     {settings.app_host}:{settings.app_port}")
    print(f"   LCC auth:     {'required' if settings.require_auth else 'localhost trusted'}")
    print(f"   LCC key:      {'configured' if settings.lcc_api_key else 'not set'}")
    if not is_loopback_host(settings.app_host) and not settings.require_auth:
        print("   LAN warning:  non-loopback APP_HOST should be used with REQUIRE_AUTH=true")
    print(f"   Capabilities: {capabilities.probe_timestamp or 'no probe results'}")
    print(f"   Lemonade ver: {capabilities.lemonade_version or 'unknown'}")
    start_collector(interval_seconds=10)
    yield
    stop_collector()
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
app.add_middleware(LccAccessControlMiddleware)

# ── Routers ──
app.include_router(health.router)
app.include_router(lemonade.router)
app.include_router(system.router)
app.include_router(logs.router)
app.include_router(diagnostic.router)
app.include_router(profiles.router)
app.include_router(diagnostics.router)
app.include_router(metrics.router)
app.include_router(metrics.ws_router)
app.include_router(security.router)
app.include_router(setup.router)
app.include_router(settings_router.router)

if settings.enable_bench_lab:
    from app.routers import bench

    app.include_router(bench.router)

if settings.serve_frontend:
    from app.frontend import router as frontend_router

    app.include_router(frontend_router)
