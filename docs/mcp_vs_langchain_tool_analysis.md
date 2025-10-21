# MCP vs LangChain Tool 비교 분석

## 현재 상황 파악

### 사용 가능한 MCP 서버 (Claude Code CLI 제공)

현재 시스템에서 사용 가능한 MCP 도구:

1. **IDE Integration**
   - `mcp__ide__getDiagnostics`: 코드 진단 정보 조회

2. **Context7 (라이브러리 문서)**
   - `mcp__context7__resolve-library-id`: 라이브러리 ID 해석
   - `mcp__context7__get-library-docs`: 라이브러리 문서 조회

3. **KIS Open API (한국투자증권)** ⭐
   - `mcp__kis-open-api-kis-code-assistant-mcp__search_domestic_stock_api`: 국내 주식 API 검색
   - `mcp__kis-open-api-kis-code-assistant-mcp__read_source_code`: 소스 코드 읽기

### 현재 프로젝트의 LangChain Tool

`src/agents/research/tools.py`에 정의된 도구:

1. `get_stock_price` - 주가 데이터 조회 (FinanceDataReader)
2. `get_basic_ratios` - 재무 비율 (DART API)
3. `get_financial_statement` - 재무제표 (DART API)
4. `get_company_info` - 기업 정보 (DART API)
5. `calculate_dcf_valuation` - DCF 밸류에이션
6. `get_sector_comparison` - 업종 비교

---

## 비교 분석

### 1. 아키텍처 차이

| 항목 | MCP | LangChain Tool |
|------|-----|----------------|
| **실행 위치** | 외부 프로세스 (서버) | 프로세스 내부 (함수) |
| **통신 방식** | IPC/RPC (JSON-RPC) | 직접 함수 호출 |
| **격리성** | 완전 격리 (프로세스 분리) | 같은 프로세스 |
| **상태 관리** | 서버가 독립적으로 관리 | 애플리케이션 컨텍스트 공유 |

**MCP 구조:**
```
LangGraph Agent
      ↓ (JSON-RPC)
MCP Server (별도 프로세스)
      ↓
External API (KIS, DART 등)
```

**LangChain Tool 구조:**
```
LangGraph Agent
      ↓ (함수 호출)
@tool 함수
      ↓
External API
```

---

### 2. 장단점 비교

#### MCP 장점 ✅

1. **프로세스 격리**
   - 도구 실행 실패가 메인 애플리케이션에 영향 없음
   - 메모리 누수, 크래시 격리

2. **표준화된 인터페이스**
   - JSON-RPC 표준 프로토콜
   - 언어 중립적 (Python, TypeScript, Rust 등)

3. **외부 관리**
   - MCP 서버는 독립적으로 업데이트 가능
   - 버전 관리 독립적

4. **보안**
   - 샌드박스 환경 (권한 제한)
   - API 키 등을 MCP 서버에만 저장

5. **재사용성**
   - 여러 애플리케이션에서 동일한 MCP 서버 공유
   - Claude Desktop, Claude Code CLI 등에서 공통 사용

#### MCP 단점 ❌

1. **성능 오버헤드**
   - IPC/RPC 통신 비용
   - 직접 호출 대비 느림 (수 ms ~ 수십 ms)

2. **복잡도 증가**
   - MCP 서버 설정/관리 필요
   - 디버깅 어려움 (프로세스 간 통신)

3. **의존성**
   - MCP 서버가 실행 중이어야 함
   - 서버 다운 시 도구 사용 불가

4. **컨텍스트 공유 제한**
   - 애플리케이션 상태 접근 어려움
   - DB 세션, 캐시 등 공유 불가

#### LangChain Tool 장점 ✅

1. **성능**
   - 직접 함수 호출 (오버헤드 최소)
   - 빠른 응답 (마이크로초 단위)

2. **간단함**
   - `@tool` decorator만으로 정의
   - 별도 서버 불필요

3. **컨텍스트 접근**
   - DB 세션, Redis 캐시 직접 사용
   - 애플리케이션 상태 공유

4. **디버깅 용이**
   - 일반 Python 함수
   - 표준 디버거 사용 가능

