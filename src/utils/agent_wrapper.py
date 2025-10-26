"""
에이전트 실행을 자동으로 로깅하는 래퍼
"""
from typing import Any, Dict
from functools import wraps
from src.utils.graph_logger import graph_logger


def with_logging(agent_name: str):
    """에이전트 실행을 자동으로 로깅하는 데코레이터"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 입력 데이터 추출
            input_data = kwargs if kwargs else {"args": args}

            # 실행 시작
            graph_logger.start_execution(agent_name, input_data)

            try:
                # 에이전트 실행
                result = await func(*args, **kwargs)

                # 종료 로깅
                graph_logger.end_execution(result)

                return result

            except Exception as e:
                # 에러 로깅
                graph_logger.log_error(agent_name, e)
                raise

        return wrapper
    return decorator


# 사용 예시
"""
from src.utils.agent_wrapper import with_logging

@with_logging("research_agent")
async def run_research_agent(stock_code: str):
    agent = build_research_agent()
    return await agent.ainvoke({"stock_code": stock_code})
"""
