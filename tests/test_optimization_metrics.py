"""
최적화 효과 측정 테스트

Phase 1, 2 최적화 적용 후 실제 개선 효과를 측정합니다:
- LLM 인스턴스 캐싱 효과
- 그래프 컴파일 캐싱 효과
- 전체 E2E 워크플로우 성능

결과는 docs/optimization_results_{timestamp}.md에 저장됩니다.
"""
import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import pytest

from src.utils.llm_factory import get_llm, _build_llm
from src.agents.graph_master import run_graph, get_compiled_graph, build_graph


class OptimizationMetrics:
    """최적화 메트릭 수집 클래스"""

    def __init__(self):
        self.reset()

    def reset(self):
        """메트릭 초기화"""
        self.llm_cache_info = None
        self.graph_cache_info = None
        self.execution_times: List[float] = []
        self.step_results: List[Dict[str, Any]] = []

    def record_step(self, step_name: str, duration: float, metadata: Dict[str, Any] = None):
        """단계별 결과 기록"""
        self.execution_times.append(duration)
        result = {
            "step": step_name,
            "duration_sec": round(duration, 3),
            "metadata": metadata or {}
        }
        self.step_results.append(result)

    def capture_cache_info(self):
        """캐시 정보 수집"""
        self.llm_cache_info = _build_llm.cache_info()
        self.graph_cache_info = get_compiled_graph.cache_info()

    def generate_report(self) -> str:
        """결과 리포트 생성 (Markdown)"""
        self.capture_cache_info()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        report = f"""# 최적화 효과 측정 리포트

**측정 일시**: {timestamp}

## 📊 전체 요약

| 항목 | 값 |
|------|------|
| 총 실행 시간 | {sum(self.execution_times):.3f}초 |
| 평균 실행 시간 | {sum(self.execution_times) / len(self.execution_times):.3f}초 |
| 총 단계 수 | {len(self.step_results)} |

## 🚀 캐시 성능

### LLM 인스턴스 캐싱

```
Cache Info: {self.llm_cache_info}
```

| 메트릭 | 값 |
|--------|------|
| 캐시 히트 | {self.llm_cache_info.hits if self.llm_cache_info else 0} |
| 캐시 미스 | {self.llm_cache_info.misses if self.llm_cache_info else 0} |
| 현재 캐시 크기 | {self.llm_cache_info.currsize if self.llm_cache_info else 0} |
| 최대 캐시 크기 | {self.llm_cache_info.maxsize if self.llm_cache_info else 0} |
| **히트율** | **{self.llm_cache_info.hits / (self.llm_cache_info.hits + self.llm_cache_info.misses) * 100 if self.llm_cache_info and (self.llm_cache_info.hits + self.llm_cache_info.misses) > 0 else 0:.1f}%** |

### 그래프 컴파일 캐싱

```
Cache Info: {self.graph_cache_info}
```

| 메트릭 | 값 |
|--------|------|
| 캐시 히트 | {self.graph_cache_info.hits if self.graph_cache_info else 0} |
| 캐시 미스 | {self.graph_cache_info.misses if self.graph_cache_info else 0} |
| 현재 캐시 크기 | {self.graph_cache_info.currsize if self.graph_cache_info else 0} |
| 최대 캐시 크기 | {self.graph_cache_info.maxsize if self.graph_cache_info else 0} |
| **히트율** | **{self.graph_cache_info.hits / (self.graph_cache_info.hits + self.graph_cache_info.misses) * 100 if self.graph_cache_info and (self.graph_cache_info.hits + self.graph_cache_info.misses) > 0 else 0:.1f}%** |

## ⏱️ 단계별 실행 시간

| 단계 | 실행 시간 (초) | 비고 |
|------|---------------|------|
"""

        for result in self.step_results:
            metadata_str = ", ".join([f"{k}={v}" for k, v in result['metadata'].items()])
            report += f"| {result['step']} | {result['duration_sec']:.3f} | {metadata_str} |\n"

        report += f"""
## 📈 분석

### 예상 개선 효과

**Before (최적화 전 예상):**
- 매 `run_graph()` 호출마다 새 그래프 빌드
- 매 노드마다 새 LLM 인스턴스 생성
- 예상 총 시간: ~5분 (20회 호출 시)

**After (최적화 후 실측):**
- 그래프 캐시 히트율: **{self.graph_cache_info.hits / (self.graph_cache_info.hits + self.graph_cache_info.misses) * 100 if self.graph_cache_info and (self.graph_cache_info.hits + self.graph_cache_info.misses) > 0 else 0:.1f}%**
- LLM 캐시 히트율: **{self.llm_cache_info.hits / (self.llm_cache_info.hits + self.llm_cache_info.misses) * 100 if self.llm_cache_info and (self.llm_cache_info.hits + self.llm_cache_info.misses) > 0 else 0:.1f}%**
- 실측 총 시간: **{sum(self.execution_times):.3f}초**

### 핵심 지표

1. **그래프 재사용률**: {self.graph_cache_info.hits if self.graph_cache_info else 0} / {(self.graph_cache_info.hits + self.graph_cache_info.misses) if self.graph_cache_info else 0}
2. **LLM 재사용률**: {self.llm_cache_info.hits if self.llm_cache_info else 0} / {(self.llm_cache_info.hits + self.llm_cache_info.misses) if self.llm_cache_info else 0}
3. **평균 응답 시간**: {sum(self.execution_times) / len(self.execution_times):.3f}초

## 🎯 결론

"""

        # 자동 분석
        if self.graph_cache_info and self.graph_cache_info.hits > 0:
            graph_hit_rate = self.graph_cache_info.hits / (self.graph_cache_info.hits + self.graph_cache_info.misses) * 100
            if graph_hit_rate > 80:
                report += "✅ **그래프 캐싱 효과 우수**: 80% 이상의 히트율로 그래프 재빌드 오버헤드가 크게 감소했습니다.\n\n"
            elif graph_hit_rate > 50:
                report += "⚠️ **그래프 캐싱 효과 보통**: 50~80% 히트율입니다. automation_level 변경이 많은 경우입니다.\n\n"
            else:
                report += "❌ **그래프 캐싱 미흡**: 50% 미만 히트율입니다. 캐싱 로직 점검이 필요합니다.\n\n"

        if self.llm_cache_info and self.llm_cache_info.hits > 0:
            llm_hit_rate = self.llm_cache_info.hits / (self.llm_cache_info.hits + self.llm_cache_info.misses) * 100
            if llm_hit_rate > 80:
                report += "✅ **LLM 캐싱 효과 우수**: 80% 이상의 히트율로 LLM 초기화 오버헤드가 크게 감소했습니다.\n\n"
            elif llm_hit_rate > 50:
                report += "⚠️ **LLM 캐싱 효과 보통**: 50~80% 히트율입니다. 다양한 temperature/max_tokens 조합이 사용되고 있습니다.\n\n"
            else:
                report += "❌ **LLM 캐싱 미흡**: 50% 미만 히트율입니다. 파라미터 표준화 검토가 필요합니다.\n\n"

        report += f"""
**총 실행 시간**: {sum(self.execution_times):.3f}초

---

*이 리포트는 자동 생성되었습니다.*
"""

        return report

    def save_report(self, output_dir: str = "docs"):
        """리포트를 파일로 저장"""
        report = self.generate_report()

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"optimization_results_{timestamp}.md"
        filepath = Path(output_dir) / filename

        filepath.write_text(report, encoding="utf-8")

        print(f"\n{'='*80}")
        print(f"📄 리포트 저장 완료: {filepath}")
        print(f"{'='*80}\n")

        return str(filepath)