5. **유연성**
   - 커스텀 로직 자유롭게 구현
   - LangGraph State와 통합 용이

#### LangChain Tool 단점 ❌

1. **격리 부족**
   - 도구 실패 시 전체 프로세스 영향 가능
   - 메모리 누수 위험

2. **재사용성 제한**
   - 다른 애플리케이션에서 재사용 어려움
   - Python 전용

3. **보안**
   - API 키가 애플리케이션 환경에 노출
   - 격리된 권한 관리 어려움

---

### 3. 사용 사례별 권장사항

#### MCP를 사용해야 하는 경우 ⭐

1. **외부 시스템 통합**
   - KIS Open API (한국투자증권) ← **현재 MCP 서버 존재!**
   - 타사 API (보안 중요)
   - 레거시 시스템

2. **격리가 중요한 작업**
   - 불안정한 외부 API
   - 리소스 집약적 작업 (크롤링, 이미지 처리)

3. **다중 애플리케이션 공유**
   - 여러 프로젝트에서 사용하는 도구
   - Frontend + Backend 공통 도구

#### LangChain Tool을 사용해야 하는 경우 ⭐

1. **내부 데이터 접근**
   - DART API (이미 구현됨) ✅
   - FinanceDataReader ✅
   - PostgreSQL 조회

2. **성능이 중요한 작업**
   - 자주 호출되는 도구 (캐시 조회)
   - 실시간 응답 필요

3. **복잡한 비즈니스 로직**
   - 애플리케이션 상태 의존적
   - DB 트랜잭션 필요

---

## 💡 HAMA 프로젝트 권장사항

### 현재 구조 유지 (LangChain Tool) ✅

**유지해야 할 도구:**
- `get_stock_price` - FinanceDataReader (내부 로직)
- `get_basic_ratios` - DART API (이미 잘 구현됨)
- `get_financial_statement` - DART API
- `get_company_info` - DART API
- `calculate_dcf_valuation` - 복잡한 비즈니스 로직
- `get_sector_comparison` - DB/캐시 의존적

**이유:**
- 이미 안정적으로 작동 중
- 성능 우수
- DB/캐시와 통합 잘 됨
- 디버깅 용이

### MCP로 전환 고려 (Phase 2) ⭐

**KIS Open API 도구 (실시간 매매)**

```python
# Phase 2: MCP 통합 예시
from langchain_core.tools import Tool

# MCP 도구를 LangChain Tool로 래핑
kis_get_price = Tool.from_function(
    func=lambda stock_code: mcp_call(
        "mcp__kis-open-api-kis-code-assistant-mcp__get_real_time_price",
        {"stock_code": stock_code}
    ),
    name="get_real_time_price_kis",
    description="KIS Open API를 통한 실시간 시세 조회"
)
```

**전환 대상:**
1. **실시간 시세** (KIS Open API) - MCP 서버 이미 존재!
2. **실제 매매 실행** (보안 중요)
3. **뉴스 크롤링** (별도 프로세스 권장)

**이유:**
- 보안: API 키 격리
- 안정성: 매매 실패가 메인 앱에 영향 없음
- 재사용: 다른 프로젝트에서도 사용 가능

---

## 🏗️ 하이브리드 아키텍처 (권장)

```
Research Agent (LangGraph)
      ↓
┌─────────────────┴─────────────────┐
│                                    │
▼ (직접 호출)                  ▼ (MCP)
LangChain Tools               MCP Servers
- get_stock_price            - KIS Real-time Price
- get_financial_statement    - KIS Trading
- calculate_dcf              - News Crawler
  (내부 로직, 성능 중요)         (외부 API, 보안 중요)
```

### 통합 예시 (Week 2 Research Agent)

