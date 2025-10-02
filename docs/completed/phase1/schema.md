PRD와 에이전트 아키텍처를 분석하여 포괄적인 데이터 스키마를 설계하겠습니다.

# 데이터 스키마 설계 문서

## 1. 개요

### 1.1 데이터베이스 구성

| 데이터베이스 | 용도 | 기술 스택 |
|------------|------|----------|
| **Primary DB** | 구조화된 데이터 저장 | PostgreSQL |
| **Vector DB** | 문서 임베딩, 유사도 검색 | Pinecone/Chroma |

### 1.2 설계 원칙

- **정규화**: 3NF 준수, 중복 최소화
- **확장성**: 샤딩 가능한 구조
- **감사 추적**: 모든 중요 변경 이력 저장
- **성능**: 적절한 인덱싱, 파티셔닝

---

## 2. 핵심 스키마

### 2.1 사용자 관리

```sql
-- 사용자 기본 정보
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    status VARCHAR(20) DEFAULT 'active', -- active, inactive, suspended
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP,
    
    -- 인덱스
    INDEX idx_email (email),
    INDEX idx_username (username),
    INDEX idx_status (status)
);

-- 사용자 프로필 (투자 성향)
CREATE TABLE user_profiles (
    profile_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    -- 투자 성향
    risk_tolerance VARCHAR(20) NOT NULL, -- aggressive, active, neutral, conservative, safe
    investment_goal VARCHAR(50) NOT NULL, -- short_term, mid_long_term, dividend, other
    investment_horizon VARCHAR(20) NOT NULL, -- under_1y, 1_3y, 3_5y, over_5y
    
    -- 자동화 레벨
    automation_level INT NOT NULL DEFAULT 2, -- 1: Pilot, 2: Copilot, 3: Advisor
    
    -- 투자 제약
    initial_capital DECIMAL(15, 2),
    monthly_contribution DECIMAL(15, 2),
    max_single_stock_ratio DECIMAL(5, 4) DEFAULT 0.20, -- 단일 종목 최대 비중
    max_sector_ratio DECIMAL(5, 4) DEFAULT 0.40, -- 섹터 최대 비중
    
    -- 메타데이터
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 제약조건
    UNIQUE(user_id),
    CHECK (automation_level BETWEEN 1 AND 3),
    CHECK (risk_tolerance IN ('aggressive', 'active', 'neutral', 'conservative', 'safe'))
);

-- 사용자 선호도
CREATE TABLE user_preferences (
    preference_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    -- 선호/회피 섹터
    preferred_sectors TEXT[], -- ['IT', 'Healthcare', 'Finance']
    avoided_sectors TEXT[],
    
    -- 선호/회피 종목
    preferred_stocks TEXT[], -- ['005930', '000660']
    avoided_stocks TEXT[],
    
    -- 알림 설정
    notification_settings JSONB DEFAULT '{"email": true, "push": false, "sms": false}',
    
    -- 모니터링 설정
    monitoring_frequency VARCHAR(20) DEFAULT 'daily', -- real_time, daily, weekly, monthly
    price_alert_threshold DECIMAL(5, 4) DEFAULT 0.10, -- ±10%
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(user_id)
);

-- 사용자 행동 이력 (Phase 2 - 개인화 학습용)
CREATE TABLE user_behavior_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    action_type VARCHAR(50) NOT NULL, -- view_stock, request_analysis, approve_trade, reject_trade
    action_details JSONB,
    
    -- 컨텍스트
    related_stock_code VARCHAR(20),
    related_agent VARCHAR(50),
    
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_user_action (user_id, action_type),
    INDEX idx_timestamp (timestamp)
);
```

### 2.2 종목 및 시장 데이터

