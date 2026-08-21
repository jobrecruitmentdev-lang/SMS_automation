import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings, ensure_adb_binary
from app.core.state import write_log
from app.controllers.auth_controller import router as auth_router
from app.controllers.gateway_controller import router as gateway_router
from app.controllers.dispatch_controller import router as dispatch_router
from app.controllers.jobs_controller import router as jobs_router
from app.controllers.ai_controller import router as ai_router
from app.controllers.template_controller import router as template_router
from app.controllers.system_controller import router as system_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup Lifespan
    write_log(f"🚀 Initializing {settings.PROJECT_NAME} v{settings.VERSION} on FastAPI ASGI...")
    adb_path = ensure_adb_binary()
    if adb_path:
        write_log(f"✅ ADB Binary Active: {adb_path}")
    yield
    # Shutdown Lifespan
    write_log("🛑 Shutting down SMS Studio ASGI Engine...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="High-Performance Multi-Tenant SMS Automation, AI Copywriter & Android Physical Phone Gateway Engine.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for Android Companion APK, local debug clients, and cross-domain webhooks
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register All MVC Router Controllers
app.include_router(auth_router)
app.include_router(gateway_router)
app.include_router(dispatch_router)
app.include_router(jobs_router)
app.include_router(ai_router)
app.include_router(template_router)
app.include_router(system_router)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print(f"[*] Starting FastAPI ASGI Server on http://0.0.0.0:{port} (Interactive Docs: /docs)...")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
