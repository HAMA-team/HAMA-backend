# DB 구현 상태 점검 (2025-10-21)

## 📊 현재 DB 상태

### 존재하는 테이블

```
✅ agent_logs
✅ alerts
✅ approval_requests
✅ chat_messages
✅ chat_sessions
✅ disclosures
✅ financial_statements
✅ news
✅ orders
✅ portfolios
✅ portfolio_holdings (positions)
✅ rebalancing_history (portfolio_snapshots)
✅ realtime_prices
✅ research_reports
✅ risk_assessments
✅ stocks
✅ stock_prices
✅ stock_quotes
✅ trade_history (transactions)
✅ trading_signals
✅ users
✅ user_decisions
✅ user_preferences
⚠️  user_profiles (구 스키마 - Week 1~4와 불일치)
```

---

## ❌ 문제점: UserProfile 스키마 불일치

### 현재 DB의 user_profiles 테이블

```sql
CREATE TABLE user_profiles (
    profile_id UUID PRIMARY KEY,
    user_id UUID UNIQUE NOT NULL,
    risk_tolerance VARCHAR(20),
    investment_goal VARCHAR(50),
    investment_horizon VARCHAR(20),
    automation_level INTEGER,
    initial_capital NUMERIC(15, 2),
    monthly_contribution NUMERIC(15, 2),
    max_single_stock_ratio NUMERIC(5, 4),
    max_sector_ratio NUMERIC(5, 4),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### Week 1~4에서 필요한 UserProfile 모델

```python
# src/models/user_profile.py
class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id = Column(UUID, primary_key=True)  # ⚠️ 다름 (구: profile_id)

    # ✅ Week 1: Router & UserProfile
    expertise_level = Column(String(50))  # ❌ 없음 (새 필드)
    investment_style = Column(String(50))  # ❌ 없음 (새 필드)
    risk_tolerance = Column(String(50))  # ✅ 있음
    avg_trades_per_day = Column(Float)  # ❌ 없음 (새 필드)
    preferred_sectors = Column(JSON)  # ❌ 없음 (새 필드)
    trading_style = Column(String(50))  # ❌ 없음 (새 필드)
    portfolio_concentration = Column(Float)  # ❌ 없음 (Week 4 추가)

    # ✅ Week 3: 개인화
    technical_level = Column(String(50))  # ❌ 없음 (새 필드)
    preferred_depth = Column(String(50))  # ❌ 없음 (새 필드)
    wants_explanations = Column(Boolean)  # ❌ 없음 (새 필드)
    wants_analogies = Column(Boolean)  # ❌ 없음 (새 필드)

    # ✅ Week 4: AI 생성 프로파일
    llm_generated_profile = Column(String)  # ❌ 없음 (새 필드)

    # 메타데이터
    created_at = Column(DateTime)  # ✅ 있음
    last_updated = Column(DateTime)  # ⚠️ 다름 (구: updated_at)
```

---

## 🔍 차이점 분석

| 필드 | 구 스키마 | Week 1~4 모델 | 상태 |
|------|----------|--------------|------|
| **Primary Key** | profile_id (UUID) | user_id (UUID) | ⚠️ 다름 |
| expertise_level | ❌ 없음 | ✅ 필수 (Week 1) | ❌ 누락 |
| investment_style | ❌ 없음 | ✅ 필수 (Week 1) | ❌ 누락 |
| risk_tolerance | ✅ 있음 | ✅ 있음 | ✅ 일치 |
| avg_trades_per_day | ❌ 없음 | ✅ 필요 (Week 1) | ❌ 누락 |
| preferred_sectors | ❌ 없음 | ✅ 필수 (Week 1) | ❌ 누락 |
| trading_style | ❌ 없음 | ✅ 필요 (Week 1) | ❌ 누락 |
| portfolio_concentration | ❌ 없음 | ✅ 필요 (Week 4) | ❌ 누락 |
| technical_level | ❌ 없음 | ✅ 필수 (Week 3) | ❌ 누락 |
| preferred_depth | ❌ 없음 | ✅ 필수 (Week 3) | ❌ 누락 |
| wants_explanations | ❌ 없음 | ✅ 필수 (Week 3) | ❌ 누락 |
| wants_analogies | ❌ 없음 | ✅ 필수 (Week 3) | ❌ 누락 |
| llm_generated_profile | ❌ 없음 | ✅ 필수 (Week 4) | ❌ 누락 |

**결론:** 구 스키마에는 Week 1~4에서 필요한 핵심 필드들이 대부분 누락되어 있음.

---

## ✅ 해결 방안

### 방안 1: DB 초기화 후 재생성 (권장 ⭐)

**장점:**
- 모든 모델이 최신 상태로 생성
- 스키마 불일치 문제 완전 해결
- 개발 환경에 적합

**단점:**
- 기존 데이터 손실
- 프로덕션 환경에서는 불가능

**실행 방법:**
```bash
# 1. DB 초기화
PYTHONPATH=. python -c "from src.models.database import Base, engine; Base.metadata.drop_all(engine)"

# 2. 모든 테이블 재생성
PYTHONPATH=. python -c "from src.models.database import Base, engine; Base.metadata.create_all(engine)"

