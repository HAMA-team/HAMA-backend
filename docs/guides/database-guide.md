# 데이터베이스 접근 정책

**HAMA 프로젝트는 동기식 SQLAlchemy를 사용합니다.**

## 원칙

- ✅ **동기식 DB 세션만 사용** (SQLAlchemy 1.4 스타일)
- ❌ **비동기 DB 세션 사용 금지** (AsyncSession, AsyncEngine 사용 안 함)
- ✅ **FastAPI는 비동기이지만 DB 접근은 동기로 처리** (문제없음)

## 사용 방법

### 1. FastAPI 엔드포인트에서 (권장)

```python
from fastapi import Depends
from sqlalchemy.orm import Session
from src.models.database import get_db

@router.post("/api/endpoint")
async def endpoint(db: Session = Depends(get_db)):
    """비동기 엔드포인트지만 DB는 동기로 접근"""
    user = db.query(User).filter(User.id == user_id).first()
    return user
```

### 2. 일반 함수/서비스에서

```python
from src.models.database import SessionLocal

def some_service_function():
    db = SessionLocal()
    try:
        result = db.query(Model).all()
        return result
    finally:
        db.close()
```

## 금지 패턴 ❌

```python
# ❌ 잘못된 예 1: AsyncSession import
from sqlalchemy.ext.asyncio import AsyncSession


# ❌ 잘못된 예 2: await db.execute()
result = await db.execute(query)  # 동기 세션은 await 불가
```

## 왜 동기식인가?

### 장점:
- 코드 단순화 (async/await 복잡도 제거)
- FastAPI에서도 동기 DB 접근 지원 (Depends + 스레드풀)
- 테스트 작성 용이
- SQLAlchemy 2.0 마이그레이션 복잡도 회피

### 성능:
- MVP에서는 동시 사용자 수가 많지 않아 성능 차이 미미
- Phase 2에서 필요 시 비동기로 전환 검토
