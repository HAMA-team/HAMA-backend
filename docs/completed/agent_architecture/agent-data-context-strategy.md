# AI 에이전트 데이터 컨텍스트 제공 전략

**작성일**: 2025-10-03
**목적**: AI 에이전트가 DART 공시, 주가 정보 등의 데이터를 효과적으로 얻는 방법 설계

---

## 📋 핵심 질문

1. **DART 공시 정보**를 AI가 어떻게 얻을 수 있을까?
2. **주가 정보**를 AI가 어떻게 얻을 수 있을까?
3. **MCP 외 다른 방법**은 무엇이 있을까?
4. 각 방법의 **장단점과 트레이드오프**는?
5. **HAMA 프로젝트에 가장 적합한 방법**은?

---

## 🔍 데이터 컨텍스트 제공 방법론 비교

### 방법 1: MCP (Model Context Protocol)

**개념**: Claude가 정의한 표준 프로토콜로, 외부 데이터 소스를 LLM에 연결

**구조**:
```
LLM (Claude/GPT)
    ↕ (MCP Protocol)
MCP Server (한투 API, DART API 등)
    ↕
External Data Sources
```

**장점**:
- ✅ LLM에서 **직접 실시간 데이터 접근**
- ✅ 표준화된 프로토콜 (Claude 공식 지원)
- ✅ Tool calling 통합 용이

**단점**:
- ❌ **별도 MCP 서버 구동 필요** (추가 인프라)
- ❌ 설정 복잡도 높음
- ❌ 캐싱 전략 직접 구현 필요
- ❌ 에이전트 독립성 저하 (MCP 서버 의존)

**적용 시나리오**:
- KIS API 실시간 시세 (Phase 3)
- 실시간 매매 실행 시

**현재 상태**:
- 한투 API MCP는 이미 연결됨 (`mcp__kis-open-api-kis-code-assistant-mcp`)
- 하지만 **Phase 1에서는 미사용** (Mock 데이터로 충분)

**평가**: ⭐⭐⭐☆☆ (Phase 3에서 필요, 현재는 오버엔지니어링)

---

### 방법 2: Service Layer + Repository Pattern ⭐ 추천

**개념**: 클린 아키텍처 기반, 데이터 접근 로직을 별도 레이어로 분리

**구조**:
```
Agents (Business Logic)
    ↓ 의존
Services (Data Access Logic)
    ↓ 의존
Repositories (Data Source Abstraction)
    ↓ 의존
External APIs (FinanceDataReader, DART, etc.)
```

**구현 예시**:
```python
# src/services/stock_data_service.py
class StockDataService:
    """주가 데이터 서비스"""

    def __init__(self):
        self.cache = {}  # Redis로 대체 가능

    async def get_stock_price(self, stock_code: str, days: int = 30):
        # 캐시 확인
        if stock_code in self.cache:
            return self.cache[stock_code]

        # FinanceDataReader 호출
        import FinanceDataReader as fdr
        df = fdr.DataReader(stock_code, start=f'-{days}days')

        # 캐싱
        self.cache[stock_code] = df
        return df

# src/services/dart_service.py
class DARTService:
    """DART 공시 서비스"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://opendart.fss.or.kr/api"

    async def get_financial_statement(self, corp_code: str, year: int):
        # DART API 호출
        url = f"{self.base_url}/fnlttSinglAcntAll.json"
        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp_code,
            "bsns_year": year,
            "reprt_code": "11011"  # 사업보고서
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            return response.json()

# src/agents/research.py
class ResearchAgent(BaseAgent):
    def __init__(self):
        super().__init__("research_agent")
        self.stock_service = StockDataService()
        self.dart_service = DARTService(settings.DART_API_KEY)

    async def process(self, input_data: AgentInput):
        # 서비스 레이어 사용
        stock_data = await self.stock_service.get_stock_price("005930")
        financial_data = await self.dart_service.get_financial_statement(...)

        # 비즈니스 로직 (분석)
        analysis = self._analyze(stock_data, financial_data)
        return AgentOutput(...)
```

**장점**:
- ✅ **클린 아키텍처 준수** (의존성 방향 올바름)
- ✅ **캐싱 전략 쉽게 구현** (Service Layer에서)
- ✅ **테스트 용이** (Mock Service 주입)
- ✅ **에이전트 독립성 유지** (Service만 교체 가능)
- ✅ **확장성 높음** (새로운 데이터 소스 추가 쉬움)