# 3. Alembic 마이그레이션 초기화
alembic stamp head
```

**적용 시점:** Phase 1 개발 완료 후 (지금)

---

### 방안 2: 마이그레이션으로 스키마 변경 (프로덕션용)

**장점:**
- 기존 데이터 보존
- 점진적 변경 가능

**단점:**
- 복잡한 마이그레이션 스크립트 필요
- 데이터 변환 로직 필요

**실행 방법:**
```bash
# 1. 수동으로 마이그레이션 생성
alembic revision -m "migrate_user_profiles_to_week4_schema"

# 2. 마이그레이션 파일 수정
# - user_profiles 테이블 삭제
# - 새로운 user_profiles 테이블 생성
# - 기존 데이터 마이그레이션

# 3. 적용
alembic upgrade head
```

**적용 시점:** 실제 사용자 데이터가 있을 때 (Phase 2 이후)

---

### 방안 3: 테이블명 변경 (임시 방안)

**실행 방법:**
```sql
-- 기존 테이블 백업
ALTER TABLE user_profiles RENAME TO user_profiles_old;

-- 새 테이블 생성 (SQLAlchemy로)
```

**적용 시점:** 개발 중 기존 데이터를 참고해야 할 때

---

## 🎯 권장 조치 (즉시 실행)

### Phase 1 (현재) - DB 초기화

```bash
# ⚠️ 경고: 모든 데이터가 삭제됩니다!

# 1. DB 초기화
PYTHONPATH=. python -c "
from src.models.database import Base, engine
print('🗑️  Dropping all tables...')
Base.metadata.drop_all(engine)
print('✅ All tables dropped')
"

# 2. 모든 모델 다시 생성
PYTHONPATH=. python -c "
from src.models.database import Base, engine
from src.models import user, agent, portfolio, chat, stock, user_profile

print('🔨 Creating all tables...')
Base.metadata.create_all(engine)
print('✅ All tables created')
"

# 3. Alembic 히스토리 정리
alembic stamp head

# 4. 확인
PYTHONPATH=. python -c "
from src.models.database import engine
from sqlalchemy import inspect

inspector = inspect(engine)
tables = inspector.get_table_names()
print(f'📊 Total tables: {len(tables)}')
for table in sorted(tables):
    print(f'  - {table}')
"
```

---

## 📝 Alembic 마이그레이션 상태

### 현재 마이그레이션 히스토리

```
1b4c9dc1c3bf (HEAD) - create_chat_history_tables
  - chat_sessions
  - chat_messages
```

### 누락된 마이그레이션

- ❌ user_profiles (Week 1~4)
- ❌ 기타 모든 테이블 (이미 수동 생성됨)

### 정리 필요성

현재 상태:
- DB에 많은 테이블이 이미 존재
- Alembic 히스토리는 chat_sessions/messages만 포함
- 불일치 상태

권장 조치:
1. DB 초기화
2. SQLAlchemy로 모든 테이블 생성
3. Alembic head로 마킹
4. 이후 변경사항만 마이그레이션으로 관리

---

## 🔧 Week 1~4 기능별 DB 요구사항

### Week 1: Router & UserProfile ✅

**필요 테이블:**
- ✅ `user_profiles` (수정 필요)
- ✅ `chat_sessions`
- ✅ `chat_messages`

**필요 필드 (user_profiles):**
```python
user_id, expertise_level, investment_style, risk_tolerance,
avg_trades_per_day, preferred_sectors, trading_style
```

**현재 상태:** ⚠️ 테이블은 있지만 필드 대부분 누락

---

### Week 2: Research Agent ReAct ✅

**필요 테이블:**
- ✅ `stocks` (종목 정보)
- ✅ `financial_statements` (재무제표)
- ✅ `disclosures` (공시)

**현재 상태:** ✅ 모두 존재

---

### Week 3: 개인화 & Thinking Trace ✅

**필요 필드 (user_profiles):**
```python
technical_level, preferred_depth, wants_explanations, wants_analogies
```

**현재 상태:** ❌ user_profiles에 없음

**추가 요구사항:**
- ✅ `chat_messages` (대화 히스토리)

---

### Week 4: AI Profile & Memory ✅

**필요 필드 (user_profiles):**
```python
llm_generated_profile, portfolio_concentration
```

**현재 상태:** ❌ user_profiles에 없음

**추가 요구사항:**
- ✅ `chat_messages` (Memory 학습용)
- ✅ `portfolio_holdings` (포트폴리오 분석용)

---

## 📋 최종 체크리스트

### 즉시 실행 (Phase 1 완료 전)

- [ ] DB 초기화 실행
- [ ] user_profiles 테이블 확인 (Week 1~4 필드 포함)
- [ ] chat_sessions/messages 테이블 확인
- [ ] Alembic head 마킹

### Phase 2 준비

- [ ] 실제 사용자 데이터 마이그레이션 계획
- [ ] Alembic 마이그레이션 전략 수립
- [ ] 백업/복구 프로세스 정의

---

## 🎓 교훈

1. **Alembic 사용 원칙**
   - 모든 스키마 변경은 마이그레이션으로 관리
   - 수동 테이블 생성 지양

2. **모델 변경 시**
   - 즉시 마이그레이션 생성
   - DB와 모델 동기화 유지

3. **Phase 별 접근**
   - Phase 1 (개발): DB 초기화 허용
   - Phase 2 (프로덕션): 마이그레이션 필수

---

**작성일:** 2025-10-21
**작성자:** Claude (AI Assistant)
**현재 Phase:** Phase 1 (80% 완성)
