# Phase 2 구현 계획 v2.0

**작성일**: 2025-10-04
**기반 문서**: 에이전트 구현 상세 가이드 v2.0

---

## 📋 목차

1. [아키텍처 재정의 요약](#아키텍처-재정의-요약)
2. [전체 워크플로우](#전체-워크플로우)
3. [디렉터리 구조](#디렉터리-구조)
4. [구현 순서 및 타임라인](#구현-순서-및-타임라인)
5. [Week별 상세 계획](#week별-상세-계획)

---

## 🔄 아키텍처 재정의 요약

### 핵심 변경 사항

| 에이전트 | 기존 역할 | 새로운 역할 | 변경 이유 |
|---------|----------|-----------|----------|
| **Strategy** | 개별 종목 Bull/Bear 분석 | **거시 대전략 수립** (시장 사이클, 섹터 로테이션) | 계층적 의사결정 확립 |
| **Research** | 재무/기술적 분석만 | **종목 심층 분석 + Bull/Bear 통합** | 역할 중복 제거 |
| **Portfolio** | 단순 최적화 | **전략 구현 전 과정** (스크리닝 → 분석 → 최적화) | 책임 명확화 |

### 개선 효과

1. **계층적 의사결정 확립**
   - 거시(Strategy) → 중간(Portfolio) → 미시(Research)
   - 각 레벨의 책임 명확

2. **역할 중복 제거**
   - Bull/Bear가 Research로 통합
   - Strategy는 거시에만 집중

3. **학술 논문과 일치**
   - MSPM의 EAM/SAM 구조
   - OpenAI의 Macro/Portfolio Manager 패턴

---

## 🔄 전체 워크플로우

### 사용자 질의 → 포트폴리오 생성

```
사용자: "적립식으로 투자하고 싶어. IT와 헬스케어 중심으로"
    ↓
┌─────────────────────────────────────┐
│ Master Agent                        │
│ - 의도 분석: portfolio_construction │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ Strategy Agent (대전략 수립)        │
│ - 시장 전망: 중기 강세              │
│ - 섹터 전략: IT 40%, 헬스케어 20%  │
│ - 스타일: 성장주, 적립식            │
└─────────────────────────────────────┘
    ↓ Strategic Blueprint
┌─────────────────────────────────────┐
│ Portfolio Agent (후보 스크리닝)     │
│ - IT 섹터: 20개 후보                │
│ - 헬스케어 섹터: 10개 후보          │
└─────────────────────────────────────┘
    ↓ 30개 후보 종목
┌─────────────────────────────────────┐
│ Research Agent (각 종목 분석)       │
│ ┌───────────────────────────────┐   │
│ │ Bull Analyst Sub-Agent        │   │
│ │ - 삼성전자: Bull 75%, Bear 25%│   │
│ │ - 종합 평가: 4.2/5.0          │   │
│ └───────────────────────────────┘   │
│ ┌───────────────────────────────┐   │
│ │ Bear Analyst Sub-Agent        │   │
│ │ - 리스크 요인 분석            │   │
│ └───────────────────────────────┘   │
└─────────────────────────────────────┘
    ↓ 30개 분석 리포트
┌─────────────────────────────────────┐
│ Portfolio Agent (종목 선택)         │
│ - 평가 점수 3.0 이상: 15개          │
│ - 섹터 다각화: IT 3, 헬스케어 2     │
│ - 최종 선택: 5개 종목               │
└─────────────────────────────────────┘
    ↓ 5개 선택 종목
┌─────────────────────────────────────┐
│ Portfolio Agent (최적화)            │
│ - 샤프 비율 최적화                  │
│ - 주식 75%, 현금 25%                │
└─────────────────────────────────────┘
    ↓ 최적 포트폴리오
┌─────────────────────────────────────┐
│ Risk Agent (리스크 검증)            │
│ - VaR 계산, 집중도 체크             │
└─────────────────────────────────────┘
    ↓
사용자에게 최종 포트폴리오 제시
```

---

## 📁 디렉터리 구조

### 서브 에이전트 폴더 구성

```
src/agents/
├── __init__.py
├── base.py                     # BaseAgent 공통 인터페이스
│
├── master.py                   # 기존 간단한 라우터 (Phase 1)
├── graph_master.py             # LangGraph 기반 마스터 (Phase 1 완료)
│
├── data_collection.py          # ✅ Phase 2 완료
│
├── research/                   # ⭐ 서브 에이전트 폴더
│   ├── __init__.py
│   ├── research_agent.py       # 메인 리서치 에이전트 (기존 research.py 이동)
│   ├── bull_analyst.py         # Bull 분석 서브에이전트
│   ├── bear_analyst.py         # Bear 분석 서브에이전트
│   └── consensus.py            # Bull/Bear Consensus 계산 로직
│
├── strategy/                   # ⭐ 서브 에이전트 폴더
│   ├── __init__.py
│   ├── strategy_agent.py       # 메인 전략 에이전트 (기존 strategy.py 이동)
│   ├── market_analyzer.py      # 시장 사이클 분석 서브모듈
│   ├── sector_rotator.py       # 섹터 로테이션 로직
│   └── risk_stance.py          # 리스크 스탠스 결정 로직
│
├── portfolio/                  # ⭐ 서브 에이전트 폴더
│   ├── __init__.py
│   ├── portfolio_agent.py      # 메인 포트폴리오 에이전트 (기존 portfolio.py 이동)
│   ├── screener.py             # 종목 스크리너
│   ├── optimizer.py            # 샤프 비율 최적화
│   └── rebalancer.py           # 리밸런싱 로직
│
├── risk.py                     # 리스크 에이전트 (서브 에이전트 없음)
├── monitoring.py               # 모니터링 에이전트
├── education.py                # 교육/질의 에이전트
└── personalization.py          # 개인화 에이전트
```

### 구조 변경 작업

1. **research.py → research/research_agent.py**
   - Bull/Bear 서브에이전트 추가
   - Consensus 로직 분리

2. **strategy.py → strategy/strategy_agent.py**
   - Market Analyzer 서브모듈 추가
   - 거시 분석 중심으로 재작성

3. **portfolio.py → portfolio/portfolio_agent.py**
   - Screener, Optimizer, Rebalancer 분리
   - Blueprint 해석 로직 추가

---

## 📅 구현 순서 및 타임라인

### 전체 타임라인 (12주)

| Week | 작업 | 상태 |
|------|------|------|
| 11-12 | ✅ 인프라 구축 (FinanceDataReader, DART, Redis) | 완료 |
| **13** | 디렉터리 재구성 + Strategy Agent 기본 구현 | ⏸️ |
| 14 | Strategy Agent 완성 (시장 분석, 섹터 로테이션) | |
| 15-16 | Research Agent 재구현 (Bull/Bear 통합) | |
| 17-18 | Portfolio Agent 재구현 (전 과정) | |
| 19-20 | Risk Agent 실제 구현 | |
| 21 | Monitoring + Education Agents | |
| 22 | 통합 테스트 및 E2E 검증 | |
| 23-24 | 성능 최적화 및 버그 수정 | |

---

## 📆 Week별 상세 계획

### Week 13: 디렉터리 재구성 + Strategy Agent 기본 구현

**목표**: 아키텍처 변경사항 반영 및 Strategy Agent 뼈대 구축

#### 작업 항목

1. **디렉터리 재구성 (1일)**
   - [ ] `src/agents/research/` 폴더 생성
   - [ ] `research.py` → `research/research_agent.py` 이동
   - [ ] `src/agents/strategy/` 폴더 생성
   - [ ] `strategy.py` → `strategy/strategy_agent.py` 이동
   - [ ] `src/agents/portfolio/` 폴더 생성
   - [ ] `portfolio.py` → `portfolio/portfolio_agent.py` 이동
   - [ ] `__init__.py` 파일들 생성 및 import 경로 수정
   - [ ] 전체 테스트 실행하여 import 에러 확인

2. **Strategy Agent Mock 구현 (2일)**
   - [ ] `strategy/strategy_agent.py` 재작성
   - [ ] Strategic Blueprint 스키마 정의 (Pydantic)
   - [ ] Mock 시장 사이클 데이터 생성
   - [ ] Mock 섹터 전략 데이터
   - [ ] 기본 워크플로우 테스트

3. **Strategy Agent 서브모듈 준비 (2일)**
   - [ ] `strategy/market_analyzer.py` 기본 구조
   - [ ] `strategy/sector_rotator.py` 기본 구조
   - [ ] `strategy/risk_stance.py` 로직 구현
   - [ ] 통합 테스트

#### 체크포인트
- [ ] 모든 기존 E2E 테스트 통과
- [ ] Strategy Agent가 Strategic Blueprint 반환
- [ ] Import 경로 모두 정상 작동

---

### Week 14: Strategy Agent 실제 구현

**목표**: LLM 기반 거시 분석 완성

#### 작업 항목

1. **거시경제 데이터 수집 (1일)**
   - [ ] 금리 데이터 API 연동 (한국은행 또는 FRED)
   - [ ] CPI, GDP 데이터 수집
   - [ ] 데이터 정규화 및 저장

2. **시장 사이클 분석 (2일)**
   - [ ] LLM 프롬프트 작성 (Claude Sonnet 4.5)
   - [ ] 시장 사이클 분류 로직
   - [ ] 신뢰도 점수 계산
   - [ ] 테스트 (실제 데이터 기반)

3. **섹터 로테이션 전략 (2일)**
   - [ ] LLM 기반 섹터 평가
   - [ ] Overweight/Underweight 분류
   - [ ] 사용자 선호도 통합
   - [ ] 테스트 및 검증

#### 출력 예시
```json
{
  "market_outlook": {
    "cycle": "mid_bull_market",
    "confidence": 0.72
  },
  "sector_strategy": {
    "overweight": ["IT", "반도체"],
    "underweight": ["에너지"]
  },
  "asset_allocation_target": {
    "stocks": 0.75,
    "cash": 0.25
  }
}
```

---

### Week 15-16: Research Agent 재구현

**목표**: Bull/Bear 서브에이전트 통합 완성

#### 작업 항목

1. **Bull Analyst 서브에이전트 (3일)**
   - [ ] `research/bull_analyst.py` 구현
   - [ ] LLM 프롬프트 (긍정적 요인 분석)
   - [ ] 목표가 산정 로직
   - [ ] 확률 계산
   - [ ] 테스트 (10개 종목)

2. **Bear Analyst 서브에이전트 (3일)**
   - [ ] `research/bear_analyst.py` 구현
   - [ ] LLM 프롬프트 (리스크 요인 분석)
   - [ ] 하방 리스크 계산
   - [ ] 확률 계산
   - [ ] 테스트 (10개 종목)

3. **Consensus 통합 (2일)**
   - [ ] `research/consensus.py` 로직
   - [ ] Bull/Bear 확률 가중 평균
   - [ ] 방향성 및 확신도 판단
   - [ ] 종합 평가 점수 산정
   - [ ] 통합 테스트

4. **Research Agent 메인 로직 (2일)**
   - [ ] Bull/Bear 병렬 호출
   - [ ] Consensus 계산 통합
   - [ ] 목표가 산정 (확률 가중)
   - [ ] 전체 워크플로우 테스트

#### 체크포인트
- [ ] 10개 종목 분석 성공
- [ ] Bull/Bear Consensus 정상 계산
- [ ] 평균 응답 시간 < 5초 (10개 종목)

---

### Week 17-18: Portfolio Agent 재구현

**목표**: 전략 구현 전 과정 완성

#### 작업 항목

1. **Blueprint 해석 로직 (2일)**
   - [ ] Strategic Blueprint 파싱
   - [ ] 제약조건 추출
   - [ ] 투자 스타일 매핑

2. **종목 스크리너 (3일)**
   - [ ] `portfolio/screener.py` 구현
   - [ ] 섹터별 종목 DB 구축
   - [ ] 스타일 필터링 (성장/가치, 대형/중형)
   - [ ] 시가총액 필터링
   - [ ] 테스트

3. **Research Agent 통합 (2일)**
   - [ ] 후보 종목 병렬 분석 호출
   - [ ] 분석 결과 기반 종목 선택
   - [ ] 평가 점수 기준 정렬
   - [ ] 섹터 다각화 로직

4. **Optimizer + Rebalancer (3일)**
   - [ ] `portfolio/optimizer.py` 샤프 비율 최적화
   - [ ] `portfolio/rebalancer.py` 리밸런싱 로직
   - [ ] 제약조건 적용
   - [ ] 테스트

#### 체크포인트
- [ ] Blueprint → 구체적 포트폴리오 생성 성공
- [ ] 30개 후보 → 5-10개 선택 정상 작동
- [ ] 샤프 비율 최적화 수렴

---

### Week 19-20: Risk Agent 실제 구현

**목표**: 리스크 평가 및 경고 시스템

#### 작업 항목

1. **VaR 계산 (3일)**
   - [ ] Historical VaR
   - [ ] Monte Carlo VaR
   - [ ] 95% 신뢰수준 손실 추정

2. **집중도 리스크 (2일)**
   - [ ] 단일 종목 비중 경고
   - [ ] 섹터 집중도 분석

3. **시나리오 분석 (2일)**
   - [ ] Monte Carlo 시뮬레이션 (10,000회)
   - [ ] 최악의 시나리오 손실
   - [ ] HITL 경고 트리거

4. **통합 (1일)**
   - [ ] Portfolio Agent와 통합
   - [ ] 테스트

---

### Week 21: 지원 에이전트 구현

**목표**: Monitoring, Education, Personalization 완성

- [ ] Monitoring Agent (가격 추적, 이벤트 감지)
- [ ] Education Agent (용어 DB, Q&A)
- [ ] Personalization Agent (프로필 관리)

---

### Week 22: 통합 테스트 및 E2E 검증

**목표**: 전체 워크플로우 검증

1. **E2E 테스트 (3일)**
   - [ ] 사용자 질의 → 포트폴리오 생성 (전체 플로우)
   - [ ] 3가지 시나리오 테스트
   - [ ] 성능 측정

2. **버그 수정 (2일)**
   - [ ] 테스트 중 발견된 이슈 해결

---

### Week 23-24: 성능 최적화 및 베타 테스트

**목표**: Phase 2 완성

1. **성능 최적화 (1주)**
   - [ ] 캐싱 전략 개선
   - [ ] 비동기 처리 최적화
   - [ ] 응답 속도 < 2초 목표

2. **베타 테스트 (1주)**
   - [ ] 5명 이상 테스터 모집
   - [ ] 피드백 수집 및 개선

---

## 🔑 핵심 성공 기준

### Phase 2 완료 조건
- [ ] 9개 에이전트 모두 실제 데이터 기반 구현
- [ ] 전체 워크플로우 E2E 테스트 통과
- [ ] 평균 응답 속도 < 3초
- [ ] 베타 테스터 만족도 80% 이상

### 기술적 품질
- [ ] 코드 커버리지 > 70%
- [ ] 주요 경로 E2E 테스트 100% 통과
- [ ] 에러율 < 5%

---

## 📚 참고 문서

- `docs/plan/agent-implementation-details.md` - 에이전트 상세 설계 v2.0
- `docs/agent-data-context-strategy.md` - 데이터 제공 방법론
- `docs/agent-architecture-detailed.md` - 에이전트 아키텍처
- `docs/progress.md` - 진행 상황 추적

---

**다음 작업**: Week 13 디렉터리 재구성부터 시작
