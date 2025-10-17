# HAMA Frontend Integration Guide

**프론트엔드 개발자를 위한 API 통합 가이드**

---

## 📋 **개요**

HAMA 백엔드는 **LangGraph 기반 멀티 에이전트 AI 시스템**으로, 프론트엔드와 **RESTful API**로 통신합니다.

### **핵심 기능**
1. 📊 **투자 분석** - 종목 분석, 시장 전망, 리스크 평가
2. 💬 **대화형 인터페이스** - 자연어로 투자 질문 및 지시
3. 🔔 **HITL (Human-in-the-Loop)** - 중요 결정(매매, 리밸런싱)은 사용자 승인 필요
4. 📈 **실시간 데이터** - FinanceDataReader, DART API 연동

---

## 🛠️ **API 엔드포인트**

### **Base URL**
```
http://localhost:8000/api/v1
```

### **주요 엔드포인트**
| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/chat/` | 대화 처리 (메인 인터페이스) |
| POST | `/chat/approve` | HITL 승인/거부 |
| GET | `/chat/history/{conversation_id}` | 대화 이력 조회 |
| DELETE | `/chat/history/{conversation_id}` | 대화 이력 삭제 |

---

## 💬 **1. 대화 API (`/chat/`)**

### **Request**

```typescript
interface ChatRequest {
  message: string;             // 사용자 메시지
  conversation_id?: string;    // 대화 ID (없으면 자동 생성)
  automation_level: 1 | 2 | 3; // 자동화 레벨
}
```

**자동화 레벨:**
- **1 (Pilot)**: AI가 거의 모든 것을 자동 실행
- **2 (Copilot)**: 매매/리밸런싱만 승인 필요 ⭐ (기본값)
- **3 (Advisor)**: 모든 결정 승인 필요

### **Response**

```typescript
interface ChatResponse {
  message: string;              // AI 응답 메시지
  conversation_id: string;      // 대화 ID
  requires_approval: boolean;   // 승인 필요 여부
  approval_request?: {          // 승인 요청 정보 (requires_approval=true일 때)
    type: string;               // "trade_approval" | "rebalancing" 등
    thread_id: string;          // 승인 처리용 스레드 ID
    interrupt_data: object;     // Interrupt 데이터
    message: string;            // 승인 요청 메시지
  };
  metadata?: {
    intent?: string;            // 의도 분석 결과
    agents_called?: string[];   // 호출된 에이전트 목록
    automation_level: number;
  };
}
```

### **예시 1: 일반 질문 (HITL 없음)**

```javascript
// Request
const response = await fetch('http://localhost:8000/api/v1/chat/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: "삼성전자 주가는 얼마야?",
    automation_level: 2
  })
});

const data = await response.json();

// Response
{
  "message": "📊 삼성전자의 현재 주가는 89,000원입니다...",
  "conversation_id": "abc123-def456",
  "requires_approval": false,  // ✅ 승인 불필요
  "metadata": {
    "intent": "stock_inquiry",
    "agents_called": ["research_agent"]
  }
}
```

### **예시 2: 매매 요청 (HITL 발생)**

```javascript
// Request
const response = await fetch('http://localhost:8000/api/v1/chat/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: "삼성전자 10주 매수해줘",
    automation_level: 2  // Copilot: 매매 승인 필요
  })
});

const data = await response.json();

// Response
{
  "message": "🔔 사용자 승인이 필요합니다.",
  "conversation_id": "abc123-def456",
  "requires_approval": true,  // ⚠️ 승인 필요!
  "approval_request": {
    "type": "trade_approval",
    "thread_id": "abc123-def456",  // ⭐ 승인 시 사용
    "interrupt_data": {
      "type": "trade_approval",
      "order_id": "ORDER_a1b2c3d4",
      "stock_code": "005930",
      "quantity": 10,
      "order_type": "buy",
      "message": "매매 주문 'ORDER_a1b2c3d4'을(를) 승인하시겠습니까?"
    },
    "message": "매매 주문을 승인하시겠습니까?"
  }
}
```

---

## ✅ **2. 승인 API (`/chat/approve`)**

### **Request**

```typescript
interface ApprovalRequest {
  thread_id: string;             // approval_request.thread_id
  decision: "approved" | "rejected" | "modified";
  automation_level: 1 | 2 | 3;
  modifications?: object;        // decision="modified"일 때 수정 내용
  user_notes?: string;           // 사용자 메모
}
```

### **Response**

```typescript
interface ApprovalResponse {
  status: "approved" | "rejected" | "modified";
  message: string;
  conversation_id: string;
  result?: object;  // 거래 실행 결과 (status="approved"일 때)
}
```

### **예시 1: 승인 (Approved)**

```javascript
// Request
const response = await fetch('http://localhost:8000/api/v1/chat/approve', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    thread_id: "abc123-def456",  // ⭐ chat response의 thread_id
    decision: "approved",
    automation_level: 2,
    user_notes: "좋은 타이밍인 것 같아요"
  })
});