```sql
-- 종목 기본 정보
CREATE TABLE stocks (
    stock_code VARCHAR(20) PRIMARY KEY, -- '005930' (삼성전자)
    stock_name VARCHAR(200) NOT NULL,
    stock_name_en VARCHAR(200),
    
    -- 분류
    market VARCHAR(20) NOT NULL, -- KOSPI, KOSDAQ, KONEX
    sector VARCHAR(100),
    industry VARCHAR(100),
    
    -- 기본 정보
    listing_date DATE,
    listing_shares BIGINT,
    par_value DECIMAL(10, 2),
    
    -- 상태
    status VARCHAR(20) DEFAULT 'active', -- active, delisted, suspended
    
    -- 메타데이터
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_market_sector (market, sector),
    INDEX idx_status (status)
);

-- 주가 데이터 (시계열)
CREATE TABLE stock_prices (
    price_id BIGSERIAL PRIMARY KEY,
    stock_code VARCHAR(20) NOT NULL REFERENCES stocks(stock_code),
    
    -- 가격 데이터
    date DATE NOT NULL,
    open_price DECIMAL(15, 2),
    high_price DECIMAL(15, 2),
    low_price DECIMAL(15, 2),
    close_price DECIMAL(15, 2) NOT NULL,
    
    -- 거래량
    volume BIGINT,
    trading_value DECIMAL(20, 2),
    
    -- 조정 가격
    adjusted_close DECIMAL(15, 2),
    
    -- 변동률
    change_amount DECIMAL(15, 2),
    change_rate DECIMAL(10, 6),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(stock_code, date),
    INDEX idx_stock_date (stock_code, date DESC),
    INDEX idx_date (date DESC)
);

-- 재무제표
CREATE TABLE financial_statements (
    statement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stock_code VARCHAR(20) NOT NULL REFERENCES stocks(stock_code),
    
    -- 기간
    fiscal_year INT NOT NULL,
    fiscal_quarter INT, -- 1, 2, 3, 4 (NULL이면 연간)
    report_type VARCHAR(20) NOT NULL, -- annual, quarterly
    
    -- 손익계산서
    revenue DECIMAL(20, 2),
    operating_profit DECIMAL(20, 2),
    net_profit DECIMAL(20, 2),
    
    -- 재무상태표
    total_assets DECIMAL(20, 2),
    total_liabilities DECIMAL(20, 2),
    total_equity DECIMAL(20, 2),
    
    -- 현금흐름표
    operating_cash_flow DECIMAL(20, 2),
    investing_cash_flow DECIMAL(20, 2),
    financing_cash_flow DECIMAL(20, 2),
    
    -- 주요 지표
    eps DECIMAL(15, 4), -- 주당순이익
    bps DECIMAL(15, 4), -- 주당순자산
    per DECIMAL(10, 4), -- 주가수익비율
    pbr DECIMAL(10, 4), -- 주가순자산비율
    roe DECIMAL(10, 6), -- 자기자본이익률
    roa DECIMAL(10, 6), -- 총자산이익률
    debt_ratio DECIMAL(10, 6), -- 부채비율
    
    -- 원본 데이터 (DART)
    raw_data JSONB,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(stock_code, fiscal_year, fiscal_quarter, report_type),
    INDEX idx_stock_year (stock_code, fiscal_year DESC)
);

-- 공시 정보
CREATE TABLE disclosures (
    disclosure_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stock_code VARCHAR(20) NOT NULL REFERENCES stocks(stock_code),
    
    -- 공시 정보
    report_number VARCHAR(50) UNIQUE NOT NULL, -- DART 고유번호
    report_name VARCHAR(500) NOT NULL,
    report_type VARCHAR(100),
    
    -- 내용
    summary TEXT,
    content TEXT,
    
    -- 메타데이터
    submit_date DATE NOT NULL,
    receipt_number VARCHAR(50),
    
    -- 중요도 (AI 평가)
    importance_score DECIMAL(3, 2), -- 0.00 ~ 1.00
    
    -- 임베딩 ID (Vector DB)
    embedding_id VARCHAR(100),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_stock_date (stock_code, submit_date DESC),
    INDEX idx_submit_date (submit_date DESC),
    INDEX idx_importance (importance_score DESC)
);

-- 뉴스
CREATE TABLE news (
    news_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 기본 정보
    title VARCHAR(500) NOT NULL,
    content TEXT,
    summary TEXT,
    url VARCHAR(1000),
    source VARCHAR(100), -- 네이버, 한경, 매경 등
    
    -- 관련 종목
    related_stocks TEXT[], -- ['005930', '000660']
    
    -- 감정 분석 (Phase 3)
    sentiment_score DECIMAL(3, 2), -- -1.00 (부정) ~ 1.00 (긍정)
    
    -- 메타데이터
    published_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 임베딩 ID (Vector DB)
    embedding_id VARCHAR(100),
    
    INDEX idx_published_at (published_at DESC),
    INDEX idx_related_stocks (related_stocks)
);
```