# ==================== 테스트 시작 ====================

@pytest.fixture
def metrics():
    """메트릭 수집기"""
    return OptimizationMetrics()


class TestOptimizationMetrics:
    """최적화 효과 측정 테스트"""

    @pytest.mark.asyncio
    async def test_llm_caching_effect(self, metrics: OptimizationMetrics):
        """
        Phase 1: LLM 인스턴스 캐싱 효과 측정

        같은 설정으로 여러 번 호출 시 캐시에서 반환되는지 확인
        """
        print("\n" + "="*80)
        print("📊 Phase 1: LLM 인스턴스 캐싱 효과 측정")
        print("="*80)

        # 초기 캐시 정보 수집
        metrics.capture_cache_info()
        initial_llm_cache = metrics.llm_cache_info

        print(f"\n초기 LLM 캐시 상태:")
        print(f"  - 히트: {initial_llm_cache.hits if initial_llm_cache else 0}")
        print(f"  - 미스: {initial_llm_cache.misses if initial_llm_cache else 0}")

        # 테스트 1: 같은 설정으로 10번 호출
        print(f"\n[테스트 1] 같은 설정(temp=0, tokens=4000)으로 10번 호출")

        start = time.time()
        for i in range(10):
            llm = get_llm(temperature=0, max_tokens=4000)
            assert llm is not None
        duration = time.time() - start

        metrics.record_step(
            "LLM 캐싱 - 같은 설정 10회",
            duration,
            {"calls": 10, "config": "temp=0, tokens=4000"}
        )

        print(f"  ✅ 완료: {duration:.3f}초")

        # 중간 캐시 정보
        metrics.capture_cache_info()
        mid_llm_cache = metrics.llm_cache_info

        print(f"\n중간 LLM 캐시 상태:")
        print(f"  - 히트: {mid_llm_cache.hits if mid_llm_cache else 0}")
        print(f"  - 미스: {mid_llm_cache.misses if mid_llm_cache else 0}")
        print(f"  - 캐시 증가: +{(mid_llm_cache.hits - initial_llm_cache.hits) if (mid_llm_cache and initial_llm_cache) else 0}개")

        # 테스트 2: 다른 설정으로 5번 호출
        print(f"\n[테스트 2] 다른 설정(temp=0.3, tokens=2000)으로 5번 호출")

        start = time.time()
        for i in range(5):
            llm = get_llm(temperature=0.3, max_tokens=2000)
            assert llm is not None
        duration = time.time() - start

        metrics.record_step(
            "LLM 캐싱 - 다른 설정 5회",
            duration,
            {"calls": 5, "config": "temp=0.3, tokens=2000"}
        )

        print(f"  ✅ 완료: {duration:.3f}초")

        # 최종 캐시 정보
        metrics.capture_cache_info()
        final_llm_cache = metrics.llm_cache_info

        print(f"\n최종 LLM 캐시 상태:")
        print(f"  - 히트: {final_llm_cache.hits if final_llm_cache else 0}")
        print(f"  - 미스: {final_llm_cache.misses if final_llm_cache else 0}")
        print(f"  - 현재 크기: {final_llm_cache.currsize if final_llm_cache else 0}")

        if final_llm_cache and (final_llm_cache.hits + final_llm_cache.misses) > 0:
            hit_rate = final_llm_cache.hits / (final_llm_cache.hits + final_llm_cache.misses) * 100
            print(f"  - 히트율: {hit_rate:.1f}%")

            # 검증
            assert hit_rate > 50, f"LLM 캐시 히트율이 너무 낮습니다: {hit_rate:.1f}%"

    @pytest.mark.asyncio
    async def test_graph_caching_effect(self, metrics: OptimizationMetrics):
        """
        Phase 2: 그래프 컴파일 캐싱 효과 측정

        같은 automation_level로 여러 번 호출 시 캐시에서 반환되는지 확인
        """
        print("\n" + "="*80)
        print("📊 Phase 2: 그래프 컴파일 캐싱 효과 측정")
        print("="*80)

        # 초기 캐시 정보
        metrics.capture_cache_info()
        initial_graph_cache = metrics.graph_cache_info

        print(f"\n초기 그래프 캐시 상태:")
        print(f"  - 히트: {initial_graph_cache.hits if initial_graph_cache else 0}")
        print(f"  - 미스: {initial_graph_cache.misses if initial_graph_cache else 0}")

        # 테스트 1: 같은 레벨로 10번 빌드
        print(f"\n[테스트 1] automation_level=2로 10번 빌드")

        start = time.time()
        for i in range(10):
            app = build_graph(automation_level=2)
            assert app is not None
        duration = time.time() - start

        metrics.record_step(
            "그래프 캐싱 - 레벨2 10회",
            duration,
            {"calls": 10, "level": 2}
        )

        print(f"  ✅ 완료: {duration:.3f}초")

        # 중간 캐시 정보
        metrics.capture_cache_info()
        mid_graph_cache = metrics.graph_cache_info

        print(f"\n중간 그래프 캐시 상태:")
        print(f"  - 히트: {mid_graph_cache.hits if mid_graph_cache else 0}")
        print(f"  - 미스: {mid_graph_cache.misses if mid_graph_cache else 0}")
        print(f"  - 캐시 증가: +{(mid_graph_cache.hits - initial_graph_cache.hits) if (mid_graph_cache and initial_graph_cache) else 0}개")

        # 테스트 2: 다른 레벨로 5번 빌드
        print(f"\n[테스트 2] automation_level=1로 5번 빌드")

        start = time.time()
        for i in range(5):
            app = build_graph(automation_level=1)
            assert app is not None
        duration = time.time() - start

        metrics.record_step(
            "그래프 캐싱 - 레벨1 5회",
            duration,
            {"calls": 5, "level": 1}
        )

        print(f"  ✅ 완료: {duration:.3f}초")

        # 최종 캐시 정보
        metrics.capture_cache_info()
        final_graph_cache = metrics.graph_cache_info

        print(f"\n최종 그래프 캐시 상태:")
        print(f"  - 히트: {final_graph_cache.hits if final_graph_cache else 0}")
        print(f"  - 미스: {final_graph_cache.misses if final_graph_cache else 0}")
        print(f"  - 현재 크기: {final_graph_cache.currsize if final_graph_cache else 0}")

        if final_graph_cache and (final_graph_cache.hits + final_graph_cache.misses) > 0:
            hit_rate = final_graph_cache.hits / (final_graph_cache.hits + final_graph_cache.misses) * 100
            print(f"  - 히트율: {hit_rate:.1f}%")

            # 검증
            assert hit_rate > 50, f"그래프 캐시 히트율이 너무 낮습니다: {hit_rate:.1f}%"

    @pytest.mark.asyncio
    async def test_end_to_end_performance(self, metrics: OptimizationMetrics):
        """
        Phase 3: 전체 E2E 워크플로우 성능 측정

        실제 run_graph() 호출을 여러 번 수행하여 전체 성능 측정
        """
        print("\n" + "="*80)
        print("📊 Phase 3: 전체 E2E 워크플로우 성능 측정")
        print("="*80)

        queries = [
            ("안녕하세요", 2),
            ("PER이 뭐야?", 2),
            ("삼성전자 분석해줘", 2),
            ("투자 전략 추천해줘", 2),
            ("내 포트폴리오 점검해줘", 2),
        ]

        for idx, (query, level) in enumerate(queries, 1):
            print(f"\n[질의 {idx}/{len(queries)}] \"{query}\" (레벨 {level})")

            start = time.time()
            try:
                result = await run_graph(
                    query=query,
                    automation_level=level,
                    request_id=f"opt_test_{idx}"
                )
                duration = time.time() - start

                metrics.record_step(
                    f"E2E - 질의 {idx}",
                    duration,
                    {
                        "query": query[:20],
                        "level": level,
                        "success": True
                    }
                )

                print(f"  ✅ 완료: {duration:.3f}초")
                print(f"  응답: {result.get('message', '')[:100]}...")

            except Exception as e:
                duration = time.time() - start

                metrics.record_step(
                    f"E2E - 질의 {idx}",
                    duration,
                    {
                        "query": query[:20],
                        "level": level,
                        "success": False,
                        "error": str(e)[:50]
                    }
                )

                print(f"  ⚠️ 에러: {e}")

            # Rate limit 준수
            await asyncio.sleep(1)

        # 최종 캐시 상태
        metrics.capture_cache_info()

        print(f"\n최종 캐시 상태 종합:")
        print(f"  LLM 캐시:")
        print(f"    - 히트: {metrics.llm_cache_info.hits if metrics.llm_cache_info else 0}")
        print(f"    - 미스: {metrics.llm_cache_info.misses if metrics.llm_cache_info else 0}")

        print(f"  그래프 캐시:")
        print(f"    - 히트: {metrics.graph_cache_info.hits if metrics.graph_cache_info else 0}")
        print(f"    - 미스: {metrics.graph_cache_info.misses if metrics.graph_cache_info else 0}")