const data = await response.json();

// Response
{
  "status": "approved",
  "message": "승인 완료 - 매매가 실행되었습니다.",
  "conversation_id": "abc123-def456",
  "result": {
    "order_id": "ORDER_a1b2c3d4",
    "status": "executed",
    "stock_code": "005930",
    "price": 89000,
    "quantity": 10,
    "total": 890000
  }
}
```

### **예시 2: 거부 (Rejected)**

```javascript
// Request
const response = await fetch('http://localhost:8000/api/v1/chat/approve', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    thread_id: "abc123-def456",
    decision: "rejected",
    automation_level: 2,
    user_notes: "가격이 너무 높아요"
  })
});

// Response
{
  "status": "rejected",
  "message": "승인 거부 - 매매가 취소되었습니다.",
  "conversation_id": "abc123-def456",
  "result": {
    "cancelled": true
  }
}
```

---

## 🔄 **3. 전체 플로우 (React 예시)**

### **Step 1: 대화 컴포넌트**

```typescript
import React, { useState } from 'react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

const ChatInterface: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [awaitingApproval, setAwaitingApproval] = useState(false);
  const [approvalData, setApprovalData] = useState<any>(null);

  const sendMessage = async () => {
    const userMessage = input;
    setInput('');

    // 사용자 메시지 추가
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);

    // API 호출
    const response = await fetch('http://localhost:8000/api/v1/chat/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: userMessage,
        conversation_id: conversationId,
        automation_level: 2
      })
    });

    const data = await response.json();
    setConversationId(data.conversation_id);

    // ⚠️ 승인 필요한 경우
    if (data.requires_approval) {
      setAwaitingApproval(true);
      setApprovalData(data.approval_request);

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `⚠️ 승인이 필요합니다.\n\n${data.approval_request.message}`
      }]);
    } else {
      // ✅ 일반 응답
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.message
      }]);
    }
  };

  const handleApproval = async (decision: 'approved' | 'rejected') => {
    const response = await fetch('http://localhost:8000/api/v1/chat/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        thread_id: approvalData.thread_id,
        decision: decision,
        automation_level: 2
      })
    });

    const data = await response.json();

    setAwaitingApproval(false);
    setApprovalData(null);

    setMessages(prev => [...prev, {
      role: 'assistant',
      content: data.message
    }]);
  };

  return (
    <div className="chat-container">
      {/* 메시지 목록 */}
      <div className="messages">
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            {msg.content}
          </div>
        ))}
      </div>

      {/* 승인 버튼 (awaiting_approval일 때만 표시) */}
      {awaitingApproval && (
        <div className="approval-buttons">
          <button onClick={() => handleApproval('approved')}>
            ✅ 승인
          </button>
          <button onClick={() => handleApproval('rejected')}>
            ❌ 거부
          </button>
        </div>
      )}

      {/* 입력창 */}
      <div className="input-box">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
          placeholder="메시지를 입력하세요..."
        />
        <button onClick={sendMessage}>전송</button>
      </div>
    </div>
  );
};
```

---

## 🎨 **4. UI/UX 권장 사항**

### **승인 요청 UI**

```
┌─────────────────────────────────────┐
│ 🤖 AI Assistant                     │
├─────────────────────────────────────┤
│ ⚠️ 매매 주문 승인이 필요합니다       │
│                                     │
│ 종목: 삼성전자 (005930)             │
│ 주문: 매수 10주                     │
│ 예상가: 89,000원                    │
│ 총액: 890,000원                     │
│                                     │
│ [✅ 승인]  [❌ 거부]  [✏️ 수정]   │
└─────────────────────────────────────┘
```

### **상태 표시**

- **분석 중**: `🔍 AI가 분석 중입니다...`
- **승인 대기**: `⚠️ 승인이 필요합니다`
- **실행 중**: `⏳ 거래를 실행 중입니다...`
- **완료**: `✅ 거래가 완료되었습니다`
- **거부됨**: `❌ 거래가 취소되었습니다`

---

## 📡 **5. WebSocket (실시간 알림) - Phase 2**

**현재는 구현되지 않았지만, Phase 2에서 추가 예정:**

```typescript
// WebSocket 연결 (예정)
const ws = new WebSocket('ws://localhost:8000/ws/chat');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.type === 'approval_required') {
    // 실시간 승인 요청 알림
    showApprovalNotification(data);
  } else if (data.type === 'trade_executed') {
    // 거래 실행 알림
    showTradeNotification(data);
  }
};
```

---

## 🔧 **6. 에러 처리**

### **HTTP 상태 코드**
- `200 OK` - 성공
- `400 Bad Request` - 잘못된 요청
- `500 Internal Server Error` - 서버 에러

### **에러 응답 형식**
```json
{
  "detail": "Unexpected error: ..."
}
```

### **에러 처리 예시**
```typescript
try {
  const response = await fetch('/api/v1/chat/', { ... });

  if (!response.ok) {
    const error = await response.json();
    console.error('API Error:', error.detail);
    alert(`오류: ${error.detail}`);
    return;
  }

  const data = await response.json();
  // ... 정상 처리
} catch (error) {
  console.error('Network Error:', error);
  alert('서버와 연결할 수 없습니다.');
}
```

---

## 📊 **7. 데이터 모델**

### **Automation Level**
```typescript
enum AutomationLevel {
  PILOT = 1,      // 거의 자동
  COPILOT = 2,    // 매매/리밸런싱 승인 필요 (기본값)
  ADVISOR = 3     // 모든 결정 승인 필요
}
```

### **Approval Type**
```typescript
type ApprovalType =
  | "trade_approval"         // 매매 승인
  | "rebalancing"            // 리밸런싱 승인
  | "portfolio_adjustment"   // 포트폴리오 조정 승인
  | "approval_needed";       // 기타 승인
