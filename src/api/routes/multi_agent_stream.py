"""
멀티 에이전트 실행을 실시간으로 스트리밍
Master Agent → 서브 에이전트들의 협업 과정을 시각화
"""
import json
import logging
import re
import uuid
from typing import AsyncGenerator, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage

from src.agents.aggregator import personalize_response
from src.agents.router import route_query
from src.services.stock_data_service import stock_data_service
from src.services.user_profile_service import user_profile_service
from src.models.database import get_db_context

logger = logging.getLogger(__name__)

router = APIRouter()

_STOCK_NAME_STOPWORDS = {
    "현재",
    "지금",
    "주식",
    "주가",
    "가격",
    "얼마",
    "얼마지",
    "분석",
    "어때",
    "상황",
    "정보",
    "알려줘",
    "문의",
    "질문",
    "요청",
}


async def resolve_stock_code(message: str) -> Optional[str]:
    """
    사용자 질의에서 종목 코드를 추출하거나 종목명으로 매핑한다.
    """
    digit_match = re.search(r"\b(\d{6})\b", message)
    if digit_match:
        return digit_match.group(1)

    candidates = re.findall(r"[가-힣A-Za-z]{2,}", message)
    tried = set()
    for candidate in candidates:
        token = candidate.strip()
        if not token or token in _STOCK_NAME_STOPWORDS:
            continue
        if token in tried:
            continue
        tried.add(token)

        for market in ("KOSPI", "KOSDAQ", "KONEX"):
            code = await stock_data_service.get_stock_by_name(token, market=market)
            if code:
                return code

    return None


class MultiAgentStreamRequest(BaseModel):
    """멀티 에이전트 스트리밍 요청"""
    message: str
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    automation_level: int = Field(default=2, ge=1, le=3)


