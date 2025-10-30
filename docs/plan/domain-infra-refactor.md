# Domain/Infrastructure 1차 리팩터링 설계안

## 배경
- 현재 `src/services`가 외부 API 호출, ORM 세션, 도메인 계산을 동시에 수행하면서 레이어 간 경계가 불명확합니다.
- SQLAlchemy 모델이 곧바로 도메인 엔티티로 사용되어 인프라 세부 구현(ORM 스키마)에 강하게 결합되어 있습니다.
- 테스트 및 교체 가능성을 높이기 위해 Repository 추상화가 일부 모듈에만 적용된 상태라 일관성이 떨어집니다.

## 리팩터링 목표
1. **도메인 계층 순수화**: 도메인 모델을 ORM으로부터 분리해 비즈니스 규칙을 독립적으로 다룰 수 있게 합니다.
2. **인프라 의존성 역전**: Repository 인터페이스를 정의하고, SQLAlchemy 구현은 인프라 계층으로 격리합니다.
3. **애플리케이션 서비스 정리**: 요청 흐름을 담당하는 유즈케이스 계층을 정의하고, 외부 시스템 연동은 별도 어댑터로 분리합니다.
4. **점진적 마이그레이션**: 기존 API/에이전트를 유지하면서 파일 이동과 네이밍 변경을 단계적으로 수행합니다.

## 타겟 영역 및 우선순위
| 우선순위 | 영역 | 현재 문제 | 조치 요약 |
| --- | --- | --- | --- |
| 1 | `stock` 관련 모델/서비스 | 서비스에서 ORM 모델 직접 조작 (`src/services/stock_data_service.py`) | 도메인 엔티티 도입, Repository 인터페이스 정의 |
| 2 | 포트폴리오 서비스 | `PortfolioService`가 세션/ORM/외부 API 의존 | 도메인 서비스 vs 인프라 어댑터 분리, 의존성 주입 도입 |
| 3 | 공용 서비스 팩토리 | 전역 싱글톤(`stock_data_service`, `portfolio_service`) | DI 컨테이너 or FastAPI Depends로 교체 |

## 제안 구조
```
src/
├── domain/
│   ├── stock/
│   │   ├── entities.py         # Stock, StockPrice (순수 데이터 클래스)
│   │   └── services.py         # 도메인 로직 (예: 수익률 계산)
│   ├── portfolio/
│   │   ├── entities.py
│   │   └── services.py
│   └── __init__.py
├── application/
│   ├── stock/
│   │   └── queries.py          # 주식 조회 유즈케이스 (서비스 계층 → Repository 인터페이스 사용)
│   ├── portfolio/
│   │   └── commands.py
│   └── __init__.py
├── infrastructure/
│   ├── db/
│   │   ├── models/
│   │   │   ├── stock.py        # 기존 SQLAlchemy 모델 이동
│   │   │   └── portfolio.py
│   │   └── repositories/
│   │       ├── stock_repository.py
│   │       └── portfolio_repository.py
│   ├── integrations/
│   │   ├── kis_service.py      # 외부 API 어댑터
│   │   └── dart_service.py
│   └── cache/
│       └── redis_cache.py
└── interfaces/
    └── api/                    # FastAPI 라우터 → application 계층 호출
```

## 단계별 실행 안
1. **폴더 스켈레톤 추가**  
   - `src/domain`, `src/application`, `src/infrastructure/db/models` 생성.  
   - 기존 모듈을 즉시 이동하지 않고, 신규 계층에 필요한 인터페이스/엔티티를 우선 정의합니다.

2. **Stock 도메인 분리 (스파이크)**  
   - `src/domain/stock/entities.py`에 `Stock`, `StockPrice` Pydantic 또는 dataclass 정의.  
   - `src/repositories/stock_repository.py`를 인터페이스 + 구현으로 분리 (`src/domain/stock/repositories.py` 인터페이스, 구현은 `src/infrastructure/db/repositories/stock_repository.py`).  
   - `StockDataService`를 `application/stock/queries.py`로 쪼갠 후, 외부 API/캐시 접근은 `infrastructure` 어댑터로 이동.

3. **포트폴리오 서비스 재구성**  
   - `PortfolioService`를 유즈케이스 계층으로 옮기고, KIS 연동/DB 접근/캐시를 의존성으로 주입.  
   - FastAPI 라우터와 LangGraph 노드에서 새로운 유즈케이스를 사용하도록 어댑터 추가.

4. **전역 싱글톤 제거**  
   - FastAPI `Depends` 및 스타트업 훅에서 의존성 등록.  
   - Celery Worker, LangGraph 초기화 코드도 동일한 팩토리/컨테이너에서 가져오도록 통일.

5. **추가 도메인 적용**  
   - 차례로 `artifact`, `user_profile` 등 나머지 서비스에도 동일한 패턴을 반영.

## 리스크 및 완화
- **마이그레이션 기간 중 순환 참조 위험**: 각 단계에서 인터페이스를 먼저 정의하고 구현을 별도 모듈로 분리해 순환 의존을 방지합니다.
- **테스트 체계 영향**: 기존 테스트가 ORM 모델에 의존하므로, 도메인 엔티티 도입 시 어댑터 테스트를 추가해야 합니다. 우선 `tests/test_api` 및 `tests/test_agents`에 대한 회귀 테스트를 우선 실행합니다.
- **배포 영향**: 모듈 경로 변경에 따른 ImportError가 발생할 수 있으므로, 단계별 PR에서 FastAPI 라우터와 Celery 초기화 코드를 모두 검증합니다.

## 즉각적인 액션 아이템
1. 폴더 구조 초안 및 `pyproject.toml` 패키지 경로 업데이트 설계.
2. Stock 도메인 스파이크 작업 분량 추정 후 TODO 리스트화.
3. FastAPI 의존성 주입 패턴(`Depends`)과 Celery 초기화 패턴 정리 문서 초안 작성.

