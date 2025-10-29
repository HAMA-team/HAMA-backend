# 하드코딩 검토 보고서

## 개요
- 목적: 코드베이스 전반의 하드코딩된 값(환경 설정, 외부 연동, 에이전트/LLM, Mock 및 테스트 자산)을 식별해 리스크와 개선 방향을 제시한다.
- 작성일: 2025-10-29
- 범위: `src/` 및 `tests/` 전역, 설정/문서 제외

## 1. 환경 및 설정 상수
- 주요 발견
  - 애플리케이션/DB 기본값이 `src/config/settings.py:14`~`src/config/settings.py:117`에 직접 박혀 있으며 `DATABASE_URL`은 샘플 자격 증명을 포함한다.
  - LLM 라우터·캐시·모니터링 관련 파라미터가 같은 파일(`src/config/settings.py:120`~`src/config/settings.py:159`)에 상수로 고정돼 있다.
- 리스크
  - 배포 환경별 구성 분리가 어렵고 환경 변수로 전환하지 않을 경우 민감 정보가 노출될 수 있다.
  - TTL/타임아웃 값 조정이 어려워 운영 중 빠른 변경이 제한된다.
- 개선 제안
  1. `.env`와 `Settings`의 필드 기본값을 분리하고, 샘플 값은 `docs/config-example.md` 등 문서로 이동.
  2. TTL·포트 등은 최소한 Pydantic 모델의 `model_config`를 활용한 환경별 override(예: `ENV=test`)를 지원하도록 조정.

## 2. 외부 연동 상수
- 주요 발견
  - 한국투자증권 API 엔드포인트 및 거래 ID가 `src/services/kis_service.py:98`~`src/services/kis_service.py:105`, `src/services/kis_service.py:231`에 하드코딩돼 있다.
  - DART·BOK API 호출 시 URL 경로/코드가 `src/services/dart_service.py:52`, `src/services/dart_service.py:156`, `src/services/bok_service.py:57`, `src/services/bok_service.py:113` 등에서 문자열로 직접 작성돼 있다.
  - 지수 데이터 모의 생성 관련 기준값이 `src/services/stock_data_service.py:388`에 고정돼 있다.
- 리스크
  - 외부 API 사양 변경 시 코드 수정이 필수라 유지보수 비용이 증가한다.
  - 서비스 환경(Real/Demo) 전환 로직이 제한돼 오작동 가능성이 존재한다.
- 개선 제안
  1. 엔드포인트/코드 값은 `Settings` 혹은 별도의 `constants.py`로 분리하고 테스트 시 Mock을 주입 가능하도록 인터페이스화.
  2. 모의 데이터 생성은 환경 플래그(`ENABLE_INDEX_MOCK`)를 통해 제어하고 기본값은 실제 API 호출을 우선하도록 조정.

## 3. 에이전트·LLM 로직 상수
- 주요 발견
  - 에이전트 기본 플랜과 허용 워커 집합이 `src/agents/research/nodes.py:26`~`src/agents/research/nodes.py:52`에 하드코딩돼 있다.
  - 섹터 로테이션 및 리스크 스탠스 전략의 규칙 기반 매핑이 `src/agents/strategy/sector_rotator.py:31`~`src/agents/strategy/sector_rotator.py:179`, `src/agents/strategy/risk_stance.py:31`~`src/agents/strategy/risk_stace.py:158`에 존재한다.
  - 프로파일 생성 시 LLM 모델 지정/섹터 초기값이 `src/services/profile_generator.py:65`, `src/services/profile_generator.py:189`에 고정돼 있다.
- 리스크
  - 전략 파라미터 튜닝 시 코드 배포가 필요해 실험 효율이 떨어진다.
  - 특정 모델 가용성 변화(예: gpt-4o 제한) 시 즉각적인 대응이 어렵다.
- 개선 제안
  1. 전략 파라미터는 설정 테이블 또는 YAML 기반 구성으로 외부화하고, 에이전트 초기 플랜은 LangGraph 노드 내 주입 가능한 설정으로 전환.
  2. LLM 모델 선택은 `Settings`의 새 필드(예: `PROFILE_GENERATOR_MODEL`)로 승격하고 테스트 시 Mock 모델 주입 허용.

## 4. Mock 및 테스트 자산
- 주요 발견
  - 종목·섹터 매핑 및 색상 팔레트가 `src/data/stock_sectors.py` 전역에 Mock 데이터로 상수화돼 있다.
  - 섹터 대표 종목과 포트폴리오 미리보기 색상/임계치가 `src/services/sector_data_service.py:18`, `src/services/portfolio_preview_service.py:71` 등에서 고정돼 있다.
  - 테스트 및 샘플 데이터에서 `"005930"` 등 특정 종목 코드가 `tests/fixtures/` 및 `tests/unit/test_agents/test_trading_agent.py` 다수 위치에 사용된다.
- 리스크
  - 실제 데이터와 괴리 시 모델 학습·테스트 정확도가 저하될 수 있다.
  - Mock 로직이 운용 코드에 잔류하면 프로덕션 결과가 왜곡될 위험이 있다.
- 개선 제안
  1. Mock 데이터는 `ENV=test` 또는 별도 플래그로만 활성화되도록 분리.
  2. 테스트 픽스처는 공통 상수 모듈로 집약하고, 실제 데이터 매핑은 데이터레이크/DB 기반으로 대체하는 로드맵 수립.

## 우선순위 정리
| 단계 | 단기(스프린트 내) | 중기(Phase 2 전) | 비고 |
| --- | --- | --- | --- |
| 환경/설정 | DB/LLM 자격 정보 기본값 제거, `.env.example` 갱신 | TTL/포트 등 구성값을 환경 변수화 | 배포 파이프라인 반영 필요 |
| 외부 연동 | 엔드포인트 상수 → 설정으로 추출 | API 스펙 맵핑을 메타데이터화 | 문서화 및 경보 체계 구축 |
| 에이전트/LLM | 프로파일·에이전트 모델명 설정화 | 전략 파라미터 구성 파일/DB화 | 실험 관리 도구와 연동 고려 |
| Mock/테스트 | Mock 활성화 플래그 추가 | 실데이터 기반 대체 로직 구현 | 테스트 안정성 검증 필요 |

## 다음 단계 제안
1. `Settings` 리팩터링 이슈 생성 후, 환경 변수 매핑/샘플 값 이전 작업 수행.
2. 외부 서비스 인터페이스 리팩터링(엔드포인트 상수 분리)과 모의 데이터 플래그 제어를 각각 별도 작업으로 계획.
3. 전략/에이전트 구성 외부화를 위한 기술 검토 문서 작성 및 Q4 로드맵에 반영.
