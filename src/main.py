"""
HAMA Backend - FastAPI Application Entry Point
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.api.routes import chat, dashboard, portfolio, stocks, multi_agent_stream, artifacts, approvals, news
from src.api.routes import settings as settings_router
from src.api.middleware.logging import RequestLoggingMiddleware
from src.api.error_handlers import setup_error_handlers
from src.config.settings import settings
from src.models.database import SessionLocal, init_db
from src.services import init_kis_service


def configure_logging() -> None:
    """settings.LOG_LEVEL에 맞춰 전역 로깅 설정."""

    level_name = (settings.LOG_LEVEL or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        force=True,  # uvicorn 기본 핸들러보다 우선 적용
    )


configure_logging()

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
    {
        "name": "news",
        "description": "종목 관련 뉴스 검색 및 조회 (네이버 뉴스 API 연동)를 위한 엔드포인트입니다.",
    },
]

@asynccontextmanager
async def lifespan(_: FastAPI):
    """FastAPI lifespan 이벤트 핸들러"""
    # KIS 서비스 초기화
    kis_env = "real" if settings.ENV.lower() == "production" else "demo"
    await init_kis_service(env=kis_env)
    yield


# Create FastAPI app
app = FastAPI(
    title="HAMA API - Human-in-the-Loop AI 투자 시스템",
    description=(
        "# HAMA API Documentation\n\n"
        "**Human-in-the-Loop AI 투자 시스템 Backend API**\n\n"
        "> \"AI가 분석하고, 당신이 결정한다\"\n\n"
        "## 아키텍처\n"
        "**LangGraph Supervisor 패턴** 기반 멀티 에이전트 시스템\n"
        "- **Supervisor**: 간단한 조회는 직접 처리, 복잡한 분석은 서브그래프에 위임\n"
        "- **Research SubGraph**: 종목 분석 (재무, 기술적 지표, 뉴스 감정)\n"
        "- **Quantitative SubGraph**: 투자 전략 & 리스크 평가 (시장 사이클, 섹터 로테이션, VaR)\n"
        "- **Trading Pipeline**: 포트폴리오 시뮬레이션 → HITL 승인 → 매매 실행\n\n"
        "## 주요 기능\n"
        "- **Chat Interface**: AI 대화 및 실시간 Thinking Trace 스트리밍\n"
        "- **HITL (Human-in-the-Loop)**: 매매 승인 시스템 (3단계 자동화 레벨)\n"
        "- **Portfolio Management**: 포트폴리오 조회, 리밸런싱, 최적화\n"
        "- **Real-time Data**: KIS API 기반 실시간 시세 조회\n"
        "- **Multi-Source Integration**: pykrx, DART, BOK API 연동\n\n"
        "## 데이터 소스\n"
        "| 소스 | 제공 데이터 |\n"
        "|------|------------|\n"
        "| **pykrx** | 주가, 거래량, 종목 리스트 |\n"
        "| **한국투자증권 API** | 실시간 시세, 차트, 호가 |\n"
        "| **DART API** | 재무제표, 공시, 기업 정보 |\n"
        "| **한국은행 API** | 금리, 거시경제 지표 |\n\n"
        "## 인증\n"
        "Phase 1에서는 인증 없이 사용 가능합니다. (Phase 2에서 JWT 인증 추가 예정)\n\n"
        "## 에러 코드\n"
        "| Code | Message | HTTP Status |\n"
        "|------|---------|-------------|\n"
        "| `VALIDATION_ERROR` | 요청 데이터가 올바르지 않습니다 | 422 |\n"
        "| `NOT_FOUND` | 리소스를 찾을 수 없습니다 | 404 |\n"
        "| `RATE_LIMIT_EXCEEDED` | 요청이 너무 많습니다 | 429 |\n"
        "| `INTERNAL_SERVER_ERROR` | 서버 오류 | 500 |\n\n"
        "## 개발 환경\n"
        "- **Backend**: http://localhost:8000\n"
        "- **Swagger UI**: http://localhost:8000/docs\n"
        "- **ReDoc**: http://localhost:8000/redoc\n"
    ),
    version=settings.API_VERSION,
    debug=settings.DEBUG,
    openapi_tags=tags_metadata,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Logging middleware (요청/응답 추적)
app.add_middleware(RequestLoggingMiddleware)

# CORS middleware (환경 변수 기반 허용 범위)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=settings.cors_origin_regex,  # 환경설정 기반 프리뷰/로컬 네트워크 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=600,  # Preflight 캐싱 (10분)
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
app.include_router(news.router, tags=["news"])  # 뉴스 API (prefix는 news.py에 정의됨)


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