### 2.3 포트폴리오 관리

```sql
-- 포트폴리오
CREATE TABLE portfolios (
    portfolio_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    -- 포트폴리오 정보
    portfolio_name VARCHAR(200) NOT NULL DEFAULT 'My Portfolio',
    strategy_type VARCHAR(50), -- growth, dividend, balanced, aggressive
    
    -- 자산 정보
    total_value DECIMAL(15, 2) NOT NULL DEFAULT 0,
    cash_balance DECIMAL(15, 2) NOT NULL DEFAULT 0,
    invested_amount DECIMAL(15, 2) NOT NULL DEFAULT 0,
    
    -- 성과 지표
    total_return DECIMAL(10, 6),
    annual_return DECIMAL(10, 6),
    sharpe_ratio DECIMAL(10, 6),
    max_drawdown DECIMAL(10, 6),
    
    -- 리스크 지표
    volatility DECIMAL(10, 6),
    var_95 DECIMAL(10, 6), -- Value at Risk (95%)
    
    -- 메타데이터
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_rebalanced_at TIMESTAMP,
    
    INDEX idx_user (user_id),
    INDEX idx_updated (updated_at DESC)
);

-- 포트폴리오 포지션 (보유 종목)
CREATE TABLE positions (
    position_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    stock_code VARCHAR(20) NOT NULL REFERENCES stocks(stock_code),
    
    -- 보유 정보
    quantity INT NOT NULL,
    average_price DECIMAL(15, 2) NOT NULL,
    current_price DECIMAL(15, 2),
    
    -- 계산 필드
    market_value DECIMAL(15, 2), -- quantity * current_price
    unrealized_pnl DECIMAL(15, 2), -- (current_price - average_price) * quantity
    unrealized_pnl_rate DECIMAL(10, 6),
    
    -- 비중
    weight DECIMAL(5, 4), -- 포트폴리오 내 비중
    
    -- 메타데이터
    first_purchased_at TIMESTAMP,
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(portfolio_id, stock_code),
    INDEX idx_portfolio (portfolio_id),
    INDEX idx_stock (stock_code)
);

-- 거래 내역
CREATE TABLE transactions (
    transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id),
    stock_code VARCHAR(20) NOT NULL REFERENCES stocks(stock_code),
    
    -- 거래 정보
    transaction_type VARCHAR(10) NOT NULL, -- BUY, SELL
    quantity INT NOT NULL,
    price DECIMAL(15, 2) NOT NULL,
    total_amount DECIMAL(15, 2) NOT NULL,
    fee DECIMAL(15, 2) DEFAULT 0,
    tax DECIMAL(15, 2) DEFAULT 0,
    
    -- 주문 정보 (Phase 2 - 실제 매매)
    order_id UUID, -- 주문 ID (있으면 실제 거래)
    order_status VARCHAR(20), -- pending, executed, cancelled, failed
    
    -- AI 추천 추적
    signal_id UUID, -- 어떤 AI 시그널에 의한 거래인지
    
    -- 메타데이터
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    
    INDEX idx_portfolio_date (portfolio_id, executed_at DESC),
    INDEX idx_stock_date (stock_code, executed_at DESC),
    INDEX idx_type (transaction_type)
);

-- 포트폴리오 히스토리 (일별 스냅샷)
CREATE TABLE portfolio_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id),
    
    -- 스냅샷 날짜
    snapshot_date DATE NOT NULL,
    
    -- 자산 정보
    total_value DECIMAL(15, 2) NOT NULL,
    cash_balance DECIMAL(15, 2) NOT NULL,
    invested_amount DECIMAL(15, 2) NOT NULL,
    
    -- 수익률
    daily_return DECIMAL(10, 6),
    cumulative_return DECIMAL(10, 6),
    
    -- 포지션 상세 (JSON)
    positions_detail JSONB,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(portfolio_id, snapshot_date),
    INDEX idx_portfolio_date (portfolio_id, snapshot_date DESC)
);
```

### 2.4 AI 에이전트 및 분석

