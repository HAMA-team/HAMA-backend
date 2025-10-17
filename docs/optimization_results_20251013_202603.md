# 최적화 효과 측정 리포트

**측정 일시**: 2025-10-13 20:26:03

## 📊 전체 요약

| 항목 | 값 |
|------|------|
| 총 실행 시간 | 206.708초 |
| 평균 실행 시간 | 29.530초 |
| 총 단계 수 | 7 |

## 🚀 캐시 성능

### LLM 인스턴스 캐싱

```
Cache Info: CacheInfo(hits=18, misses=4, maxsize=16, currsize=4)
```

| 메트릭 | 값 |
|--------|------|
| 캐시 히트 | 18 |
| 캐시 미스 | 4 |
| 현재 캐시 크기 | 4 |
| 최대 캐시 크기 | 16 |
| **히트율** | **81.8%** |

### 그래프 컴파일 캐싱

```
Cache Info: CacheInfo(hits=4, misses=2, maxsize=16, currsize=1)
```

| 메트릭 | 값 |
|--------|------|
| 캐시 히트 | 4 |
| 캐시 미스 | 2 |
| 현재 캐시 크기 | 1 |
| 최대 캐시 크기 | 16 |
| **히트율** | **66.7%** |

## ⏱️ 단계별 실행 시간

| 단계 | 실행 시간 (초) | 비고 |
|------|---------------|------|
| LLM 캐싱 - 같은 설정 10회 | 0.045 | calls=10, config=temp=0, tokens=4000 |
| LLM 캐싱 - 다른 설정 5회 | 0.000 | calls=5, config=temp=0.3, tokens=2000 |
| E2E - 질의 1 | 1.965 | query=안녕하세요, level=2, success=False, error=Invalid argument provided to Gemini: 400 * Generat |
| E2E - 질의 2 | 1.364 | query=PER이 뭐야?, level=2, success=False, error=Invalid argument provided to Gemini: 400 * Generat |
| E2E - 질의 3 | 72.204 | query=삼성전자 분석해줘, level=2, success=False, error=강세 분석 실패: 빈 응답 수신 |
| E2E - 질의 4 | 35.490 | query=투자 전략 추천해줘, level=2, success=True |
| E2E - 질의 5 | 95.640 | query=내 포트폴리오 점검해줘, level=2, success=False, error=Recursion limit of 25 reached without hitting a st |

## 📈 분석

### 예상 개선 효과

**Before (최적화 전 예상):**
- 매 `run_graph()` 호출마다 새 그래프 빌드
- 매 노드마다 새 LLM 인스턴스 생성
- 예상 총 시간: ~5분 (20회 호출 시)

**After (최적화 후 실측):**
- 그래프 캐시 히트율: **66.7%**
- LLM 캐시 히트율: **81.8%**
- 실측 총 시간: **206.708초**

### 핵심 지표

1. **그래프 재사용률**: 4 / 6
2. **LLM 재사용률**: 18 / 22
3. **평균 응답 시간**: 29.530초

## 🎯 결론

⚠️ **그래프 캐싱 효과 보통**: 50~80% 히트율입니다. automation_level 변경이 많은 경우입니다.

✅ **LLM 캐싱 효과 우수**: 80% 이상의 히트율로 LLM 초기화 오버헤드가 크게 감소했습니다.


**총 실행 시간**: 206.708초

---

*이 리포트는 자동 생성되었습니다.*
