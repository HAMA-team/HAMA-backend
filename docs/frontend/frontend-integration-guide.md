# Frontend 연동 가이드

**버전:** 1.0
**최종 업데이트:** 2025-10-26
**목적:** Frontend PRD v3.0 요구사항에 맞는 Backend API 사용 가이드

---

## 📚 목차

1. [환경 설정](#1-환경-설정)
2. [Chat API](#2-chat-api)
3. [Portfolio API](#3-portfolio-api)
4. [HITL 승인 API](#4-hitl-승인-api)
5. [Onboarding API](#5-onboarding-api)
6. [에러 핸들링](#6-에러-핸들링)
7. [TypeScript 타입 정의](#7-typescript-타입-정의)

---

## 1. 환경 설정

### 1.1 환경 변수

`.env.local` 파일 생성:

```bash
# Frontend 환경 변수
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

### 1.2 API Client 생성

```typescript
// lib/api/client.ts
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

class APIError extends Error {
  constructor(
    public status: number,
    public message: string,
    public code?: string
  ) {
    super(message);
    this.name = 'APIError';
  }
}

export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      message: 'Unknown error',
      code: 'UNKNOWN_ERROR',
    }));

    throw new APIError(response.status, error.message, error.code);
  }

  return await response.json();
}
```

---

## 2. Chat API

### 2.1 기본 대화

**Endpoint:** `POST /chat`

**Request:**
```typescript
interface ChatRequest {
  message: string;
  conversation_id?: string;
  intervention_required?: number; // 1, 2, 3 (default: 2)
}
```

**Response (일반):**
```typescript
interface ChatResponse {
  message: string;                // AI 답변 (Markdown)
  conversation_id: string;
  requires_approval: boolean;     // false
  thinking?: ThinkingStep[];
  timestamp: string;
  metadata?: {
    intent: string;
    agents_called: string[];
  };
}

interface ThinkingStep {
  agent: string;
  description: string;
  timestamp: string;
}
```

**사용 예시:**
```typescript
// lib/api/chat.ts
import { apiRequest } from './client';

export async function sendMessage(message: string, conversationId?: string) {
  return apiRequest<ChatResponse>('/chat', {
    method: 'POST',
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
      intervention_required: 2,
    }),
  });
}

// 컴포넌트에서 사용
const handleSubmit = async (message: string) => {
  try {
    const response = await sendMessage(message, conversationId);

    if (response.requires_approval) {
      // HITL 패널 열기
      openApprovalPanel(response.approval_request);
    } else {
      // 일반 답변 표시
      addMessage({
        role: 'assistant',
        content: response.message,
        thinking: response.thinking,
      });
    }
  } catch (error) {
    if (error instanceof APIError) {
      toast.error(error.message);
    }
  }
};
```

### 2.2 Thinking Trace 스트리밍 (SSE)

**Endpoint:** `POST /chat/stream`

**EventSource 연동:**
```typescript
// hooks/useChatStream.ts
import { useState, useEffect } from 'react';

interface StreamEvent {
  type: 'thought' | 'tool_call' | 'tool_result' | 'answer' | 'done' | 'error';
  content: any;
}