```sql
-- AI 분석 리포트
CREATE TABLE research_reports (
    report_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stock_code VARCHAR(20) NOT NULL REFERENCES stocks(stock_code),
    
    -- 리포트 유형
    report_type VARCHAR(50) NOT NULL, -- fundamental, technical, industry, competitor
    
    -- 분석 결과
    rating INT, -- 1~5 별점
    target_price DECIMAL(15, 2),
    recommendation VARCHAR(20), -- STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL
    
    -- 상세 분석
    summary TEXT,
    bull_case TEXT,
    bear_case TEXT,
    key_insights JSONB,
    
    -- 지표
    metrics JSONB, -- {
    --   "profitability": {"roe": 0.15, "roa": 0.08},
    --   "growth": {"revenue_growth": 0.10},
    --   "valuation": {"per": 15.5, "pbr": 1.2}
    -- }
    
    -- AI 메타데이터
    agent_id VARCHAR(50), -- research_agent
    model_version VARCHAR(50),
    confidence_score DECIMAL(3, 2),
    
    -- 메타데이터
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valid_until TIMESTAMP,
    
    INDEX idx_stock_date (stock_code, generated_at DESC),
    INDEX idx_type (report_type),
    INDEX idx_rating (rating DESC)
);

-- 매매 시그널
CREATE TABLE trading_signals (
    signal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stock_code VARCHAR(20) NOT NULL REFERENCES stocks(stock_code),
    user_id UUID REFERENCES users(user_id),
    
    -- 시그널 정보
    action VARCHAR(10) NOT NULL, -- BUY, SELL, HOLD
    confidence DECIMAL(3, 2) NOT NULL, -- 0.00 ~ 1.00
    
    -- 가격 정보
    current_price DECIMAL(15, 2),
    target_price DECIMAL(15, 2),
    stop_loss DECIMAL(15, 2),
    
    -- 근거
    reasoning TEXT NOT NULL,
    bull_case TEXT,
    bear_case TEXT,
    
    -- Bull/Bear 분석
    bull_confidence DECIMAL(3, 2),
    bear_confidence DECIMAL(3, 2),
    consensus VARCHAR(50), -- bullish, bearish, neutral, uncertain
    
    -- AI 메타데이터
    agent_id VARCHAR(50), -- strategy_agent
    model_version VARCHAR(50),
    
    -- 상태
    status VARCHAR(20) DEFAULT 'active', -- active, executed, expired, rejected
    
    -- 메타데이터
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    
    INDEX idx_stock_date (stock_code, generated_at DESC),
    INDEX idx_user_status (user_id, status),
    INDEX idx_action (action),
    INDEX idx_confidence (confidence DESC)
);

-- 리스크 평가
CREATE TABLE risk_assessments (
    assessment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID REFERENCES portfolios(portfolio_id),
    user_id UUID REFERENCES users(user_id),
    
    -- 평가 대상
    assessment_type VARCHAR(50), -- portfolio, position, trade
    related_entity_id UUID, -- portfolio_id, position_id, or signal_id
    
    -- 리스크 지표
    risk_level VARCHAR(20) NOT NULL, -- low, medium, high, critical
    risk_score DECIMAL(5, 2), -- 0 ~ 100
    
    -- 구체적 리스크
    concentration_risk DECIMAL(3, 2), -- 집중도 리스크
    sector_risk JSONB, -- 섹터별 리스크
    volatility_risk DECIMAL(10, 6),
    
    -- 시뮬레이션
    var_95 DECIMAL(10, 6),
    expected_loss DECIMAL(15, 2),
    max_drawdown_scenario DECIMAL(10, 6),
    
    -- 경고 및 권고
    warnings TEXT[],
    recommendations TEXT[],
    
    -- AI 메타데이터
    agent_id VARCHAR(50), -- risk_agent
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_portfolio (portfolio_id),
    INDEX idx_user (user_id),
    INDEX idx_risk_level (risk_level),
    INDEX idx_created (created_at DESC)
);

-- 에이전트 실행 로그
CREATE TABLE agent_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 에이전트 정보
    agent_id VARCHAR(50) NOT NULL, -- master_agent, research_agent, etc.
    agent_action VARCHAR(100) NOT NULL,
    
    -- 요청 정보
    request_id UUID,
    user_id UUID REFERENCES users(user_id),
    
    -- 입출력
    input_data JSONB,
    output_data JSONB,
    
    -- 실행 정보
    status VARCHAR(20), -- success, failure, timeout
    error_message TEXT,
    execution_time_ms INT,
    
    -- 메타데이터
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_agent_time (agent_id, timestamp DESC),
    INDEX idx_user_time (user_id, timestamp DESC),
    INDEX idx_request (request_id)
);

-- 에이전트 간 메시지
CREATE TABLE agent_messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 송수신 정보
    from_agent VARCHAR(50) NOT NULL,
    to_agent VARCHAR(50) NOT NULL,
    message_type VARCHAR(100) NOT NULL,
    
    -- 내용
    payload JSONB NOT NULL,
    
    -- 추적
    request_id UUID NOT NULL,
    parent_message_id UUID REFERENCES agent_messages(message_id),
    
    -- 상태
    status VARCHAR(20) DEFAULT 'pending', -- pending, processing, completed, failed
    
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    
    INDEX idx_request (request_id),
    INDEX idx_from_to (from_agent, to_agent),
    INDEX idx_status (status)
);
```

