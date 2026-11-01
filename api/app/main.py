from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.core.database import engine, Base, SessionLocal
from app.middleware.error_handler import register_exception_handlers
from app.api.v1 import api_v1_router
from app.routers.documents import router as documents_router

setup_logging(settings.LOG_LEVEL)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing HAT Converse FastAPI application...")
    logger.info("HAT Converse application startup complete.")
    yield
    logger.info("Application shutting down.")


app = FastAPI(
    title="HAT Converse API",
    description="Production-Ready API backend for HAT Converse digital transformation platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "app": "HAT Converse API", "environment": settings.APP_ENV}

app.include_router(api_v1_router, prefix="/api/v1")
app.include_router(documents_router)