async def stream_multi_agent_execution(
    message: str,
    user_id: str,
    conversation_id: str,
    automation_level: int
) -> AsyncGenerator[str, None]:
    """
    멀티 에이전트 실행을 SSE로 스트리밍

    프론트엔드에서 받는 이벤트:
    - master_start: Master Agent 시작
    - master_routing: Router 판단 (어떤 에이전트들을 호출할지)
    - agent_start: 서브 에이전트 시작
    - agent_node: 에이전트 내부 노드 실행
    - agent_llm_start: LLM 호출 시작
    - agent_llm_stream: LLM 응답 스트리밍
    - agent_llm_end: LLM 호출 완료
    - agent_complete: 서브 에이전트 완료
    - master_aggregating: Master가 결과 집계 중
    - master_complete: 전체 완료
    - error: 에러 발생
    """

    try:
        # 1. Master Agent 시작
        yield f"event: master_start\ndata: {json.dumps({'message': '분석을 시작합니다...'}, ensure_ascii=False)}\n\n"

        # 2. 사용자 프로파일 로드
        with get_db_context() as db:
            user_profile = user_profile_service.get_user_profile(user_id, db)

        yield f"event: user_profile\ndata: {json.dumps({'profile_loaded': True}, ensure_ascii=False)}\n\n"

        # 3. Router 판단 (어떤 에이전트를 호출할지)
        routing_decision = await route_query(
            query=message,
            user_profile=user_profile,
            conversation_history=[]
        )

        agents_to_call = list(dict.fromkeys(routing_decision.agents_to_call))
        if not agents_to_call:
            agents_to_call = ["general"]

        yield f"event: master_routing\ndata: {json.dumps({'agents': agents_to_call, 'depth_level': routing_decision.depth_level}, ensure_ascii=False)}\n\n"

        # 4. 각 에이전트 실행
        agent_results = {}
        resolved_stock_code: Optional[str] = None

        for agent_name in agents_to_call:
            yield f"event: agent_start\ndata: {json.dumps({'agent': agent_name, 'message': f'{agent_name.upper()} Agent 실행 중...'}, ensure_ascii=False)}\n\n"

            # Research Agent 예시
            if agent_name == "research":
                from src.agents.research.graph import build_research_subgraph

                agent = build_research_subgraph()
                if resolved_stock_code is None:
                    resolved_stock_code = await resolve_stock_code(message)
                if not resolved_stock_code:
                    raise ValueError("질문에서 종목 코드를 추출하지 못했습니다.")

                input_state = {
                    "messages": [HumanMessage(content=message)],
                    "stock_code": resolved_stock_code,
                    "query": message,
                    "request_id": conversation_id,
                }

                # 스트리밍 실행
                node_count = 0
                async for event in agent.astream_events(input_state, version="v2"):
                    event_type = event["event"]

                    # 노드 실행
                    if event_type == "on_chain_start":
                        node_name = event.get("name", "")
                        if node_name and node_name != "LangGraph":
                            node_count += 1
                            yield f"event: agent_node\ndata: {json.dumps({'agent': agent_name, 'node': node_name, 'status': 'running', 'message': f'{node_name} 노드 실행 중...'}, ensure_ascii=False)}\n\n"

                    # 노드 완료
                    elif event_type == "on_chain_end":
                        node_name = event.get("name", "")
                        if node_name and node_name != "LangGraph":
                            yield f"event: agent_node\ndata: {json.dumps({'agent': agent_name, 'node': node_name, 'status': 'complete', 'message': f'{node_name} 완료'}, ensure_ascii=False)}\n\n"

                    # LLM 호출 시작
                    elif event_type == "on_chat_model_start":
                        model = event.get("name", "LLM")
                        yield f"event: agent_llm_start\ndata: {json.dumps({'agent': agent_name, 'model': model, 'message': 'AI 분석 중...'}, ensure_ascii=False)}\n\n"

                    # LLM 스트리밍 (선택적, 너무 많으면 생략)
                    # elif event_type == "on_chat_model_stream":
                    #     chunk = event.get("data", {}).get("chunk", {})
                    #     if hasattr(chunk, "content") and chunk.content:
                    #         yield f"event: agent_llm_stream\ndata: {json.dumps({'agent': agent_name, 'content': chunk.content}, ensure_ascii=False)}\n\n"

                    # LLM 완료
                    elif event_type == "on_chat_model_end":
                        yield f"event: agent_llm_end\ndata: {json.dumps({'agent': agent_name, 'message': 'AI 분석 완료'}, ensure_ascii=False)}\n\n"

                # 최종 결과 가져오기
                final_result = await agent.ainvoke(input_state)
                agent_results[agent_name] = final_result

                # 에이전트 완료
                consensus = final_result.get("consensus", {})
                yield f"event: agent_complete\ndata: {json.dumps({'agent': agent_name, 'result': {'recommendation': consensus.get('recommendation'), 'target_price': consensus.get('target_price'), 'confidence': consensus.get('confidence')}}, ensure_ascii=False)}\n\n"
            elif agent_name == "general":
                from src.agents.general.graph import build_general_subgraph

                agent = build_general_subgraph()

                input_state = {
                    "messages": [HumanMessage(content=message)],
                    "query": message,
                    "request_id": conversation_id,
                    "answer": None,
                    "sources": [],
                }

                result = await agent.ainvoke(input_state)
                agent_results[agent_name] = result

                yield f"event: agent_complete\ndata: {json.dumps({'agent': agent_name, 'result': {'answer': result.get('answer')}}, ensure_ascii=False)}\n\n"

            elif agent_name == "strategy":
                # Strategy Agent (간단한 mock)
                yield f"event: agent_node\ndata: {json.dumps({'agent': agent_name, 'node': 'analyze_market', 'status': 'running'}, ensure_ascii=False)}\n\n"
                yield f"event: agent_node\ndata: {json.dumps({'agent': agent_name, 'node': 'generate_strategy', 'status': 'running'}, ensure_ascii=False)}\n\n"
                yield f"event: agent_complete\ndata: {json.dumps({'agent': agent_name, 'result': {'strategy': 'MOMENTUM', 'allocation': 0.3}}, ensure_ascii=False)}\n\n"

            elif agent_name == "risk":
                # Risk Agent (간단한 mock)
                yield f"event: agent_node\ndata: {json.dumps({'agent': agent_name, 'node': 'calculate_risk', 'status': 'running'}, ensure_ascii=False)}\n\n"
                yield f"event: agent_complete\ndata: {json.dumps({'agent': agent_name, 'result': {'risk_level': 'MEDIUM', 'max_loss': 0.15}}, ensure_ascii=False)}\n\n"
            else:
                logger.warning("⚠️ [MultiAgentStream] 지원되지 않는 에이전트 요청: %s", agent_name)
                yield f"event: agent_complete\ndata: {json.dumps({'agent': agent_name, 'result': {'warning': '지원되지 않는 에이전트입니다.'}}, ensure_ascii=False)}\n\n"

        # 5. Master가 결과 집계
        yield f"event: master_aggregating\ndata: {json.dumps({'message': '분석 결과를 종합하고 있습니다...'}, ensure_ascii=False)}\n\n"

        # 6. 답변 개인화
        personalized = await personalize_response(
            agent_results=agent_results,
            user_profile=user_profile,
            routing_decision=routing_decision.model_dump()
        )

        final_response = personalized.get("response", "분석이 완료되었습니다.")

        # 7. 완료
        yield f"event: master_complete\ndata: {json.dumps({'message': final_response, 'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"
        yield f"event: done\ndata: {json.dumps({'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"

        logger.info("✅ [MultiAgentStream] 완료")

    except Exception as e:
        logger.error(f"❌ [MultiAgentStream] 에러: {e}", exc_info=True)
        yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"