### 2.5 HITL (Human-in-the-Loop)

```sql
-- 승인 요청
CREATE TABLE approval_requests (
    request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id),
    
    -- 요청 정보
    request_type VARCHAR(50) NOT NULL, -- trade_execution, portfolio_rebalance, strategy_change
    request_title VARCHAR(200) NOT NULL,
    request_description TEXT,
    
    -- 관련 엔티티
    related_signal_id UUID REFERENCES trading_signals(signal_id),
    related_portfolio_id UUID REFERENCES portfolios(portfolio_id),
    
    -- 제안 내용
    proposed_actions JSONB NOT NULL, -- [
    --   {"action": "BUY", "stock": "005930", "quantity": 10},
    --   {"action": "SELL", "stock": "000660", "quantity": 5}
    -- ]
    
    -- 영향 분석
    impact_analysis JSONB, -- {
    --   "risk_change": {"before": 0.18, "after": 0.16},
    --   "expected_return": 0.05,
    --   "portfolio_composition": {...}
    -- }
    
    -- 리스크 경고
    risk_warnings TEXT[],
    
    -- 대안 제시
    alternatives JSONB, -- [
    --   {"option": "conservative", "actions": [...]},
    --   {"option": "aggressive", "actions": [...]}
    -- ]
    
    -- 상태
    status VARCHAR(20) DEFAULT 'pending', -- pending, approved, rejected, modified, expired
    
    -- AI 메타데이터
    triggering_agent VARCHAR(50),
    automation_level INT, -- 사용자의 당시 자동화 레벨
    urgency VARCHAR(20), -- low, medium, high
    
    -- 타임스탬프
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    responded_at TIMESTAMP,
    expires_at TIMESTAMP,
    
    INDEX idx_user_status (user_id, status),
    INDEX idx_type (request_type),
    INDEX idx_created (created_at DESC),
    INDEX idx_urgency (urgency)
);

-- 사용자 결정 이력
CREATE TABLE user_decisions (
    decision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES approval_requests(request_id),
    user_id UUID NOT NULL REFERENCES users(user_id),
    
    -- 결정 내용
    decision VARCHAR(20) NOT NULL, -- approved, rejected, modified
    selected_option VARCHAR(50), -- original, conservative, aggressive, custom
    
    -- 수정 사항 (있는 경우)
    modifications JSONB,
    
    -- 사용자 피드백
    user_notes TEXT,
    confidence_level INT, -- 1~5 (사용자가 이 결정에 얼마나 확신하는지)
    
    -- 결정 컨텍스트
    decision_reason VARCHAR(500),
    
    -- 타임스탬프
    decided_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_request (request_id),
    INDEX idx_user_decision (user_id, decision),
    INDEX idx_decided (decided_at DESC)
);
```

### 2.6 모니터링 및 알림