**단점**:
- ⚠️ 초기 구현 시간 필요
- ⚠️ 레이어가 많아짐 (하지만 장기적으로 유리)

**적용 시나리오**:
- **모든 데이터 소스** (FinanceDataReader, DART, 뉴스 크롤링)
- Phase 2 핵심 구현 방식

**평가**: ⭐⭐⭐⭐⭐ **최우선 추천**

---

### 방법 3: Data Collection Agent + Shared Cache

**개념**: 9개 에이전트 중 하나인 Data Collection Agent가 모든 데이터 수집 담당

**구조**:
```
Master Agent
    ↓
┌───────────────────┐
│Data Collection    │ → Cache Layer (Redis)
│Agent              │
└───────────────────┘
    ↓ (데이터 제공)
Other Agents (Research, Strategy, etc.)
```

**구현 예시**:
```python
# src/agents/data_collection.py
class DataCollectionAgent(BaseAgent):
    """모든 데이터 수집을 담당하는 에이전트"""

    def __init__(self):
        super().__init__("data_collection_agent")
        self.stock_service = StockDataService()
        self.dart_service = DARTService()
        self.cache = CacheManager()

    async def process(self, input_data: AgentInput):
        data_type = input_data.context.get("data_type")

        if data_type == "stock_price":
            return await self._fetch_stock_price(input_data)
        elif data_type == "financial_statement":
            return await self._fetch_financial_statement(input_data)
        elif data_type == "dart_disclosure":
            return await self._fetch_dart_disclosure(input_data)

    async def _fetch_stock_price(self, input_data):
        stock_code = input_data.context["stock_code"]

        # 캐시 확인
        cached = await self.cache.get(f"stock_price:{stock_code}")
        if cached:
            return AgentOutput(status="success", data=cached)

        # FinanceDataReader 호출
        data = await self.stock_service.get_stock_price(stock_code)

        # 캐싱 (60초 TTL)
        await self.cache.set(f"stock_price:{stock_code}", data, ttl=60)

        return AgentOutput(status="success", data=data)

# src/agents/research.py
class ResearchAgent(BaseAgent):
    async def process(self, input_data: AgentInput):
        # Data Collection Agent 호출
        stock_data_input = AgentInput(
            request_id=input_data.request_id,
            context={"data_type": "stock_price", "stock_code": "005930"}
        )
        stock_data_result = await data_collection_agent.execute(stock_data_input)

        # 분석 로직
        analysis = self._analyze(stock_data_result.data)
        return AgentOutput(...)
```

**장점**:
- ✅ **에이전트 구조와 완벽히 일치** (9개 에이전트 설계)
- ✅ **중복 API 호출 방지** (중앙화된 캐싱)
- ✅ **각 에이전트 독립성 유지**
- ✅ **PRD의 설계와 일치** (Data Collection Agent의 역할 명확)

**단점**:
- ⚠️ 에이전트 간 호출 오버헤드 (하지만 비동기로 최소화 가능)
- ⚠️ Data Collection Agent가 SPF (Single Point of Failure) 위험

**적용 시나리오**:
- **HAMA의 기본 아키텍처**
- 모든 에이전트가 데이터 필요 시 Data Collection Agent 호출

**평가**: ⭐⭐⭐⭐⭐ **아키텍처 일관성 측면에서 최고**

---

### 방법 4: RAG (Retrieval-Augmented Generation)

**개념**: DART 공시 문서 등 대용량 비정형 데이터를 Vector DB에 저장 후 검색

**구조**:
```
LLM
    ↓
Retriever (Embedding Search)
    ↓
Vector DB (Qdrant/Pinecone)
    ↑ (Indexing)
DART 공시 문서, 뉴스 등
```

