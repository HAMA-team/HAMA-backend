"""
FastAPI 요청/응답 로깅 미들웨어
API 레벨에서 모든 요청을 추적
"""
import time
import json
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """모든 API 요청을 로깅"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 시작 시간
        start_time = time.time()

        # 요청 정보
        print(f"\n{'='*60}")
        print(f"📨 [{request.method}] {request.url.path}")
        print(f"   Client: {request.client.host}")

        # 요청 본문 (있는 경우)
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    print(f"   Body: {body[:200].decode()}")  # 처음 200자만
            except:
                pass

        # 요청 처리
        response = await call_next(request)

        # 응답 시간
        duration = time.time() - start_time

        # 응답 정보
        status_emoji = "✅" if response.status_code < 400 else "❌"
        print(f"{status_emoji} Status: {response.status_code}")
        print(f"⏱️  Duration: {duration:.3f}s")
        print(f"{'='*60}\n")

        # 응답 헤더에 추가
        response.headers["X-Process-Time"] = str(duration)

        return response