```python
# src/agents/research/tools.py

from langchain_core.tools import tool

# ===== LangChain Tools (유지) =====

@tool
async def get_stock_price(stock_code: str) -> dict:
    """주가 조회 (FinanceDataReader) - 빠르고 안정적"""
    # 기존 구현 유지
    pass

@tool
async def get_financial_statement(stock_code: str) -> dict:
    """재무제표 조회 (DART API) - DB 캐싱 활용"""
    # 기존 구현 유지
    pass

# ===== MCP Tools (Phase 2 추가) =====

@tool
async def get_real_time_price_kis(stock_code: str) -> dict:
    """실시간 시세 (KIS Open API) - MCP 서버 사용"""
    # MCP 서버 호출
    result = await mcp_client.call(
        server="kis-open-api",
        tool="get_real_time_price",
        args={"stock_code": stock_code}
    )
    return result

@tool
async def execute_trade_kis(stock_code: str, quantity: int, order_type: str) -> dict:
    """매매 실행 (KIS Open API) - 보안 격리"""
    # MCP 서버 호출
    result = await mcp_client.call(
        server="kis-open-api",
        tool="place_order",
        args={
            "stock_code": stock_code,
            "quantity": quantity,
            "order_type": order_type
        }
    )
    return result
```

---

## 📊 성능 비교 (예상)

| 작업 | LangChain Tool | MCP | 차이 |
|------|---------------|-----|------|
| **간단한 조회** (캐시) | 0.1 ms | 5-10 ms | 50-100배 느림 |
| **DB 쿼리** | 10 ms | 20 ms | 2배 느림 |
| **외부 API 호출** | 200 ms | 210 ms | 5% 느림 (무시 가능) |
| **복잡한 계산** (DCF) | 50 ms | 60 ms | 20% 느림 |

**결론:**
- 외부 API 호출 시 MCP 오버헤드는 무시 가능 (5% 이내)
- 내부 로직/캐시 조회 시 LangChain Tool이 압도적으로 빠름

---

## ✅ 최종 권장사항

### 현재 (Phase 1) - LangChain Tool 유지

```
✅ 모든 도구를 LangChain Tool로 유지
✅ 성능 우수, 디버깅 용이
✅ 이미 안정적으로 작동 중
```

### Phase 2 - 하이브리드 전환

```
1. KIS Open API → MCP 서버 사용 (보안, 격리)
   - get_real_time_price_kis (MCP)
   - execute_trade_kis (MCP)

2. 내부 로직 → LangChain Tool 유지
   - get_stock_price (기존)
   - get_financial_statement (기존)
   - calculate_dcf_valuation (기존)

3. 선택적 MCP 전환
   - 뉴스 크롤링 → MCP (리소스 격리)
   - 차트 분석 → MCP (이미지 처리)
```

---

## 🔧 구현 가이드

### MCP 서버 연결 방법 (Phase 2)

1. **MCP 클라이언트 설치**
```bash
pip install mcp
```

2. **MCP 설정 파일** (`mcp.json`)
```json
{
  "mcpServers": {
    "kis-open-api": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-kis-open-api"],
      "env": {
        "KIS_APP_KEY": "${KIS_APP_KEY}",
        "KIS_APP_SECRET": "${KIS_APP_SECRET}"
      }
    }
  }
}
```

3. **LangChain Tool 래핑**
```python
from langchain_core.tools import Tool
from mcp import Client

mcp_client = Client()

@tool
async def get_real_time_price_kis(stock_code: str) -> dict:
    """KIS Open API 실시간 시세 (MCP)"""
    result = await mcp_client.call_tool(
        server="kis-open-api",
        tool="get_real_time_price",
        arguments={"stock_code": stock_code}
    )
    return result
```

---

## 📝 요약

| 기준 | 승자 | 근거 |
|------|------|------|
| **성능** | LangChain Tool ✅ | 50-100배 빠름 (내부 로직) |
| **보안** | MCP ✅ | API 키 격리, 권한 관리 |
| **디버깅** | LangChain Tool ✅ | 표준 Python 디버거 |
| **재사용성** | MCP ✅ | 언어 중립적, 다중 앱 지원 |
| **복잡도** | LangChain Tool ✅ | 간단한 구현 |
| **격리성** | MCP ✅ | 프로세스 분리 |

**최종 결론:**
- **Phase 1 (현재)**: 모든 도구를 **LangChain Tool**로 유지 ✅
- **Phase 2 (실제 매매)**: **KIS Open API**만 **MCP**로 전환 ⭐
- **장기적**: 하이브리드 아키텍처 (도구 특성에 따라 선택)