**구현 예시**:
```python
# src/services/dart_rag_service.py
from langchain.vectorstores import Qdrant
from langchain.embeddings import OpenAIEmbeddings

class DARTRAGService:
    """DART 공시 RAG 서비스"""

    def __init__(self):
        self.embeddings = OpenAIEmbeddings()
        self.vectorstore = Qdrant(
            url=settings.QDRANT_URL,
            collection_name="dart_disclosures",
            embeddings=self.embeddings
        )

    async def index_disclosure(self, corp_code: str, doc_id: str):
        """공시 문서를 Vector DB에 인덱싱"""
        # DART API로 문서 가져오기
        doc = await dart_service.get_disclosure(doc_id)

        # 청크로 분할
        chunks = self._split_document(doc)

        # 임베딩 및 저장
        self.vectorstore.add_texts(chunks, metadatas=[...])

    async def search_disclosure(self, query: str, top_k: int = 5):
        """질의와 관련된 공시 내용 검색"""
        results = self.vectorstore.similarity_search(query, k=top_k)
        return results

# src/agents/research.py
class ResearchAgent(BaseAgent):
    def __init__(self):
        self.dart_rag = DARTRAGService()

    async def process(self, input_data: AgentInput):
        stock_name = "삼성전자"

        # RAG로 관련 공시 검색
        disclosures = await self.dart_rag.search_disclosure(
            f"{stock_name} 재무제표 분석"
        )

        # LLM에게 컨텍스트 제공
        analysis = await llm.generate(
            prompt=f"다음 공시 정보를 바탕으로 분석:\n{disclosures}"
        )

        return AgentOutput(...)
```

**장점**:
- ✅ **대용량 문서 처리 최적** (수백 페이지 사업보고서)
- ✅ **시맨틱 검색** (질의와 유사한 내용 자동 검색)
- ✅ **LLM 컨텍스트 윈도우 절약**

**단점**:
- ❌ **Vector DB 인프라 필요** (Qdrant, Pinecone)
- ❌ **초기 인덱싱 시간** (모든 공시 문서)
- ❌ **임베딩 비용** (OpenAI Embeddings)

**적용 시나리오**:
- **DART 공시 분석** (특히 사업보고서, 감사보고서)
- 뉴스 아카이브 검색
- Phase 2 후반 또는 Phase 3

**평가**: ⭐⭐⭐⭐☆ (DART 공시 분석에 특화)

---

### 방법 5: Direct API Calls in Agents ❌ 비추천

**개념**: 각 에이전트가 직접 외부 API 호출

**구조**:
```
Research Agent → FinanceDataReader API
Strategy Agent → FinanceDataReader API (중복!)
Risk Agent     → FinanceDataReader API (중복!)
```

**장점**:
- ✅ 구현 간단
- ✅ 직관적

**단점**:
- ❌ **중복 API 호출** (API 레이트 리밋 위험)
- ❌ **캐싱 어려움**
- ❌ **클린 아키텍처 위반** (에이전트가 외부 의존성 직접 참조)
- ❌ **테스트 어려움**
- ❌ **확장성 낮음**

**평가**: ⭐☆☆☆☆ (MVP 외에는 비추천)

---

## 🎯 HAMA 프로젝트 최종 권장 방식

### 하이브리드 아키텍처 (3-Layer)

```
┌─────────────────────────────────────────────────────────┐
│                    Agents Layer                         │
│  (Research, Strategy, Risk, Portfolio, etc.)            │
└──────────────────┬──────────────────────────────────────┘
                   ↓ 의존
┌─────────────────────────────────────────────────────────┐
│              Data Collection Agent                       │
│  + Service Layer (StockDataService, DARTService)        │
│  + Cache Manager (Redis)                                │
└──────────────────┬──────────────────────────────────────┘
                   ↓ 의존
┌─────────────────────────────────────────────────────────┐
│              External Data Sources                       │
│  - FinanceDataReader (주가)                             │
│  - DART API (공시, 재무제표)                            │
│  - 뉴스 크롤링 (네이버 금융)                            │
│  - [Phase 3] KIS API via MCP (실시간 시세)              │
│  - [Phase 2] RAG (DART 공시 문서)                       │
└─────────────────────────────────────────────────────────┘
```

### Phase별 구현 전략

#### Phase 1 (현재): Mock Data
```python
# 모든 에이전트가 _get_mock_response() 사용
# 실제 API 호출 없음
```

#### Phase 2: 핵심 데이터 소스 연동

**1단계: Service Layer 구축 (Week 11-12)**
```python
# src/services/stock_data_service.py
class StockDataService:
    async def get_stock_price(self, stock_code: str):
        """FinanceDataReader 사용"""
        import FinanceDataReader as fdr
        return fdr.DataReader(stock_code)

    async def get_stock_listing(self, market: str = "KOSPI"):
        """종목 리스트"""
        import FinanceDataReader as fdr
        return fdr.StockListing(market)

# src/services/dart_service.py
class DARTService:
    async def get_financial_statement(self, corp_code: str):
        """재무제표 조회"""
        # DART API 호출

    async def search_disclosure(self, corp_code: str, keyword: str):
        """공시 검색"""
        # DART API 호출
```

