"""
FastAPI 요청/응답 로깅 미들웨어
API 레벨에서 모든 요청을 추적
"""
import time
import json
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse

logger = logging.getLogger(__name__)


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

        # SSE 스트리밍 응답 처리
        if isinstance(response, StreamingResponse):
            print(f"🔄 [Streaming] SSE 응답 시작...")

            # SSE 응답 내용을 로깅하면서 스트리밍
            async def log_streaming_response():
                event_count = 0
                try:
                    async for chunk in response.body_iterator:
                        event_count += 1

                        # 모든 이벤트 로깅 (디버깅용)
                        try:
                            chunk_str = chunk.decode('utf-8')
                            # SSE 포맷 파싱: "event: xxx\ndata: {...}"
                            if chunk_str.strip():
                                lines = chunk_str.strip().split('\n')
                                event_type = None
                                event_data = None
                                for line in lines:
                                    if line.startswith('event:'):
                                        event_type = line.split(':', 1)[1].strip()
                                    elif line.startswith('data:'):
                                        event_data = line.split(':', 1)[1].strip()

                                if event_type and event_data:
                                    # 긴 데이터는 축약
                                    if len(event_data) > 150:
                                        event_data = event_data[:150] + "..."
                                    print(f"   [SSE] {event_type}: {event_data}")
                        except Exception as e:
                            logger.debug(f"SSE 로깅 실패: {e}")

                        yield chunk
                except Exception as e:
                    logger.error(f"❌ [Streaming] 에러: {e}")
                    raise
                finally:
                    # 스트리밍 종료 로그
                    total_duration = time.time() - start_time
                    print(f"✅ Streaming Complete ({event_count} events)")
                    print(f"⏱️  Total Duration: {total_duration:.3f}s")
                    print(f"{'='*60}\n")

            # 원본 body_iterator를 로깅 래퍼로 교체
            return StreamingResponse(
                log_streaming_response(),
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )

        # 일반 응답 정보
        status_emoji = "✅" if response.status_code < 400 else "❌"
        print(f"{status_emoji} Status: {response.status_code}")
        print(f"⏱️  Duration: {duration:.3f}s")
        print(f"{'='*60}\n")

        # 응답 헤더에 추가
        response.headers["X-Process-Time"] = str(duration)

        return response
