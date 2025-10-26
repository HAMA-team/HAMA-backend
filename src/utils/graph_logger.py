"""
LangGraph 실행 가시성을 위한 커스텀 로거
LangSmith 없이도 에이전트 실행을 추적할 수 있음
"""
import json
import time
from typing import Any, Dict
from datetime import datetime
from pathlib import Path


class GraphLogger:
    """그래프 실행을 로깅하는 유틸리티"""

    def __init__(self, log_dir: str = "logs/graph_executions"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.current_execution = None
        self.start_time = None

    def start_execution(self, graph_name: str, input_data: Dict[str, Any]):
        """실행 시작"""
        self.start_time = time.time()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.current_execution = {
            "graph_name": graph_name,
            "timestamp": timestamp,
            "input": self._serialize(input_data),
            "nodes": [],
            "errors": []
        }

        print(f"\n{'='*60}")
        print(f"🚀 [{graph_name}] 실행 시작")
        print(f"{'='*60}")

    def log_node_start(self, node_name: str, state: Dict[str, Any]):
        """노드 실행 시작"""
        node_start = time.time()

        print(f"\n▶️  노드: {node_name}")
        print(f"   상태 키: {list(state.keys())}")

        node_log = {
            "node": node_name,
            "start_time": node_start,
            "input_state": self._serialize(state, max_depth=2)
        }

        if self.current_execution:
            self.current_execution["nodes"].append(node_log)

        return node_start

    def log_node_end(self, node_name: str, node_start: float, output_state: Dict[str, Any]):
        """노드 실행 종료"""
        duration = time.time() - node_start

        print(f"   ✅ 완료 ({duration:.2f}s)")

        if self.current_execution and self.current_execution["nodes"]:
            # 마지막 노드 로그 업데이트
            self.current_execution["nodes"][-1].update({
                "duration": duration,
                "output_state": self._serialize(output_state, max_depth=2)
            })

    def log_llm_call(self, model: str, prompt: str, response: str, tokens: int = None):
        """LLM 호출 로깅"""
        print(f"   🤖 LLM 호출: {model}")
        if tokens:
            print(f"      토큰: {tokens}")

        if self.current_execution and self.current_execution["nodes"]:
            if "llm_calls" not in self.current_execution["nodes"][-1]:
                self.current_execution["nodes"][-1]["llm_calls"] = []

            self.current_execution["nodes"][-1]["llm_calls"].append({
                "model": model,
                "prompt_preview": prompt[:100] + "...",
                "response_preview": response[:100] + "...",
                "tokens": tokens
            })

    def log_error(self, node_name: str, error: Exception):
        """에러 로깅"""
        print(f"   ❌ 에러: {str(error)}")

        if self.current_execution:
            self.current_execution["errors"].append({
                "node": node_name,
                "error": str(error),
                "type": type(error).__name__
            })

    def end_execution(self, final_state: Dict[str, Any]):
        """실행 종료"""
        total_duration = time.time() - self.start_time

        print(f"\n{'='*60}")
        print(f"✅ 실행 완료 (총 {total_duration:.2f}s)")
        print(f"{'='*60}\n")

        if self.current_execution:
            self.current_execution.update({
                "total_duration": total_duration,
                "final_state": self._serialize(final_state, max_depth=2)
            })

            # 로그 파일 저장
            log_file = self.log_dir / f"{self.current_execution['timestamp']}_{self.current_execution['graph_name']}.json"
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(self.current_execution, f, indent=2, ensure_ascii=False)

            print(f"📝 로그 저장: {log_file}")

    def _serialize(self, obj: Any, max_depth: int = 3, current_depth: int = 0) -> Any:
        """객체를 JSON 직렬화 가능한 형태로 변환"""
        if current_depth > max_depth:
            return "..."

        if isinstance(obj, dict):
            return {k: self._serialize(v, max_depth, current_depth + 1) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._serialize(item, max_depth, current_depth + 1) for item in obj]
        elif hasattr(obj, "__dict__"):
            return f"<{type(obj).__name__}>"
        else:
            return str(obj) if not isinstance(obj, (str, int, float, bool, type(None))) else obj


# 전역 로거 인스턴스
graph_logger = GraphLogger()


def log_graph_execution(func):
    """그래프 실행을 자동으로 로깅하는 데코레이터"""
    async def wrapper(*args, **kwargs):
        graph_name = func.__name__
        input_data = kwargs if kwargs else {"args": args}

        graph_logger.start_execution(graph_name, input_data)

        try:
            result = await func(*args, **kwargs)
            graph_logger.end_execution(result)
            return result
        except Exception as e:
            graph_logger.log_error(graph_name, e)
            raise

    return wrapper