**2단계: Data Collection Agent 실제 구현 (Week 13)**
```python
# src/agents/data_collection.py
class DataCollectionAgent(BaseAgent):
    def __init__(self):
        self.stock_service = StockDataService()
        self.dart_service = DARTService(settings.DART_API_KEY)
        self.cache = Redis(settings.REDIS_URL)

    async def process(self, input_data: AgentInput):
        data_type = input_data.context["data_type"]

        if data_type == "stock_price":
            return await self._fetch_stock_price(input_data)
        elif data_type == "financial_statement":
            return await self._fetch_financial(input_data)
```

**3단계: 다른 에이전트들이 Data Collection Agent 사용 (Week 14-24)**
```python
# src/agents/research.py
class ResearchAgent(BaseAgent):
    async def process(self, input_data: AgentInput):
        # Data Collection Agent 호출
        stock_data = await self._get_stock_data(stock_code)
        financial_data = await self._get_financial_data(corp_code)

        # 실제 분석 로직
        analysis = self._analyze(stock_data, financial_data)
        return AgentOutput(...)

    async def _get_stock_data(self, stock_code: str):
        """Data Collection Agent 호출"""
        request = AgentInput(
            request_id=self.current_request_id,
            context={"data_type": "stock_price", "stock_code": stock_code}
        )
        result = await data_collection_agent.execute(request)
        return result.data
```

#### Phase 3: 고급 기능

**RAG for DART 공시 (선택)**
```python
# src/services/dart_rag_service.py
# Vector DB 인덱싱 및 검색
```

**MCP for KIS 실시간 시세**
```python
# 실시간 매매 실행 시
# MCP Server를 통해 실시간 호가/체결 데이터 접근
```

---

## 📊 방법론 종합 비교표

| 방법론 | 복잡도 | 성능 | 캐싱 | 확장성 | 아키텍처 | 적용 Phase |
|--------|--------|------|------|--------|----------|------------|
| **MCP** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | Phase 3 |
| **Service Layer** ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | **Phase 2** |
| **Data Collection Agent** ⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | **Phase 2** |
| **RAG** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Phase 2-3 |
| **Direct Calls** | ⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐ | ❌ 비추천 |

---

## 🚀 구현 로드맵

### Week 11-12: 인프라 구축
- [ ] FinanceDataReader 설치 및 테스트
- [ ] DART API 연동 테스트
- [ ] Redis 캐싱 설정
- [ ] Service Layer 뼈대 구축

### Week 13: Data Collection Agent 실제 구현
- [ ] FinanceDataReader 통합
- [ ] DART API 통합
- [ ] 캐싱 전략 구현
- [ ] 에러 핸들링 및 재시도 로직

### Week 14-16: Research Agent 실제 구현
- [ ] Data Collection Agent 사용
- [ ] 재무비율 계산 로직
- [ ] 기술적 지표 계산 (TA-Lib)
- [ ] LLM 기반 분석

### Week 17-24: 나머지 에이전트 구현
- [ ] Strategy Agent (Bull/Bear)
- [ ] Portfolio Agent (최적화)
- [ ] Risk Agent (VaR, Monte Carlo)

### Phase 3 (선택):
- [ ] RAG for DART 공시 분석
- [ ] MCP for KIS 실시간 시세

---

## 🔑 핵심 원칙

1. **클린 아키텍처 준수**
   - Agents → Services → External APIs (단방향 의존성)

2. **캐싱 최우선**
   - API 레이트 리밋 방지
   - 응답 속도 개선

3. **에이전트 독립성 유지**
   - 각 에이전트는 Data Collection Agent만 호출
   - 외부 API 직접 의존 금지

4. **단계적 전환**
   - Phase 1: Mock
   - Phase 2: Real (Service Layer + Data Collection Agent)
   - Phase 3: Advanced (RAG, MCP)

---

**최종 결론**: **Service Layer + Data Collection Agent + Cache**를 핵심으로, 필요 시 **RAG**(DART 공시)와 **MCP**(KIS 실시간)를 보조로 사용하는 **하이브리드 방식** 추천.

**작성자**: Claude Code
**최종 업데이트**: 2025-10-03