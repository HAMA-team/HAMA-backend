"""
전역 에러 핸들러 모듈

모든 API 에러를 표준화된 형식으로 반환합니다.
"""
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from datetime import datetime
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class APIException(Exception):
    """
    커스텀 API 예외

    Usage:
        raise APIException(
            status_code=404,
            message="리소스를 찾을 수 없습니다",
            code="RESOURCE_NOT_FOUND",
            details={"resource_id": "123"}
        )
    """

    def __init__(
        self,
        status_code: int,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.status_code = status_code
        self.message = message
        self.code = code or f"ERROR_{status_code}"
        self.details = details or {}
        super().__init__(self.message)


def setup_error_handlers(app: FastAPI):
    """
    전역 에러 핸들러 등록

    Args:
        app: FastAPI 앱 인스턴스
    """

    @app.exception_handler(APIException)
    async def api_exception_handler(request: Request, exc: APIException):
        """커스텀 API 예외 처리"""
        logger.error(
            f"API Exception: {exc.message}",
            extra={
                "status_code": exc.status_code,
                "code": exc.code,
                "path": request.url.path,
                "method": request.method,
                "details": exc.details
            }
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "message": exc.message,
                "code": exc.code,
                "timestamp": datetime.utcnow().isoformat(),
                **exc.details
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError
    ):
        """Pydantic Validation 에러"""
        logger.warning(
            f"Validation Error: {exc.errors()}",
            extra={
                "path": request.url.path,
                "method": request.method
            }
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": True,
                "message": "요청 데이터가 올바르지 않습니다",
                "code": "VALIDATION_ERROR",
                "timestamp": datetime.utcnow().isoformat(),
                "details": exc.errors()
            }
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        """404 Not Found"""
        return JSONResponse(
            status_code=404,
            content={
                "error": True,
                "message": "요청하신 리소스를 찾을 수 없습니다",
                "code": "NOT_FOUND",
                "timestamp": datetime.utcnow().isoformat(),
                "path": request.url.path
            }
        )

    @app.exception_handler(429)
    async def rate_limit_handler(request: Request, exc):
        """429 Too Many Requests"""
        return JSONResponse(
            status_code=429,
            content={
                "error": True,
                "message": "요청이 너무 많습니다. 잠시 후 다시 시도해주세요",
                "code": "RATE_LIMIT_EXCEEDED",
                "timestamp": datetime.utcnow().isoformat(),
                "retry_after": 60  # seconds
            }
        )

    @app.exception_handler(500)
    async def internal_server_error_handler(request: Request, exc: Exception):
        """500 Internal Server Error"""
        import traceback

        # 콘솔에 상세 에러 출력 (디버깅용)
        print(f"\n{'='*80}")
        print(f"❌ 500 Internal Server Error")
        print(f"📍 Path: {request.method} {request.url.path}")
        print(f"🔥 Exception Type: {type(exc).__name__}")
        print(f"💬 Message: {str(exc)}")
        print(f"\n📜 Full Traceback:")
        print(traceback.format_exc())
        print(f"{'='*80}\n")

        logger.exception(
            f"Internal Server Error: {exc}",
            extra={
                "path": request.url.path,
                "method": request.method
            }
        )

        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "message": "서버 오류가 발생했습니다",
                "code": "INTERNAL_SERVER_ERROR",
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    @app.exception_handler(401)
    async def unauthorized_handler(request: Request, exc):
        """401 Unauthorized"""
        return JSONResponse(
            status_code=401,
            content={
                "error": True,
                "message": "로그인이 필요합니다",
                "code": "UNAUTHORIZED",
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    @app.exception_handler(403)
    async def forbidden_handler(request: Request, exc):
        """403 Forbidden"""
        return JSONResponse(
            status_code=403,
            content={
                "error": True,
                "message": "접근 권한이 없습니다",
                "code": "FORBIDDEN",
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    logger.info("✅ 전역 에러 핸들러 등록 완료")