```sql
-- 알림
CREATE TABLE alerts (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id),
    
    -- 알림 정보
    alert_type VARCHAR(50) NOT NULL, -- price_change, disclosure, news, risk_warning, hitl_request
    severity VARCHAR(20) NOT NULL, -- info, warning, critical
    
    -- 내용
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    action_required BOOLEAN DEFAULT FALSE,
    
    -- 관련 엔티티
    related_stock VARCHAR(20),
    related_portfolio_id UUID,
    related_request_id UUID,
    
    -- 상태
    status VARCHAR(20) DEFAULT 'unread', -- unread, read, dismissed, acted
    
    -- 타임스탬프
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP,
    
    INDEX idx_user_status (user_id, status),
    INDEX idx_severity (severity),
    INDEX idx_created (created_at DESC)
);

-- 모니터링 트리거 설정
CREATE TABLE monitoring_triggers (
    trigger_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id),
    
    -- 트리거 정보
    trigger_name VARCHAR(100) NOT NULL,
    trigger_type VARCHAR(50) NOT NULL, -- price_threshold, volume_surge, disclosure, news
    
    -- 조건
    stock_code VARCHAR(20),
    conditions JSONB NOT NULL, -- {
    --   "price_change_pct": 10,
    --   "volume_multiplier": 3,
    --   "keywords": ["실적", "배당"]
    -- }
    
    -- 액션
    action_type VARCHAR(50) NOT NULL, -- send_alert, auto_analyze, hitl_request
    action_config JSONB,
    
    -- 상태
    is_active BOOLEAN DEFAULT TRUE,
    
    -- 마지막 실행
    last_triggered_at TIMESTAMP,
    trigger_count INT DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_user_active (user_id, is_active),
    INDEX idx_type (trigger_type)
);

-- 모니터링 이벤트 (트리거 발동 이력)
CREATE TABLE monitoring_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trigger_id UUID REFERENCES monitoring_triggers(trigger_id),
    user_id UUID NOT NULL REFERENCES users(user_id),
    
    -- 이벤트 정보
    event_type VARCHAR(50) NOT NULL,
    stock_code VARCHAR(20),
    
    -- 상세
    event_data JSONB,
    detected_value DECIMAL(15, 2),
    threshold_value DECIMAL(15, 2),
    
    -- 처리 결과
    actions_taken TEXT[],
    
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_trigger (trigger_id),
    INDEX idx_user_date (user_id, detected_at DESC)
);
```

### 2.7 백테스팅 (Phase 2)

```sql
-- 백테스트
CREATE TABLE backtests (
    backtest_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id),
    
    -- 백테스트 설정
    strategy_name VARCHAR(100) NOT NULL,
    strategy_config JSONB NOT NULL,
    
    -- 기간
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_capital DECIMAL(15, 2) NOT NULL,
    
    -- 결과 지표
    total_return DECIMAL(10, 6),
    annual_return DECIMAL(10, 6),
    sharpe_ratio DECIMAL(10, 6),
    max_drawdown DECIMAL(10, 6),
    win_rate DECIMAL(5, 4),
    profit_factor DECIMAL(10, 6),
    
    -- 거래 통계
    total_trades INT,
    winning_trades INT,
    losing_trades INT,
    
    -- 상태
    status VARCHAR(20) DEFAULT 'pending', -- pending, running, completed, failed
    
    -- 메타데이터
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    
    INDEX idx_user (user_id),
    INDEX idx_status (status),
    INDEX idx_created (created_at DESC)
);

-- 백테스트 거래 내역
CREATE TABLE backtest_trades (
    trade_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    backtest_id UUID NOT NULL REFERENCES backtests(backtest_id) ON DELETE CASCADE,
    
    -- 거래 정보
    stock_code VARCHAR(20) NOT NULL,
    trade_type VARCHAR(10) NOT NULL, -- BUY, SELL
    quantity INT NOT NULL,
    price DECIMAL(15, 2) NOT NULL,
    
    -- 결과
    pnl DECIMAL(15, 2),
    pnl_rate DECIMAL(10, 6),
    
    -- 타임스탬프
    executed_at TIMESTAMP NOT NULL,
    
    INDEX idx_backtest (backtest_id),
    INDEX idx_executed (executed_at)
);
```

### 2.8 컴플라이언스 및 감사 (Phase 2)