# ==================== 직접 실행 ====================

if __name__ == "__main__":
    """
    직접 실행 시 모든 테스트를 순차적으로 실행하고 리포트 생성
    """
    async def main():
        print("\n" + "🎯"*40)
        print("최적화 효과 측정 테스트 시작")
        print("🎯"*40)

        metrics = OptimizationMetrics()
        test_suite = TestOptimizationMetrics()

        # Phase 1: LLM 캐싱
        try:
            print("\n" + "="*80)
            print("Phase 1: LLM 인스턴스 캐싱 효과")
            print("="*80)
            await test_suite.test_llm_caching_effect(metrics)
            print("\n✅ Phase 1 완료")
        except Exception as e:
            print(f"\n❌ Phase 1 실패: {e}")
            import traceback
            traceback.print_exc()

        # Phase 2: 그래프 캐싱
        try:
            print("\n" + "="*80)
            print("Phase 2: 그래프 컴파일 캐싱 효과")
            print("="*80)
            await test_suite.test_graph_caching_effect(metrics)
            print("\n✅ Phase 2 완료")
        except Exception as e:
            print(f"\n❌ Phase 2 실패: {e}")
            import traceback
            traceback.print_exc()

        # Phase 3: E2E 성능
        try:
            print("\n" + "="*80)
            print("Phase 3: 전체 E2E 워크플로우 성능")
            print("="*80)
            await test_suite.test_end_to_end_performance(metrics)
            print("\n✅ Phase 3 완료")
        except Exception as e:
            print(f"\n❌ Phase 3 실패: {e}")
            import traceback
            traceback.print_exc()

        # 리포트 생성
        print("\n" + "="*80)
        print("📄 리포트 생성 중...")
        print("="*80)

        report_path = metrics.save_report()

        print(f"\n{'='*80}")
        print(f"✅ 모든 테스트 완료!")
        print(f"📄 리포트: {report_path}")
        print(f"{'='*80}")

    asyncio.run(main())