```

### **Decision Type**
```typescript
type Decision =
  | "approved"   // 승인
  | "rejected"   // 거부
  | "modified";  // 수정 후 승인
```

---

## 🧪 **8. 개발 팁**

### **CORS 설정**
백엔드에서 CORS가 설정되어 있으므로, 로컬 개발 시 문제 없습니다.

```typescript
// Vite 개발 서버 설정 (vite.config.ts)
export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
});
```

### **환경 변수**
```bash
# .env.local
VITE_API_URL=http://localhost:8000/api/v1
```

```typescript
// API 호출
const API_URL = import.meta.env.VITE_API_URL;

fetch(`${API_URL}/chat/`, { ... });
```

### **TypeScript 타입 정의**
```bash
# types/api.ts 에 모든 인터페이스 정의
```

---

## 📚 **9. 참고 자료**

- **API 문서**: OpenAPI (Swagger) - `http://localhost:8000/docs`
- **백엔드 구조**: `docs/langgraph-supervisor-architecture.md`
- **테스트 예시**: `tests/test_api_chat.py`

---

## 🚀 **10. 시작하기**

### **1. 백엔드 실행**
```bash
cd HAMA-backend
python -m uvicorn src.main:app --reload
```

### **2. API 테스트**
```bash
# 간단한 질문
curl -X POST http://localhost:8000/api/v1/chat/ \
  -H "Content-Type: application/json" \
  -d '{
    "message": "안녕하세요",
    "automation_level": 2
  }'

# 매매 요청 (HITL 발생)
curl -X POST http://localhost:8000/api/v1/chat/ \
  -H "Content-Type: application/json" \
  -d '{
    "message": "삼성전자 10주 매수해줘",
    "automation_level": 2
  }'
```

### **3. 프론트엔드 개발**
위의 React 예시 코드를 참고하여 구현하세요!

---

**문서 버전**: 1.0
**최종 업데이트**: 2025-10-06
**작성자**: HAMA Backend Team
