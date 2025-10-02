# PostgreSQL 로컬 데이터베이스 설정 가이드

캡스톤 프로젝트를 위한 간단한 PostgreSQL 로컬 구성 가이드입니다.

## 1. PostgreSQL 설치

### macOS (Homebrew)

```bash
# PostgreSQL 설치
brew install postgresql@16

# PostgreSQL 서비스 시작
brew services start postgresql@16

# PATH 설정 (필요시)
echo 'export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### macOS (Postgres.app) - 추천 ⭐

가장 간단한 방법:

1. [Postgres.app](https://postgresapp.com/) 다운로드
2. 앱 실행 → Initialize
3. 완료!

### Ubuntu/Debian

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

## 2. 데이터베이스 생성

### 방법 1: 커맨드라인 (추천)

```bash
# 현재 사용자로 데이터베이스 생성
createdb hama_db

# 확인
psql -l
```

### 방법 2: psql 사용

```bash
# psql 접속
psql postgres

# 데이터베이스 생성
CREATE DATABASE hama_db;

# 확인
\l

# 종료
\q
```

## 3. 데이터베이스 연결 확인

```bash
# 생성한 DB에 접속
psql hama_db

# 연결 정보 확인
\conninfo

# 종료
\q
```

## 4. .env 파일 설정

프로젝트 루트의 `.env` 파일이 이미 설정되어 있습니다:

```bash
DATABASE_URL=postgresql://elaus@localhost:5432/hama_db
```

**주의**: `elaus` 부분은 본인의 macOS 사용자명입니다. 다른 사용자면 변경하세요.

### 사용자명 확인 방법

```bash
whoami
```

### 연결 문자열 형식

```
postgresql://[사용자명]:[비밀번호]@[호스트]:[포트]/[데이터베이스명]
```

**로컬 개발 예시:**
- 비밀번호 없음: `postgresql://username@localhost:5432/hama_db`
- 비밀번호 있음: `postgresql://username:password@localhost:5432/hama_db`

## 5. 테이블 생성 (Alembic 마이그레이션)

```bash
# Alembic 초기화 (처음 한번만)
alembic init alembic

# 마이그레이션 파일 생성
alembic revision --autogenerate -m "Initial migration"

# 마이그레이션 실행
alembic upgrade head
```

### 또는 직접 테이블 생성 (간단한 방법)

Python 스크립트로 직접 생성:

```python
# init_db.py
from src.models.database import Base, engine, init_db

if __name__ == "__main__":
    print("Creating database tables...")
    init_db()
    print("Done!")
```

```bash
python init_db.py
```

## 6. 연결 테스트

```bash
# Python으로 연결 테스트
python -c "
from src.config.settings import settings
from sqlalchemy import create_engine
engine = create_engine(settings.DATABASE_URL)
conn = engine.connect()
print('✅ Database connection successful!')
conn.close()
"
```

## 7. 유용한 PostgreSQL 명령어

### psql 내부 명령어

```sql
-- 데이터베이스 목록
\l

-- 테이블 목록
\dt

-- 테이블 구조 확인
\d table_name

-- 사용자 목록
\du

-- 현재 연결 정보
\conninfo

-- 종료
\q
```

### SQL 쿼리 예시

```sql
-- 테이블 확인
SELECT * FROM stocks LIMIT 10;

-- 테이블 생성 확인
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public';
```

## 8. GUI 도구 (선택사항)

### pgAdmin (공식 GUI)

```bash
brew install --cask pgadmin4
```

### TablePlus (추천) ⭐

- [TablePlus 다운로드](https://tableplus.com/)
- 직관적이고 사용하기 쉬움
- 무료 버전으로 충분

### DBeaver (무료 오픈소스)

```bash
brew install --cask dbeaver-community
```

## 9. 데이터베이스 백업 & 복원

### 백업

```bash
# 전체 백업
pg_dump hama_db > hama_backup.sql

# 압축 백업
pg_dump hama_db | gzip > hama_backup.sql.gz
```

### 복원

```bash
# 기본 복원
psql hama_db < hama_backup.sql

# 압축 파일 복원
gunzip -c hama_backup.sql.gz | psql hama_db
```

## 10. 트러블슈팅

### "connection refused" 에러

```bash
# PostgreSQL 실행 상태 확인
brew services list

# 재시작
brew services restart postgresql@16
```

### "database does not exist" 에러

```bash
# 데이터베이스 다시 생성
createdb hama_db
```

### "role does not exist" 에러

```bash
# 사용자 생성
createuser -s elaus  # 본인의 사용자명으로 변경
```

### 포트 충돌 (5432)

```bash
# 다른 포트로 변경 (예: 5433)
# .env 파일 수정
DATABASE_URL=postgresql://elaus@localhost:5433/hama_db
```

## 11. 개발 팁

### 개발 중 데이터 초기화

```bash
# 데이터베이스 삭제 후 재생성
dropdb hama_db
createdb hama_db

# 테이블 재생성
python init_db.py
```

### 테스트용 샘플 데이터 입력

```sql
-- psql hama_db에서 실행
INSERT INTO stocks (stock_code, stock_name, market, sector)
VALUES
  ('005930', '삼성전자', 'KOSPI', '반도체'),
  ('000660', 'SK하이닉스', 'KOSPI', '반도체'),
  ('035420', 'NAVER', 'KOSPI', 'IT서비스');
```

## 12. 프로덕션 고려사항 (캡스톤 발표 시)

### 로컬 개발 (현재)
- 간단한 설정
- 백업 필요 없음
- 비밀번호 선택사항

### 만약 배포한다면 (참고용)
- ✅ 강력한 비밀번호 설정
- ✅ SSL 연결 설정
- ✅ 정기 백업 설정
- ✅ 연결 풀 최적화
- ✅ 모니터링 설정

하지만 캡스톤 프로젝트에서는 **로컬 개발만으로 충분**합니다!

## 추가 참고 자료

- [PostgreSQL 공식 문서](https://www.postgresql.org/docs/)
- [SQLAlchemy 문서](https://docs.sqlalchemy.org/)
- [Alembic 문서](https://alembic.sqlalchemy.org/)

---

**문제 발생 시**: PostgreSQL은 로컬 개발 환경에서 가장 안정적인 DB입니다. 문제가 생기면 재설치가 가장 빠른 해결책입니다!