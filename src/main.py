"""
HAMA Backend - FastAPI Application Entry Point
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.api.routes import chat, dashboard, portfolio, stocks, multi_agent_stream, artifacts, approvals
from src.api.routes import settings as settings_router
from src.api.middleware.logging import RequestLoggingMiddleware
from src.api.error_handlers import setup_error_handlers
from src.config.settings import settings
from src.models.database import SessionLocal, init_db
from src.services import init_kis_service

tags_metadata = [
    {
        "name": "chat",
        "description": "대화 생성, 히스토리 조회, 승인 처리를 담당하는 엔드포인트 모음입니다.",
    },
    {
        "name": "dashboard",
        "description": "대시보드 화면에 필요한 자산 요약, 활동 로그 등을 제공합니다.",
    },
    {
        "name": "portfolio",
        "description": "포트폴리오 요약과 리밸런싱 등 자산 관리 기능을 위한 엔드포인트입니다.",
    },
    {
        "name": "stocks",
        "description": "종목 검색 및 시세 조회와 같은 주식 데이터 관련 API입니다.",
    },
    {
        "name": "settings",
        "description": "사용자 설정 (자동화 레벨 등)을 관리하는 엔드포인트입니다.",
    },
    {
        "name": "artifacts",
        "description": "AI 생성 콘텐츠 저장 및 관리 (분석 결과, 포트폴리오, 전략 등)를 위한 엔드포인트입니다.",
    },
    {
        "name": "approvals",
        "description": "승인 이력 조회 및 관리 (매매, 리밸런싱 등 HITL 승인 기록)를 위한 엔드포인트입니다.",
    },
]

# Create FastAPI app
app = FastAPI(
    title=f"{settings.APP_NAME} 백엔드 API",
    description=(
        "HAMA 투자 도우미의 백엔드 API 문서입니다.\n\n"
        "채팅 기반 분석, 포트폴리오 관리, 대시보드 통계를 비롯한 핵심 기능을 "
        "Swagger UI에서 바로 확인하고 테스트할 수 있습니다."
    ),
    version=settings.API_VERSION,
    debug=settings.DEBUG,
    openapi_tags=tags_metadata,
)

# Logging middleware (요청/응답 추적)
app.add_middleware(RequestLoggingMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역 에러 핸들러 등록
setup_error_handlers(app)

# Ensure database schema is present (noop if already created)
try:
    init_db()
except SQLAlchemyError:
    pass

# Include routers
api_prefix = f"/api/{settings.API_VERSION}"

app.include_router(chat.router, prefix=f"{api_prefix}/chat", tags=["chat"])
app.include_router(multi_agent_stream.router, prefix=f"{api_prefix}/chat", tags=["chat"])  # 멀티 에이전트 스트리밍
app.include_router(dashboard.router, prefix=f"{api_prefix}/dashboard", tags=["dashboard"])
app.include_router(portfolio.router, prefix=f"{api_prefix}/portfolio", tags=["portfolio"])
app.include_router(stocks.router, prefix=f"{api_prefix}/stocks", tags=["stocks"])
app.include_router(settings_router.router, prefix=f"{api_prefix}/settings", tags=["settings"])
app.include_router(artifacts.router, prefix=f"{api_prefix}/artifacts", tags=["artifacts"])
app.include_router(approvals.router, prefix=f"{api_prefix}/approvals", tags=["approvals"])


@app.on_event("startup")
async def initialize_kis_service():
    """애플리케이션 시작 시 KIS 서비스 초기화."""
    kis_env = "real" if settings.ENV.lower() == "production" else "demo"
    await init_kis_service(env=kis_env)


@app.get("/")
async def root():
    """애플리케이션 기본 상태를 확인하는 엔드포인트입니다."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.API_VERSION,
        "env": settings.ENV,
    }


@app.get("/health")
async def health():
    """데이터베이스 연결 여부 등 상세 상태를 확인하는 엔드포인트입니다."""
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