@router.post("/multi-stream")
async def multi_agent_stream(request: MultiAgentStreamRequest):
    """
    멀티 에이전트 실행을 실시간으로 스트리밍

    **Master Agent가 여러 서브 에이전트를 조율하는 과정을 시각화**

    **응답 형식: Server-Sent Events (SSE)**

    **이벤트 타입:**
    - `master_start`: Master Agent 시작
    - `master_routing`: 어떤 에이전트들을 호출할지 결정
    - `agent_start`: 서브 에이전트 시작
    - `agent_node`: 에이전트 내부 노드 실행 상태
    - `agent_llm_start`: LLM 호출 시작
    - `agent_llm_end`: LLM 호출 완료
    - `agent_complete`: 서브 에이전트 완료
    - `master_aggregating`: Master가 결과 집계 중
    - `master_complete`: 전체 완료
    - `error`: 에러 발생
    - `done`: 스트리밍 종료

    **Frontend 사용 예시 (React):**
    ```javascript
    const [agentStatus, setAgentStatus] = useState({});

    const eventSource = new EventSource('/api/v1/chat/multi-stream', {
        method: 'POST',
        body: JSON.stringify({
            message: '삼성전자 분석해줘',
            user_id: 'user123'
        })
    });

    eventSource.addEventListener('master_routing', (event) => {
        const data = JSON.parse(event.data);
        console.log('호출할 에이전트:', data.agents);
        // UI에 표시: Research, Strategy, Risk 에이전트 활성화
    });

    eventSource.addEventListener('agent_start', (event) => {
        const data = JSON.parse(event.data);
        setAgentStatus(prev => ({
            ...prev,
            [data.agent]: 'running'
        }));
        // UI: Research Agent 카드에 "실행 중" 표시
    });

    eventSource.addEventListener('agent_node', (event) => {
        const data = JSON.parse(event.data);
        console.log(`${data.agent} - ${data.node}: ${data.status}`);
        // UI: "데이터 수집 중...", "Bull 분석 중..." 등 표시
    });

    eventSource.addEventListener('agent_complete', (event) => {
        const data = JSON.parse(event.data);
        setAgentStatus(prev => ({
            ...prev,
            [data.agent]: 'complete'
        }));
        console.log('결과:', data.result);
        // UI: Research Agent 카드에 "완료" + 결과 요약 표시
    });

    eventSource.addEventListener('master_complete', (event) => {
        const data = JSON.parse(event.data);
        console.log('최종 답변:', data.message);
        // UI: 최종 답변 표시
    });

    eventSource.addEventListener('done', (event) => {
        eventSource.close();
    });
    ```

    **Frontend UI 예시:**
    ```
    [Master Agent]
    ├─ 📊 Research Agent ✅
    │   ├─ planner ✅
    │   ├─ data_worker ✅
    │   ├─ bull_worker ✅
    │   ├─ bear_worker ✅
    │   ├─ insight_worker ✅
    │   └─ synthesis ✅
    │   결과: SELL, 목표가 90,000원
    │
    ├─ 🎯 Strategy Agent ✅
    │   └─ 전략: MOMENTUM
    │
    └─ ⚠️ Risk Agent ✅
        └─ 리스크: MEDIUM

    최종 답변: 현재 삼성전자는 SELL 추천입니다...
    ```
    """
    user_id = request.user_id or str(uuid.uuid4())
    conversation_id = request.conversation_id or str(uuid.uuid4())

    return StreamingResponse(
        stream_multi_agent_execution(
            message=request.message,
            user_id=user_id,
            conversation_id=conversation_id,
            automation_level=request.automation_level
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