export function useChatStream(message: string, conversationId: string) {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);

  useEffect(() => {
    if (!message) return;

    setIsStreaming(true);

    const eventSource = new EventSource(
      `${process.env.NEXT_PUBLIC_API_URL}/chat/stream?` +
      `message=${encodeURIComponent(message)}&conversation_id=${conversationId}`
    );

    // Thinking 과정
    eventSource.addEventListener('thought', (event) => {
      const data = JSON.parse(event.data);
      setEvents((prev) => [...prev, { type: 'thought', content: data.content }]);
    });

    // 도구 호출
    eventSource.addEventListener('tool_call', (event) => {
      const data = JSON.parse(event.data);
      setEvents((prev) => [...prev, { type: 'tool_call', content: data }]);
    });

    // 최종 답변
    eventSource.addEventListener('answer', (event) => {
      const data = JSON.parse(event.data);
      setEvents((prev) => [...prev, { type: 'answer', content: data.content }]);
    });

    // 완료
    eventSource.addEventListener('done', (event) => {
      setIsStreaming(false);
      eventSource.close();
    });

    // 에러
    eventSource.addEventListener('error', (event) => {
      console.error('SSE Error:', event);
      setIsStreaming(false);
      eventSource.close();

      // Fallback: 폴링 모드
      toast.warning('실시간 업데이트를 사용할 수 없습니다');
    });

    eventSource.onerror = (error) => {
      console.error('EventSource failed:', error);
      eventSource.close();
      setIsStreaming(false);
    };

    return () => {
      eventSource.close();
    };
  }, [message, conversationId]);

  return { events, isStreaming };
}
```

**컴포넌트 사용:**
```tsx
// components/chat/ThinkingSection.tsx
export function ThinkingSection({ events }: { events: StreamEvent[] }) {
  const [isExpanded, setIsExpanded] = useState(false);

  const thinkingEvents = events.filter((e) => e.type === 'thought');

  if (thinkingEvents.length === 0) return null;

  return (
    <div className="my-4 border-l-4 border-blue-500 pl-4">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 text-sm text-gray-600"
      >
        <span>{isExpanded ? '▼' : '▶'}</span>
        <span>AI 사고 과정 ({thinkingEvents.length}단계)</span>
      </button>

      {isExpanded && (
        <div className="mt-2 space-y-2">
          {thinkingEvents.map((event, index) => (
            <div key={index} className="text-sm text-gray-700">
              🔍 {event.content}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

---

## 3. Portfolio API

### 3.1 차트 데이터 조회

**Endpoint:** `GET /portfolio/chart-data`

**Response:**
```typescript
interface PortfolioChartData {
  stocks: StockChartData[];
  total_value: number;
  total_return: number;
  total_return_percent: number;
  cash: number;
  sectors: { [sector: string]: number };  // 섹터별 비중 (0~1)
}

interface StockChartData {
  stock_code: string;
  stock_name: string;
  quantity: number;
  current_price: number;
  purchase_price: number;
  weight: number;           // 비중 (0~1)
  return_percent: number;
  sector: string;
}
```

**사용 예시:**
```typescript
// lib/api/portfolio.ts
export async function getPortfolioChartData() {
  return apiRequest<PortfolioChartData>('/portfolio/chart-data');
}

// 컴포넌트
import { useQuery } from '@tanstack/react-query';

export function PortfolioChart() {
  const { data, isLoading } = useQuery({
    queryKey: ['portfolio', 'chart-data'],
    queryFn: getPortfolioChartData,
    refetchInterval: 60000, // 1분마다 자동 새로고침
  });

  if (isLoading) return <LoadingSpinner />;
  if (!data) return <EmptyState />;

  return (
    <div>
      <h2>총 평가금액: {data.total_value.toLocaleString()}원</h2>
      <h3>총 수익률: {data.total_return_percent.toFixed(2)}%</h3>

      {/* Treemap */}
      <TreemapChart data={data.stocks} />

      {/* Pie Chart (섹터별) */}
      <PieChart data={Object.entries(data.sectors).map(([name, weight]) => ({
        name,
        value: weight * 100
      }))} />

      {/* Bar Chart (수익률 순) */}
      <BarChart data={[...data.stocks].sort((a, b) =>
        b.return_percent - a.return_percent
      )} />
    </div>
  );
}
```

### 3.2 Recharts 연동 예시

**Treemap:**
```tsx
import { Treemap, ResponsiveContainer } from 'recharts';

export function TreemapChart({ data }: { data: StockChartData[] }) {
  const treemapData = data.map((stock) => ({
    name: stock.stock_name,
    size: stock.weight * 100,
    color: stock.return_percent > 0 ? '#10B981' : '#EF4444',
  }));

  return (
    <ResponsiveContainer width="100%" height={400}>
      <Treemap
        data={treemapData}
        dataKey="size"
        stroke="#fff"
        fill="#8884d8"
        content={<CustomizedContent />}
      />
    </ResponsiveContainer>
  );
}
```

**Pie Chart (섹터별):**
```tsx
import { PieChart, Pie, Cell, Legend } from 'recharts';

export function SectorPieChart({ sectors }: { sectors: { [key: string]: number } }) {
  const data = Object.entries(sectors).map(([name, weight]) => ({
    name,
    value: weight * 100,
  }));

  const COLORS = ['#8B5CF6', '#F59E0B', '#10B981', '#3B82F6', '#6B7280'];

  return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          labelLine={false}
          label={(entry) => `${entry.name} ${entry.value.toFixed(1)}%`}
          outerRadius={80}
          fill="#8884d8"
          dataKey="value"
        >
          {data.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}
```

---

## 4. HITL 승인 API

### 4.1 승인 요청 처리

**Endpoint:** `POST /chat/approve`

**Request:**
```typescript
interface ApprovalDecision {
  thread_id: string;
  decision: 'approved' | 'rejected' | 'modified';
  intervention_required?: number;
  modifications?: any;
  user_notes?: string;
}
```

**Response:**
```typescript
interface ApprovalResponse {
  status: string;
  message: string;
  conversation_id: string;
  result?: {
    order_id: string;
    status: string;
    price: number;
    quantity: number;
  };
}
```

**사용 예시:**
```typescript
// components/hitl/ApprovalPanel.tsx
import { useState } from 'react';

export function ApprovalPanel({
  approvalRequest,
  threadId,
  onClose,
}: {
  approvalRequest: ApprovalRequest;
  threadId: string;
  onClose: () => void;
}) {
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleApprove = async () => {
    setIsSubmitting(true);

    try {
      const response = await apiRequest<ApprovalResponse>('/chat/approve', {
        method: 'POST',
        body: JSON.stringify({
          thread_id: threadId,
          decision: 'approved',
          intervention_required: 2,
        }),
      });

      toast.success('✅ ' + response.message);
      onClose();
    } catch (error) {
      if (error instanceof APIError) {
        toast.error(error.message);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReject = async () => {
    setIsSubmitting(true);

    try {
      const response = await apiRequest<ApprovalResponse>('/chat/approve', {
        method: 'POST',
        body: JSON.stringify({
          thread_id: threadId,
          decision: 'rejected',
        }),
      });

      toast.info(response.message);
      onClose();
    } catch (error) {
      if (error instanceof APIError) {
        toast.error(error.message);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed right-0 top-0 h-full w-1/2 bg-white shadow-2xl p-6">
      <h2 className="text-2xl font-bold mb-4">⚠️ 승인 필요</h2>

      {/* 주문 내역 */}
      <div className="mb-6">
        <h3 className="font-semibold mb-2">주문 내역</h3>
        <ul className="space-y-1">
          <li>종목: {approvalRequest.stock_name}</li>
          <li>수량: {approvalRequest.quantity}주</li>
          <li>가격: {approvalRequest.price.toLocaleString()}원</li>
          <li>총액: {approvalRequest.total_amount.toLocaleString()}원</li>
        </ul>
      </div>

      {/* 리스크 경고 */}
      {approvalRequest.risk_warning && (
        <div className="bg-red-50 border-l-4 border-red-500 p-4 mb-6">
          <p className="text-sm text-red-700">{approvalRequest.risk_warning}</p>
          <div className="mt-2">
            <p className="text-xs text-gray-600">
              현재 비중: {(approvalRequest.current_weight * 100).toFixed(1)}%
            </p>
            <p className="text-xs text-gray-600">
              예상 비중: {(approvalRequest.expected_weight * 100).toFixed(1)}%
            </p>
          </div>
        </div>
      )}

      {/* 대안 제시 */}
      {approvalRequest.alternatives && (
        <div className="mb-6">
          <h3 className="font-semibold mb-2">💡 권장 대안</h3>
          <ul className="space-y-2">
            {approvalRequest.alternatives.map((alt, index) => (
              <li key={index} className="bg-gray-50 p-2 rounded">
                {alt.suggestion}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 액션 버튼 */}
      <div className="flex gap-4">
        <button
          onClick={handleApprove}
          disabled={isSubmitting}
          className="flex-1 bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 disabled:bg-gray-300"
        >
          {isSubmitting ? '처리 중...' : '승인'}
        </button>
        <button
          onClick={handleReject}
          disabled={isSubmitting}
          className="flex-1 bg-gray-200 text-gray-700 px-4 py-2 rounded hover:bg-gray-300"
        >
          거부
        </button>
      </div>
    </div>
  );
}
```

---

## 5. Onboarding API

### 5.1 투자 성향 분석

**Endpoint:** `POST /onboarding/screening`

**Request:**
```typescript
interface ScreeningRequest {
  screening_answers: {
    investment_goal: string;
    investment_period: string;
    risk_questions: Array<{ q: string; a: string }>;
    preferred_sectors: string[];
    expected_trade_frequency: string;
  };
  portfolio_data?: Array<{
    stock_code: string;
    quantity: number;
    avg_price: number;
  }>;
}
```

**Response:**
```typescript
interface ScreeningResponse {
  user_id: string;
  profile: {
    expertise_level: string;
    investment_style: string;
    risk_tolerance: string;
    preferred_sectors: string[];
    trading_style: string;
    portfolio_concentration: number;
    technical_level: string;
    preferred_depth: string;
    wants_explanations: boolean;
    wants_analogies: boolean;
    llm_generated_profile: string;
  };
  message: string;
}
```

**사용 예시:**
```typescript
// 온보딩 플로우
const handleOnboardingComplete = async (answers: any) => {
  const response = await apiRequest<ScreeningResponse>('/onboarding/screening', {
    method: 'POST',
    body: JSON.stringify({
      screening_answers: answers,
    }),
  });

  // 프로파일 저장
  localStorage.setItem('userId', response.user_id);
  localStorage.setItem('profile', JSON.stringify(response.profile));

  toast.success(response.message);
  router.push('/chat');
};
```

---

## 6. 에러 핸들링

### 6.1 표준 에러 응답

모든 에러는 다음 형식으로 반환됩니다:

```typescript
interface ErrorResponse {
  error: true;
  message: string;
  code: string;
  timestamp: string;
  details?: any;
}
```

### 6.2 에러 코드 및 처리

| Code | Status | Message | 처리 방법 |
|------|--------|---------|----------|
| `VALIDATION_ERROR` | 422 | 요청 데이터가 올바르지 않습니다 | 입력값 확인 |
| `NOT_FOUND` | 404 | 리소스를 찾을 수 없습니다 | 존재 여부 확인 |
| `RATE_LIMIT_EXCEEDED` | 429 | 요청이 너무 많습니다 | 60초 후 재시도 |
| `UNAUTHORIZED` | 401 | 로그인이 필요합니다 | 로그인 페이지로 이동 |
| `FORBIDDEN` | 403 | 접근 권한이 없습니다 | 권한 확인 |
| `INTERNAL_SERVER_ERROR` | 500 | 서버 오류가 발생했습니다 | 관리자에게 문의 |

### 6.3 Global Error Handler

```typescript
// lib/api/error-handler.ts
export function handleAPIError(error: unknown) {
  if (error instanceof APIError) {
    switch (error.code) {
      case 'VALIDATION_ERROR':
        toast.error('입력값을 확인해주세요');
        break;
      case 'NOT_FOUND':
        toast.error('요청하신 리소스를 찾을 수 없습니다');
        break;
      case 'RATE_LIMIT_EXCEEDED':
        toast.error('요청이 너무 많습니다. 잠시 후 다시 시도해주세요');
        break;
      case 'UNAUTHORIZED':
        toast.error('로그인이 필요합니다');
        router.push('/login');
        break;
      case 'INTERNAL_SERVER_ERROR':
        toast.error('서버 오류가 발생했습니다');
        break;
      default:
        toast.error(error.message);
    }
  } else {
    toast.error('알 수 없는 오류가 발생했습니다');
  }
}
```

---

## 7. TypeScript 타입 정의

### 7.1 전체 타입 파일

```typescript
// types/api.ts

// Chat
export interface ChatRequest {
  message: string;
  conversation_id?: string;
  intervention_required?: number;
}

export interface ChatResponse {
  message: string;
  conversation_id: string;
  requires_approval: boolean;
  approval_request?: ApprovalRequest;
  thinking?: ThinkingStep[];
  timestamp: string;
  metadata?: any;
}

export interface ThinkingStep {
  agent: string;
  description: string;
  timestamp: string;
}

// HITL
export interface ApprovalRequest {
  action: 'buy' | 'sell';
  stock_code: string;
  stock_name: string;
  quantity: number;
  price: number;
  total_amount: number;
  current_weight: number;
  expected_weight: number;
  risk_warning?: string;
  alternatives?: Alternative[];
  expected_portfolio_preview?: {
    current: PortfolioPreview[];
    after_approval: PortfolioPreview[];
  };
}

export interface Alternative {
  suggestion: string;
  adjusted_quantity: number;
  adjusted_amount: number;
}

export interface PortfolioPreview {
  stock_name: string;
  weight: number;
  color: string;
}

// Portfolio
export interface PortfolioChartData {
  stocks: StockChartData[];
  total_value: number;
  total_return: number;
  total_return_percent: number;
  cash: number;
  sectors: { [sector: string]: number };
}

export interface StockChartData {
  stock_code: string;
  stock_name: string;
  quantity: number;
  current_price: number;
  purchase_price: number;
  weight: number;
  return_percent: number;
  sector: string;
}

// Error
export class APIError extends Error {
  constructor(
    public status: number,
    public message: string,
    public code?: string
  ) {
    super(message);
    this.name = 'APIError';
  }
}
```

---

## 8. 개발 팁

### 8.1 React Query 활용

```typescript
// hooks/usePortfolio.ts
import { useQuery } from '@tanstack/react-query';
import { getPortfolioChartData } from '@/lib/api/portfolio';

export function usePortfolio() {
  return useQuery({
    queryKey: ['portfolio', 'chart-data'],
    queryFn: getPortfolioChartData,
    staleTime: 60000,      // 1분 동안 캐시 유지
    refetchInterval: 60000, // 1분마다 자동 새로고침
    retry: 3,              // 실패 시 3번 재시도
  });
}
```

### 8.2 낙관적 업데이트

```typescript
// 승인 후 즉시 UI 업데이트
const { mutate } = useMutation({
  mutationFn: (decision: ApprovalDecision) =>
    apiRequest('/chat/approve', {
      method: 'POST',
      body: JSON.stringify(decision),
    }),
  onMutate: async () => {
    // 낙관적 업데이트
    await queryClient.cancelQueries(['portfolio']);
    const previousData = queryClient.getQueryData(['portfolio']);

    // UI 즉시 업데이트
    queryClient.setQueryData(['portfolio'], (old: any) => ({
      ...old,
      // 예상 변경사항 반영
    }));

    return { previousData };
  },
  onError: (err, variables, context) => {
    // 실패 시 롤백
    queryClient.setQueryData(['portfolio'], context?.previousData);
  },
  onSettled: () => {
    // 성공/실패 관계없이 최종 데이터 새로고침
    queryClient.invalidateQueries(['portfolio']);
  },
});
```

---

## 9. 참고 자료

- **Backend API Docs**: `http://localhost:8000/docs` (Swagger UI)
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`
- **Gap Analysis**: `docs/frontend-backend-gap-analysis.md`
- **Phase 1 Plan**: `docs/plan/phase1-frontend-integration.md`

---

**작성자:** Backend Team
**문의:** GitHub Issues
