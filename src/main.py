"""
HAMA Backend - FastAPI Application Entry Point
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.api.routes import chat, portfolio, stocks
from src.config.settings import settings
from src.models.database import SessionLocal, init_db

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.API_VERSION,
    debug=settings.DEBUG,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure database schema is present (noop if already created)
try:
    init_db()
except SQLAlchemyError:
    pass

# Include routers
api_prefix = f"/api/{settings.API_VERSION}"

app.include_router(chat.router, prefix=f"{api_prefix}/chat", tags=["chat"])
app.include_router(portfolio.router, prefix=f"{api_prefix}/portfolio", tags=["portfolio"])
app.include_router(stocks.router, prefix=f"{api_prefix}/stocks", tags=["stocks"])


@app.get("/")
async def root():
    """Basic health probe"""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.API_VERSION,
        "env": settings.ENV,
    }


@app.get("/health")
async def health():
    """Detailed health check"""
    db_status = "connected"
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        db_status = f"error:{exc.__class__.__name__}"

    status_value = "healthy" if db_status == "connected" else "degraded"

    return {
        "status": status_value,
        "database": db_status,
        "agents": "ready",
        "app": settings.APP_NAME,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
