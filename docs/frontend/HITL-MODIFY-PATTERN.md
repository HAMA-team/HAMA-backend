# HITL Modify 패턴 - Frontend 구현 가이드

> **작성일**: 2025-11-15
> **대상**: Frontend 개발자
> **목적**: HITL (Human-in-the-Loop) Modify 패턴 UI 구현을 위한 API 스펙 및 사용 가이드

---

## 📋 목차

1. [개요](#개요)
2. [API 스펙](#api-스펙)
3. [시나리오별 구현 가이드](#시나리오별-구현-가이드)
4. [UI 컴포넌트 설계](#ui-컴포넌트-설계)
5. [예시 코드](#예시-코드)

---

## 개요

### HITL Modify 패턴이란?

사용자가 AI의 제안에 대해 **Approve/Reject뿐만 아니라 구체적인 수정사항을 제시**할 수 있는 패턴입니다.

**기존 HITL (2-Way)**:
```
AI 제안 → [Approve | Reject]
```

**신규 HITL Modify (3-Way)**:
```
AI 제안 → [Approve | Reject | Modify]
                              ↓
                    [구조화된 수정 + 자유 텍스트]
```

### 지원 범위

| 기능 | Modify 지원 | 수정 가능 항목 |
|------|-------------|---------------|
| **Research Plan** | ✅ | Depth, Scope, Perspectives, User Input (자유 텍스트) |
| **Trading** | ✅ | Quantity, Price, Action |
| **Portfolio Rebalancing** | ✅ | User Guidance (자유 텍스트) |

---

## API 스펙

### 1. `/chat` 엔드포인트 (초기 요청)

**Request**:
```json
POST /chat
{
  "message": "삼성전자 분석해줘",
  "conversation_id": "uuid-string",
  "hitl_config": {
    "research_plan": true,
    "trade_execution": true,
    "rebalancing": true
  }
}
```

**Response (Interrupt 발생 시)**:
```json
{
  "message": "🔔 사용자 승인이 필요합니다.",
  "conversation_id": "uuid-string",
  "requires_approval": true,
  "approval_request": {
    "type": "research_plan_approval",  // 또는 "trade_approval", "rebalance_approval"
    "request_id": "approval-uuid",
    "stock_code": "005930",
    "plan": {
      "depth": "detailed",
      "scope": "balanced",
      "perspectives": ["technical", "fundamental"]
    },
    "options": {
      "depths": ["brief", "detailed", "comprehensive"],
      "scopes": ["key_points", "balanced", "wide_coverage"],
      "perspectives": ["macro", "fundamental", "technical", "flow", "strategy", "bull_case", "bear_case"]
    },
    "modifiable_fields": ["depth", "scope", "perspectives"],
    "supports_user_input": true,
    "message": "다음과 같이 분석할 예정입니다. 진행하시겠습니까?"
  }
}
```

### 2. `/chat/approve` 엔드포인트 (승인/수정/거부)

**Request (Approve)**:
```json
POST /chat/approve
{
  "thread_id": "conversation-uuid",
  "decision": "approved",
  "request_id": "approval-uuid"
}
```

**Request (Reject)**:
```json
POST /chat/approve
{
  "thread_id": "conversation-uuid",
  "decision": "rejected",
  "request_id": "approval-uuid",
  "user_notes": "지금은 분석하지 않겠습니다"
}
```

**Request (Modify)**:
```json
POST /chat/approve
{
  "thread_id": "conversation-uuid",
  "decision": "modified",
  "request_id": "approval-uuid",
  "modifications": {
    // 구조화된 수정사항 (케이스별 다름)
  },
  "user_input": "자유 텍스트 입력 (선택사항)"
}
```

**Response**:
```json
{
  "status": "approved",  // 또는 "rejected", "modified"
  "message": "승인 완료 - 분석을 시작합니다.",
  "conversation_id": "uuid-string",
  "result": {
    // 최종 결과
  }
}
```

---

## 시나리오별 구현 가이드

### Scenario 1: Research Plan Modify

#### 1-1. AI 제안 수신

```json
{
  "type": "research_plan_approval",
  "request_id": "req-123",
  "stock_code": "005930",
  "query": "삼성전자 분석해줘",
  "plan": {
    "depth": "detailed",
    "depth_name": "표준 분석",
    "scope": "balanced",
    "perspectives": ["technical", "fundamental"],
    "estimated_time": "30-45초"
  },
  "options": {
    "depths": ["brief", "detailed", "comprehensive"],
    "scopes": ["key_points", "balanced", "wide_coverage"],
    "perspectives": ["macro", "fundamental", "technical", "flow", "strategy", "bull_case", "bear_case"]
  },
  "modifiable_fields": ["depth", "scope", "perspectives"],
  "supports_user_input": true
}
```

#### 1-2. UI 구성

```
┌─────────────────────────────────────────┐
│ AI 제안                                  │
│ ────────────────────────────────────── │
│ 삼성전자를 다음과 같이 분석합니다:       │
│                                          │
│ • 깊이: 표준 분석 (30-45초)             │
│ • 범위: 균형잡힌 (최대 5개 관점)         │
│ • 관점: 기술적 분석, 재무 분석           │
│                                          │
│ [수정하기]  [승인]  [거부]               │
└─────────────────────────────────────────┘

[수정하기] 클릭 시:
┌─────────────────────────────────────────┐
│ 분석 설정 수정                           │
│ ────────────────────────────────────── │
│ 깊이: ○ 빠른 분석  ● 표준 분석  ○ 종합   │
│                                          │
│ 범위: ○ 핵심만  ● 균형  ○ 광범위        │
│                                          │
│ 관점: [x] 거시경제  [x] 재무제표         │
│       [x] 기술적    [ ] 거래동향         │
│       [ ] 투자전략  [ ] 강세  [ ] 약세   │
│                                          │
│ 추가 요청:                               │
│ ┌─────────────────────────────────────┐ │
│ │ 반도체 사업부에 집중해주세요         │ │
│ └─────────────────────────────────────┘ │
│                                          │
│ [취소]  [수정 후 승인]                   │
└─────────────────────────────────────────┘
```

#### 1-3. Modify 요청

```json
POST /chat/approve
{
  "thread_id": "conv-123",
  "decision": "modified",
  "request_id": "req-123",
  "modifications": {
    "depth": "comprehensive",
    "scope": "wide_coverage",
    "perspectives": ["macro", "fundamental", "technical", "bull_case", "bear_case"]
  },
  "user_input": "반도체 사업부에 집중해주세요"
}
```

---

### Scenario 2: Trading Modify

#### 2-1. AI 제안 수신

```json
{
  "type": "trade_approval",
  "request_id": "trade-456",
  "action": "buy",
  "stock_code": "005930",
  "stock_name": "삼성전자",
  "quantity": 100,
  "price": 75000,
  "total_amount": 7500000,
  "current_weight": 0.25,
  "expected_weight": 0.35,
  "risk_warning": "⚠️ 단일 종목 35% 집중",
  "modifiable_fields": ["quantity", "price", "action"],
  "supports_user_input": false
}
```

#### 2-2. UI 구성

```
┌─────────────────────────────────────────┐
│ 매매 주문 승인                           │
│ ────────────────────────────────────── │
│ 삼성전자 100주를 75,000원에 매수          │
│                                          │
│ 총 금액: 7,500,000원                     │
│ 현재 비중: 25% → 예상 비중: 35%          │
│                                          │
│ ⚠️ 단일 종목 35% 집중                   │
│                                          │
│ [수정하기]  [승인]  [거부]               │
└─────────────────────────────────────────┘

[수정하기] 클릭 시:
┌─────────────────────────────────────────┐
│ 주문 수정                                │
│ ────────────────────────────────────── │
│ 방향: ● 매수  ○ 매도                    │
│                                          │
│ 수량: [   50    ] 주                    │
│                                          │
│ 가격: [  68,000  ] 원                   │
│                                          │
│ 예상 금액: 3,400,000원                   │
│                                          │
│ [취소]  [수정 후 승인]                   │
└─────────────────────────────────────────┘
```

#### 2-3. Modify 요청

```json
POST /chat/approve
{
  "thread_id": "conv-123",
  "decision": "modified",
  "request_id": "trade-456",
  "modifications": {
    "quantity": 50,
    "price": 68000,
    "action": "buy"
  }
}
```

---

### Scenario 3: Portfolio Rebalancing Modify

#### 3-1. AI 제안 수신

```json
{
  "type": "rebalance_approval",
  "request_id": "rebal-789",
  "proposed_allocation": [
    {"stock_code": "005930", "stock_name": "삼성전자", "weight": 0.30},
    {"stock_code": "000660", "stock_name": "SK하이닉스", "weight": 0.25},
    {"stock_code": "035420", "stock_name": "NAVER", "weight": 0.20},
    {"stock_code": "CASH", "stock_name": "현금", "weight": 0.25}
  ],
  "expected_return": 0.12,
  "expected_volatility": 0.18,
  "sharpe_ratio": 0.67,
  "market_condition": "중립장",
  "modifiable_fields": [],
  "supports_user_input": true,
  "message": "다음과 같이 리밸런싱할 예정입니다."
}
```

#### 3-2. UI 구성

```
┌─────────────────────────────────────────┐
│ 리밸런싱 계획                            │
│ ────────────────────────────────────── │
│ 삼성전자     30%                         │
│ SK하이닉스   25%                         │
│ NAVER       20%                         │
│ 현금        25%                         │
│                                          │
│ 예상 수익률: 12% | 변동성: 18%           │
│ 샤프지수: 0.67                           │
│                                          │
│ [의견 제시]  [승인]  [거부]              │
└─────────────────────────────────────────┘

[의견 제시] 클릭 시:
┌─────────────────────────────────────────┐
│ 리밸런싱 방향성 제시                     │
│ ────────────────────────────────────── │
│ AI 계획에 대한 조언을 입력하세요:         │
│ ┌─────────────────────────────────────┐ │
│ │ IT 섹터를 더 늘려주세요.              │ │
│ │ 엔비디아 실적이 좋아서 반도체가       │ │
│ │ 유망해보입니다.                       │ │
│ └─────────────────────────────────────┘ │
│                                          │
│ [취소]  [조언 반영하여 재조정]           │
└─────────────────────────────────────────┘
```

#### 3-3. Modify 요청

```json
POST /chat/approve
{
  "thread_id": "conv-123",
  "decision": "modified",
  "request_id": "rebal-789",
  "user_input": "IT 섹터를 더 늘려주세요. 엔비디아 실적이 좋아서 반도체가 유망해보입니다."
}
```

---

## UI 컴포넌트 설계

### 1. HITL 패널 (공통)

```tsx
interface HITLPanelProps {
  approvalRequest: ApprovalRequest;
  onApprove: () => void;
  onReject: (notes?: string) => void;
  onModify: (modifications: any, userInput?: string) => void;
}

const HITLPanel: React.FC<HITLPanelProps> = ({
  approvalRequest,
  onApprove,
  onReject,
  onModify,
}) => {
  const [isModifying, setIsModifying] = useState(false);

  if (isModifying) {
    return (
      <ModifyPanel
        approvalRequest={approvalRequest}
        onCancel={() => setIsModifying(false)}
        onSubmit={onModify}
      />
    );
  }

  return (
    <ApprovalPanel
      approvalRequest={approvalRequest}
      onApprove={onApprove}
      onReject={onReject}
      onModify={() => setIsModifying(true)}
    />
  );
};
```

### 2. Research Plan Modify Panel

```tsx
interface ResearchModifyPanelProps {
  plan: {
    depth: string;
    scope: string;
    perspectives: string[];
  };
  options: {
    depths: string[];
    scopes: string[];
    perspectives: string[];
  };
  onSubmit: (modifications: any, userInput?: string) => void;
}

const ResearchModifyPanel: React.FC<ResearchModifyPanelProps> = ({
  plan,
  options,
  onSubmit,
}) => {
  const [depth, setDepth] = useState(plan.depth);
  const [scope, setScope] = useState(plan.scope);
  const [perspectives, setPerspectives] = useState(plan.perspectives);
  const [userInput, setUserInput] = useState("");

  const handleSubmit = () => {
    onSubmit(
      {
        depth,
        scope,
        perspectives,
      },
      userInput || undefined
    );
  };

  return (
    <div>
      {/* Depth 선택 */}
      <RadioGroup value={depth} onChange={setDepth}>
        {options.depths.map((d) => (
          <Radio key={d} value={d}>{d}</Radio>
        ))}
      </RadioGroup>

      {/* Scope 선택 */}
      <RadioGroup value={scope} onChange={setScope}>
        {options.scopes.map((s) => (
          <Radio key={s} value={s}>{s}</Radio>
        ))}
      </RadioGroup>

      {/* Perspectives 선택 */}
      <CheckboxGroup value={perspectives} onChange={setPerspectives}>
        {options.perspectives.map((p) => (
          <Checkbox key={p} value={p}>{p}</Checkbox>
        ))}
      </CheckboxGroup>

      {/* 추가 요청 */}
      <TextArea
        placeholder="추가 요청사항을 입력하세요 (예: 반도체 사업부에 집중)"
        value={userInput}
        onChange={(e) => setUserInput(e.target.value)}
      />

      <Button onClick={handleSubmit}>수정 후 승인</Button>
    </div>
  );
};
```

### 3. Trading Modify Panel

```tsx
interface TradingModifyPanelProps {
  trade: {
    action: string;
    quantity: number;
    price: number;
  };
  onSubmit: (modifications: any) => void;
}

const TradingModifyPanel: React.FC<TradingModifyPanelProps> = ({
  trade,
  onSubmit,
}) => {
  const [action, setAction] = useState(trade.action);
  const [quantity, setQuantity] = useState(trade.quantity);
  const [price, setPrice] = useState(trade.price);

  const totalAmount = quantity * price;

  return (
    <div>
      <RadioGroup value={action} onChange={setAction}>
        <Radio value="buy">매수</Radio>
        <Radio value="sell">매도</Radio>
      </RadioGroup>

      <Input
        type="number"
        label="수량"
        value={quantity}
        onChange={(e) => setQuantity(Number(e.target.value))}
      />

      <Input
        type="number"
        label="가격"
        value={price}
        onChange={(e) => setPrice(Number(e.target.value))}
      />

      <div>예상 금액: {totalAmount.toLocaleString()}원</div>

      <Button onClick={() => onSubmit({ action, quantity, price })}>
        수정 후 승인
      </Button>
    </div>
  );
};
```

---

## 예시 코드

### React Hook 예시

```tsx
const useHITL = (conversationId: string) => {
  const [approvalRequest, setApprovalRequest] = useState<ApprovalRequest | null>(null);

  const handleApprove = async (requestId: string) => {
    await fetch('/chat/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        thread_id: conversationId,
        decision: 'approved',
        request_id: requestId,
      }),
    });
  };

  const handleReject = async (requestId: string, notes?: string) => {
    await fetch('/chat/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        thread_id: conversationId,
        decision: 'rejected',
        request_id: requestId,
        user_notes: notes,
      }),
    });
  };

  const handleModify = async (
    requestId: string,
    modifications: any,
    userInput?: string
  ) => {
    await fetch('/chat/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        thread_id: conversationId,
        decision: 'modified',
        request_id: requestId,
        modifications,
        user_input: userInput,
      }),
    });
  };

  return {
    approvalRequest,
    setApprovalRequest,
    handleApprove,
    handleReject,
    handleModify,
  };
};
```

### 사용 예시

```tsx
const ChatInterface = () => {
  const { conversationId } = useConversation();
  const { approvalRequest, setApprovalRequest, handleApprove, handleReject, handleModify } =
    useHITL(conversationId);

  const sendMessage = async (message: string) => {
    const response = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        conversation_id: conversationId,
      }),
    });

    const data = await response.json();

    if (data.requires_approval) {
      setApprovalRequest(data.approval_request);
    }
  };

  return (
    <div>
      {approvalRequest && (
        <HITLPanel
          approvalRequest={approvalRequest}
          onApprove={() => handleApprove(approvalRequest.request_id)}
          onReject={(notes) => handleReject(approvalRequest.request_id, notes)}
          onModify={(modifications, userInput) =>
            handleModify(approvalRequest.request_id, modifications, userInput)
          }
        />
      )}
    </div>
  );
};
```

---

## 추가 참고사항

### 1. Interrupt Type별 처리

```typescript
switch (approvalRequest.type) {
  case 'research_plan_approval':
    return <ResearchModifyPanel {...props} />;
  case 'trade_approval':
    return <TradingModifyPanel {...props} />;
  case 'rebalance_approval':
    return <RebalanceModifyPanel {...props} />;
  default:
    return <GenericApprovalPanel {...props} />;
}
```

### 2. Validation

```typescript
const validateModifications = (type: string, modifications: any) => {
  switch (type) {
    case 'research_plan_approval':
      return (
        modifications.depth &&
        modifications.scope &&
        modifications.perspectives.length > 0
      );
    case 'trade_approval':
      return (
        modifications.quantity > 0 &&
        modifications.price > 0
      );
    default:
      return true;
  }
};
```

### 3. Error Handling

```typescript
try {
  await handleModify(requestId, modifications, userInput);
} catch (error) {
  console.error('Modify 요청 실패:', error);
  alert('수정 요청 처리 중 오류가 발생했습니다.');
}
```

---

## 문의

백엔드 API 관련 문의사항은 백엔드 팀에게 연락주세요.

- API 엔드포인트: `/chat`, `/chat/approve`
- Interrupt Type: `research_plan_approval`, `trade_approval`, `rebalance_approval`
- 지원 필드: `modifications`, `user_input`