```sql
-- 감사 로그
CREATE TABLE audit_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 주체
    user_id UUID REFERENCES users(user_id),
    agent_id VARCHAR(50),
    
    -- 액션
    action_type VARCHAR(100) NOT NULL, -- user_login, trade_executed, portfolio_modified
    entity_type VARCHAR(50), -- user, portfolio, transaction
    entity_id UUID,
    
    -- 상세
    before_state JSONB,
    after_state JSONB,
    changes JSONB,
    
    -- IP 및 환경
    ip_address INET,
    user_agent TEXT,
    
    -- 타임스탬프
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_user_time (user_id, timestamp DESC),
    INDEX idx_action (action_type),
    INDEX idx_entity (entity_type, entity_id)
);

-- 컴플라이언스 체크
CREATE TABLE compliance_checks (
    check_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 체크 대상
    user_id UUID REFERENCES users(user_id),
    transaction_id UUID REFERENCES transactions(transaction_id),
    
    -- 체크 유형
    check_type VARCHAR(50) NOT NULL, -- insider_trading, market_manipulation, limit_breach
    
    -- 결과
    status VARCHAR(20) NOT NULL, -- passed, failed, warning
    violation_details TEXT,
    
    -- 규제 근거
    regulation_reference VARCHAR(200),
    
    -- AI 메타데이터
    agent_id VARCHAR(50),
    
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_user (user_id),
    INDEX idx_status (status),
    INDEX idx_type (check_type)
);
```

---

## 3. 인덱싱 전략

### 3.1 복합 인덱스

```sql
-- 자주 함께 조회되는 컬럼
CREATE INDEX idx_stock_prices_composite ON stock_prices(stock_code, date DESC, close_price);
CREATE INDEX idx_positions_composite ON positions(portfolio_id, stock_code, last_updated_at DESC);
CREATE INDEX idx_transactions_composite ON transactions(portfolio_id, executed_at DESC, transaction_type);
CREATE INDEX idx_alerts_composite ON alerts(user_id, status, created_at DESC);
```

### 3.2 부분 인덱스

```sql
-- 특정 조건의 데이터만 인덱싱
CREATE INDEX idx_active_positions ON positions(portfolio_id, stock_code) 
    WHERE quantity > 0;

CREATE INDEX idx_unread_alerts ON alerts(user_id, created_at DESC) 
    WHERE status = 'unread';

CREATE INDEX idx_pending_approvals ON approval_requests(user_id, created_at DESC) 
    WHERE status = 'pending';
```

---

## 4. 파티셔닝 전략

### 4.1 시계열 데이터 파티셔닝

```sql
-- stock_prices를 월별로 파티셔닝
CREATE TABLE stock_prices (
    -- ... 기존 컬럼들 ...
) PARTITION BY RANGE (date);

CREATE TABLE stock_prices_2024_01 PARTITION OF stock_prices
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE stock_prices_2024_02 PARTITION OF stock_prices
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
-- ... 계속
```

---

## 5. 캐싱 전략 (Redis)

### 5.1 실시간 데이터

```python
# Redis 키 구조
redis_keys = {
    "stock:price:{stock_code}": "실시간 주가",
    "portfolio:value:{portfolio_id}": "포트폴리오 현재 가치",
    "user:session:{user_id}": "사용자 세션",
    "agent:status:{agent_id}": "에이전트 상태",
    "hitl:pending:{user_id}": "대기 중인 승인 요청 수"
}

# TTL 설정
ttl_config = {
    "stock:price": 60,  # 1분
    "portfolio:value": 300,  # 5분
    "user:session": 3600,  # 1시간
    "agent:status": 10  # 10초
}
```

---

## 6. Vector DB 스키마 (Pinecone/Chroma)

### 6.1 문서 임베딩

```python
# Pinecone 인덱스 구조
index_schema = {
    "dart_disclosures": {
        "dimension": 1536,  # OpenAI ada-002
        "metric": "cosine",
        "metadata": {
            "stock_code": "string",
            "report_type": "string",
            "submit_date": "date",
            "importance_score": "float"
        }
    },
    "news_articles": {
        "dimension": 1536,
        "metric": "cosine",
        "metadata": {
            "related_stocks": "list[string]",
            "published_at": "date",
            "sentiment_score": "float"
        }
    },
    "research_reports": {
        "dimension": 1536,
        "metric": "cosine",
        "metadata": {
            "stock_code": "string",
            "report_type": "string",
            "rating": "int"
        }
    }
}
```

---

## 7. 데이터 보존 정책

| 데이터 유형 | 보존 기간 | 아카이빙 |
|-----------|---------|---------|
| 사용자 정보 | 영구 | - |
| 주가 데이터 | 10년 | Cold Storage |
| 거래 내역 | 영구 | - |
| AI 로그 | 1년 | S3 |
| 알림 | 6개월 | 삭제 |
| 백테스트 | 1년 | 요청 시 |

---

이제 이 스키마를 바탕으로 ERD 다이어그램을 생성하시겠습니까?