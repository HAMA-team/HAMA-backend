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

from src.agents.router import route_query
from src.services.stock_data_service import stock_data_service
from src.services.user_profile_service import user_profile_service
from src.services import chat_history_service
from src.models.database import get_db_context
from src.utils.stock_name_extractor import extract_stock_names_from_query
from src.utils.hitl_compat import automation_level_to_hitl_config
from src.config.settings import settings
from src.workers.market_data import get_stock_price, get_index_price

logger = logging.getLogger(__name__)

router = APIRouter()


async def resolve_stock_code(message: str) -> Optional[str]:
    """
    사용자 질의에서 종목 코드를 추출 (LLM 기반).

    Args:
        message: 사용자 질문

    Returns:
        종목 코드 (6자리) 또는 None
    """
    # 1. 6자리 코드가 직접 입력된 경우
    digit_match = re.search(r"\b(\d{6})\b", message)
    if digit_match:
        return digit_match.group(1)

    # 2. LLM으로 종목명 추출
    stock_names = await extract_stock_names_from_query(message)
    if not stock_names:
        return None

    # 3. 첫 번째 종목명으로 코드 검색
    stock_name = stock_names[0]
    for market in ("KOSPI", "KOSDAQ", "KONEX"):
        code = await stock_data_service.get_stock_by_name(stock_name, market=market)
        if code:
            logger.info(f"✅ [ResolveStock] 종목 코드 찾기 성공: {stock_name} -> {code}")
            return code

    logger.warning(f"⚠️ [ResolveStock] 종목 코드를 찾을 수 없음: {stock_name}")
    return None


class MultiAgentStreamRequest(BaseModel):
    """멀티 에이전트 스트리밍 요청"""
    message: str
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    automation_level: int = Field(default=2, ge=1, le=3)
    hitl_config: Optional[dict] = Field(default=None, description="HITL 설정 (automation_level보다 우선)")
    stream_thinking: bool = Field(default=True, description="LLM 사고 과정 실시간 스트리밍 활성화 (ChatGPT식)")


def _format_agent_results(agent_results: dict) -> str:
    """
    에이전트 결과를 읽을 수 있는 텍스트로 포맷팅

    Args:
        agent_results: 에이전트 실행 결과 딕셔너리

    Returns:
        포맷팅된 텍스트 응답
    """
    response_parts = []

    # Research Agent 결과
    if "research" in agent_results:
        research = agent_results["research"]
        # Research Agent는 messages 필드에 AIMessage로 대시보드를 반환
        if research.get("messages"):
            # 마지막 메시지의 content 추출
            last_message = research["messages"][-1]
            if hasattr(last_message, "content"):
                response_parts.append(last_message.content)
            elif isinstance(last_message, dict) and last_message.get("content"):
                response_parts.append(last_message["content"])
        # Fallback: summary 필드 확인
        elif research.get("summary"):
            response_parts.append("## 📊 종목 분석\n")
            response_parts.append(research["summary"])

    # Strategy Agent 결과
    if "strategy" in agent_results:
        strategy = agent_results["strategy"]
        if strategy.get("summary"):
            response_parts.append("\n\n## 📈 투자 전략\n")
            response_parts.append(strategy["summary"])

    # Risk Agent 결과
    if "risk" in agent_results:
        risk = agent_results["risk"]
        if risk.get("summary"):
            response_parts.append("\n\n## ⚠️ 리스크 분석\n")
            response_parts.append(risk["summary"])

    # Trading Agent 결과
    if "trading" in agent_results:
        trading = agent_results["trading"]
        if trading.get("summary"):
            response_parts.append("\n\n## 💼 매매 실행\n")
            response_parts.append(trading["summary"])

    if not response_parts:
        return "분석이 완료되었습니다."

    return "\n".join(response_parts)


async def stream_multi_agent_execution(
    message: str,
    user_id: str,
    conversation_id: str,
    automation_level: int,
    hitl_config_dict: Optional[dict] = None,
    stream_thinking: bool = True
) -> AsyncGenerator[str, None]:
    """
    멀티 에이전트 실행을 SSE로 스트리밍

    프론트엔드에서 받는 이벤트:
    - master_start: Master Agent 시작
    - master_routing: Router 판단 (어떤 에이전트들을 호출할지)
    - agent_start: 서브 에이전트 시작
    - agent_node: 에이전트 내부 노드 실행
    - agent_llm_start: LLM 호출 시작
    - agent_thinking: LLM 사고 과정 실시간 스트리밍 (stream_thinking=True 시)
    - agent_tool_call: Tool 호출 시작 (향후 대비)
    - agent_tool_result: Tool 실행 결과 (향후 대비)
    - agent_llm_end: LLM 호출 완료
    - agent_complete: 서브 에이전트 완료
    - master_aggregating: Master가 결과 집계 중
    - master_complete: 전체 완료
    - error: 에러 발생
    """

    try:
        # 0. HITL 설정 처리
        from src.schemas.hitl_config import HITLConfig

        if hitl_config_dict:
            hitl_config = HITLConfig(**hitl_config_dict)
            logger.info(f"🎛️  [MultiAgentStream] HITL Config: preset={hitl_config.preset}, phases={hitl_config.phases.model_dump()}")
        else:
            hitl_config = automation_level_to_hitl_config(automation_level)
            logger.info(f"🎛️  [MultiAgentStream] Fallback to automation_level {automation_level} -> preset={hitl_config.preset}")

        # 1. Master Agent 시작
        yield f"event: master_start\ndata: {json.dumps({'message': '분석을 시작합니다...'}, ensure_ascii=False)}\n\n"

        # 2. 사용자 프로파일 로드
        with get_db_context() as db:
            user_profile = user_profile_service.get_user_profile(user_id, db)

        yield f"event: user_profile\ndata: {json.dumps({'profile_loaded': True}, ensure_ascii=False)}\n\n"

        # 2.5. 대화 세션 초기화 및 사용자 메시지 저장
        conversation_uuid = uuid.UUID(conversation_id)
        demo_user_uuid = settings.demo_user_uuid

        # automation_level 제거됨: hitl_config로 완전 전환
        await chat_history_service.upsert_session(
            conversation_id=conversation_uuid,
            user_id=demo_user_uuid,
            metadata={"hitl_preset": automation_level_to_hitl_config(automation_level).preset},  # hitl_config 정보만 metadata에 저장
        )
        await chat_history_service.append_message(
            conversation_id=conversation_uuid,
            role="user",
            content=message,
        )

        # 2.6. 대화 히스토리 조회 (최근 5개 메시지)
        conversation_history = []
        try:
            history_data = await chat_history_service.get_history(
                conversation_id=conversation_uuid,
                limit=10  # 최근 10개 메시지 (user + assistant 쌍 5개)
            )
            if history_data and "messages" in history_data:
                # 최신 메시지 제외 (방금 저장한 user 메시지)
                messages = history_data["messages"][:-1]
                conversation_history = [
                    {"role": msg.role, "content": msg.content}
                    for msg in messages[-6:]  # 최근 3턴 (6개 메시지)
                ]
                logger.info(f"📜 [MultiAgentStream] 대화 히스토리 로드: {len(conversation_history)}개")
                # 디버깅: 대화 히스토리 내용 출력
                for i, msg in enumerate(conversation_history):
                    logger.info(f"  [{i}] {msg['role']}: {msg['content'][:100]}...")
        except Exception as e:
            logger.warning(f"⚠️ [MultiAgentStream] 대화 히스토리 로드 실패: {e}")

        # 3. Router 판단 (어떤 에이전트를 호출할지)
        logger.info(f"🧭 [Router] 쿼리 분석 시작: '{message}'")
        routing_decision = await route_query(
            query=message,
            user_profile=user_profile,
            conversation_history=conversation_history
        )

        # Router 판단 결과 상세 로깅
        logger.info("=" * 80)
        logger.info("🧭 [Router] 판단 결과:")
        logger.info(f"  - 복잡도: {routing_decision.query_complexity}")
        logger.info(f"  - 사용자 의도: {routing_decision.user_intent}")
        logger.info(f"  - 종목명: {routing_decision.stock_names}")
        logger.info(f"  - 호출할 에이전트: {routing_decision.agents_to_call}")
        logger.info(f"  - 워커 액션: {routing_decision.worker_action}")
        logger.info(f"  - 직접 답변: {routing_decision.direct_answer[:100] if routing_decision.direct_answer else None}")
        logger.info(f"  - 근거: {routing_decision.reasoning}")
        logger.info("=" * 80)

        agents_to_call = list(dict.fromkeys(routing_decision.agents_to_call))

        # 3.5. HITL 설정에 따라 에이전트 필터링
        original_agents = agents_to_call.copy()
        logger.info(f"🎛️  [HITL] 필터링 전 에이전트: {original_agents}")

        # Trading 에이전트는 별도 처리 (항상 실행, HITL은 내부에서 처리)
        trading_requested = "trading" in agents_to_call

        if not hitl_config.phases.data_collection:
            # data_collection이 false면 research 제거 (데이터 수집 에이전트)
            if "research" in agents_to_call:
                agents_to_call.remove("research")
                logger.info("🚫 [HITL] data_collection=False -> research agent 제거")

        if not hitl_config.phases.analysis:
            # analysis가 false면 strategy 제거 (전략 분석 에이전트)
            if "strategy" in agents_to_call:
                agents_to_call.remove("strategy")
                logger.info("🚫 [HITL] analysis=False -> strategy agent 제거")

        if not hitl_config.phases.risk:
            # risk가 false면 risk 제거
            if "risk" in agents_to_call:
                agents_to_call.remove("risk")
                logger.info("🚫 [HITL] risk=False -> risk agent 제거")

        # Trading 에이전트는 HITL 필터링에서 제외하고 다시 추가
        # (Trading Agent 내부에서 hitl_config.phases.trade를 직접 확인)
        if trading_requested and "trading" not in agents_to_call:
            agents_to_call.append("trading")
            logger.info("✅ [HITL] trading agent는 항상 실행 (HITL은 내부 처리)")

        # 필터링 결과 로그
        logger.info(f"🎛️  [HITL] 필터링 후 에이전트: {agents_to_call}")
        if original_agents != agents_to_call:
            logger.info(f"⚠️  [HITL] 에이전트가 필터링되었습니다: {set(original_agents) - set(agents_to_call)} 제거됨")
        else:
            logger.info(f"✅ [HITL] 에이전트 필터링 없음")

        # 워커 직접 호출 (단순 데이터 조회)
        if routing_decision.worker_action:
            logger.info(f"⚡ [MultiAgentStream] Worker 호출: {routing_decision.worker_action}")

            try:
                worker_result = None

                # stock_price 워커 호출
                if routing_decision.worker_action == "stock_price":
                    params = routing_decision.worker_params or {}
                    stock_code = params.get("stock_code")
                    stock_name = params.get("stock_name")

                    if not stock_code:
                        # stock_name으로 코드 검색
                        if stock_name:
                            for market in ("KOSPI", "KOSDAQ", "KONEX"):
                                code = await stock_data_service.get_stock_by_name(stock_name, market=market)
                                if code:
                                    stock_code = code
                                    break

                    if stock_code:
                        worker_result = await get_stock_price(stock_code, stock_name)
                    else:
                        worker_result = {
                            "error": "종목 코드를 찾을 수 없습니다.",
                            "message": f"죄송합니다. '{stock_name}' 종목을 찾을 수 없습니다."
                        }

                # index_price 워커 호출
                elif routing_decision.worker_action == "index_price":
                    params = routing_decision.worker_params or {}
                    index_name = params.get("index_name", "코스피")
                    worker_result = await get_index_price(index_name)

                # Worker 결과를 LLM으로 친근하게 변환
                worker_message_raw = worker_result.get("message", "데이터를 가져왔습니다.") if worker_result else "데이터를 가져오는 중 오류가 발생했습니다."

                # SSE 이벤트 전송 (WorkerParams를 dict로 변환)
                worker_params_dict = routing_decision.worker_params.model_dump() if routing_decision.worker_params else {}
                yield f"event: worker_start\ndata: {json.dumps({'worker': routing_decision.worker_action, 'params': worker_params_dict}, ensure_ascii=False)}\n\n"
                yield f"event: worker_complete\ndata: {json.dumps({'worker': routing_decision.worker_action, 'result': worker_result}, ensure_ascii=False)}\n\n"

                # LLM으로 답변 개선 (더 친근하고 맥락있게)
                yield f"event: agent_llm_start\ndata: {json.dumps({'agent': 'master', 'model': 'gpt-4o-mini', 'message': '답변을 생성하고 있습니다...'}, ensure_ascii=False)}\n\n"

                try:
                    from langchain_openai import ChatOpenAI
                    from langchain_core.prompts import ChatPromptTemplate

                    # 대화 히스토리 조회 (최근 1개 메시지만 - 맥락 파악용)
                    recent_context = ""
                    try:
                        history_data = await chat_history_service.get_history(
                            conversation_id=conversation_uuid,
                            limit=4  # 최근 2턴
                        )
                        if history_data and "messages" in history_data:
                            # 최신 메시지 제외 (방금 저장한 user 메시지)
                            messages = history_data["messages"][:-1]
                            if messages:
                                last_msg = messages[-1]
                                recent_context = f"[이전 답변] {last_msg.content[:150]}..."
                    except Exception as e:
                        logger.debug(f"대화 히스토리 조회 실패: {e}")

                    enhancer_llm = ChatOpenAI(
                        model="gpt-4o-mini",
                        temperature=0.7,
                        max_completion_tokens=300,
                        api_key=settings.OPENAI_API_KEY,
                    )

                    enhancer_prompt = ChatPromptTemplate.from_messages([
                        ("system", """당신은 투자 정보를 친근하고 이해하기 쉽게 전달하는 AI 어시스턴트입니다.

주어진 데이터를 바탕으로 사용자에게 자연스럽고 도움이 되는 답변을 생성하세요.

<guidelines>
1. **친근한 톤**: "~입니다", "~해요" 같은 부드러운 어투 사용
2. **맥락 제공**: 단순 숫자 나열이 아닌, 의미 있는 해석 포함
3. **간결함**: 핵심 정보를 명확히 전달 (3-4문장)
4. **추가 인사이트**: 가능하면 간단한 해석이나 조언 추가
</guidelines>

<data>
{worker_data}
</data>

{context_block}

위 데이터를 바탕으로 사용자에게 친근하고 유용한 답변을 생성하세요."""),
                        ("human", "사용자 질문: {query}")
                    ])

                    context_block = f"\n<recent_context>\n{recent_context}\n</recent_context>" if recent_context else ""

                    enhancer_chain = enhancer_prompt | enhancer_llm
                    enhanced_response = await enhancer_chain.ainvoke({
                        "query": message,
                        "worker_data": worker_message_raw,
                        "context_block": context_block
                    })

                    worker_message = enhanced_response.content

                except Exception as e:
                    logger.warning(f"⚠️ [MultiAgentStream] LLM 답변 개선 실패, 원본 사용: {e}")
                    worker_message = worker_message_raw

                yield f"event: agent_llm_end\ndata: {json.dumps({'agent': 'master', 'message': 'AI 분석 완료'}, ensure_ascii=False)}\n\n"

                # 최종 답변 로그 출력
                logger.info("=" * 80)
                logger.info("📝 [Worker] 최종 답변 (전체):")
                logger.info(worker_message)
                logger.info("=" * 80)

                # Assistant 메시지 저장
                await chat_history_service.append_message(
                    conversation_id=conversation_uuid,
                    role="assistant",
                    content=worker_message,
                    metadata={
                        "source": "worker",
                        "worker_action": routing_decision.worker_action,
                        "worker_result": worker_result,
                        "reasoning": routing_decision.reasoning
                    }
                )

                yield f"event: master_complete\ndata: {json.dumps({'message': worker_message, 'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"
                yield f"event: done\ndata: {json.dumps({'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"

                logger.info(f"✅ [MultiAgentStream] Worker 완료: {routing_decision.worker_action}")
                return

            except Exception as e:
                logger.error(f"❌ [MultiAgentStream] Worker 실행 실패: {e}")
                error_message = f"죄송합니다. 데이터를 가져오는 중 오류가 발생했습니다: {str(e)}"

                await chat_history_service.append_message(
                    conversation_id=conversation_uuid,
                    role="assistant",
                    content=error_message,
                    metadata={"source": "worker_error", "error": str(e)}
                )

                yield f"event: error\ndata: {json.dumps({'error': str(e), 'message': error_message}, ensure_ascii=False)}\n\n"
                yield f"event: done\ndata: {json.dumps({'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"
                return

        # Router가 직접 답변한 경우 바로 반환
        if routing_decision.direct_answer:
            logger.info("💬 [MultiAgentStream] Router 직접 답변 사용")

            # 최종 답변 로그 출력
            logger.info("=" * 80)
            logger.info("📝 [Router] 직접 답변 (전체):")
            logger.info(routing_decision.direct_answer)
            logger.info("=" * 80)

            # Assistant 메시지 저장
            await chat_history_service.append_message(
                conversation_id=conversation_uuid,
                role="assistant",
                content=routing_decision.direct_answer,
                metadata={"source": "router_direct", "reasoning": routing_decision.reasoning}
            )

            yield f"event: master_routing\ndata: {json.dumps({'agents': [], 'depth_level': routing_decision.depth_level, 'stock_names': None, 'direct_answer': True}, ensure_ascii=False)}\n\n"
            yield f"event: master_complete\ndata: {json.dumps({'message': routing_decision.direct_answer, 'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"
            yield f"event: done\ndata: {json.dumps({'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"
            logger.info("✅ [MultiAgentStream] Router 직접 답변으로 완료")
            return

        resolved_stock_code: Optional[str] = None
        clarification_message: Optional[str] = None

        # Router가 이미 종목명을 추출했는지 확인
        stock_names = routing_decision.stock_names
        logger.info(f"🧭 [Router] 추출된 종목명: {stock_names}")

        # research, trading 에이전트는 종목 코드가 필요 (portfolio는 불필요)
        if any(agent in agents_to_call for agent in ["research", "trading"]):
            logger.info(f"🔍 [StockCode] 종목 코드 추출 필요 (agents: {[a for a in agents_to_call if a in ['research', 'trading']]})")

            # Router가 종목을 추출했으면 사용, 아니면 fallback
            if stock_names:
                stock_name = stock_names[0]  # 첫 번째 종목 사용
                logger.info(f"🔍 [StockCode] Router가 추출한 종목명 사용: {stock_name}")

                # 종목명으로 코드 검색
                for market in ("KOSPI", "KOSDAQ", "KONEX"):
                    code = await stock_data_service.get_stock_by_name(stock_name, market=market)
                    if code:
                        resolved_stock_code = code
                        logger.info(f"✅ [StockCode] 종목 코드 찾기 성공: {stock_name} -> {code} ({market})")
                        break

                if not resolved_stock_code:
                    logger.warning(f"⚠️ [StockCode] Router가 추출한 종목명으로 코드를 찾지 못함: {stock_name}")

            # Fallback: Router가 종목을 못 찾았거나 코드 변환 실패
            if not resolved_stock_code:
                logger.info(f"🔍 [StockCode] Fallback: 직접 종목 코드 추출 시도")
                resolved_stock_code = await resolve_stock_code(message)
                if resolved_stock_code:
                    logger.info(f"✅ [StockCode] Fallback 성공: {resolved_stock_code}")
                else:
                    logger.warning(f"⚠️ [StockCode] Fallback 실패: 종목 코드를 추출하지 못함")

            if not resolved_stock_code:
                # trading이면 매매 관련 메시지, 아니면 분석 관련 메시지
                if "trading" in agents_to_call:
                    clarification_message = (
                        "어떤 종목을 매매하시겠습니까? "
                        "종목명이나 티커(예: 086790)를 알려주세요."
                    )
                    logger.warning(f"⚠️ [StockCode] 매매 요청이지만 종목 코드를 찾지 못함")
                else:
                    clarification_message = (
                        "어떤 종목을 장기 투자 관점에서 보고 싶으신가요? "
                        "종목명이나 티커(예: 128940)를 알려주시면 분석을 도와드릴게요."
                    )
                    logger.warning(f"⚠️ [StockCode] 분석 요청이지만 종목 코드를 찾지 못함")
                # Supervisor가 직접 처리하도록 agents_to_call 비움
                agents_to_call = []
                logger.info(f"🚫 [StockCode] 종목 코드 부재로 agents_to_call 초기화")
        else:
            logger.info(f"✅ [StockCode] 종목 코드 추출 불필요 (agents: {agents_to_call})")

        yield f"event: master_routing\ndata: {json.dumps({'agents': agents_to_call, 'depth_level': routing_decision.depth_level, 'stock_names': stock_names}, ensure_ascii=False)}\n\n"

        # 4. 각 에이전트 실행
        agent_results = {}

        logger.info("=" * 80)
        logger.info(f"🤖 [Agents] 실행할 에이전트 목록: {agents_to_call}")
        logger.info("=" * 80)

        for agent_name in agents_to_call:
            logger.info(f"▶️  [Agent/{agent_name.upper()}] 시작")
            yield f"event: agent_start\ndata: {json.dumps({'agent': agent_name, 'message': f'{agent_name.upper()} Agent 실행 중...'}, ensure_ascii=False)}\n\n"

            if agent_name == "research":
                from src.agents.research.graph import build_research_subgraph

                agent = build_research_subgraph()
                if not resolved_stock_code:
                    raise ValueError("질문에서 종목 코드를 추출하지 못했습니다.")

                input_state = {
                    "messages": [HumanMessage(content=message)],
                    "stock_code": resolved_stock_code,
                    "query": message,
                    "request_id": conversation_id,
                }

                node_count = 0
                async for event in agent.astream_events(input_state, version="v2"):
                    event_type = event["event"]

                    if event_type == "on_chain_start":
                        node_name = event.get("name", "")
                        if node_name and node_name != "LangGraph":
                            node_count += 1
                            yield f"event: agent_node\ndata: {json.dumps({'agent': agent_name, 'node': node_name, 'status': 'running', 'message': f'{node_name} 노드 실행 중...'}, ensure_ascii=False)}\n\n"
                    elif event_type == "on_chain_end":
                        node_name = event.get("name", "")
                        if node_name and node_name != "LangGraph":
                            yield f"event: agent_node\ndata: {json.dumps({'agent': agent_name, 'node': node_name, 'status': 'complete', 'message': f'{node_name} 완료'}, ensure_ascii=False)}\n\n"

                            # Pre-Trade Risk Briefing 노드 완료 시 상세 정보 스트리밍
                            if node_name == "risk_briefing":
                                try:
                                    # State에서 risk_analysis 추출
                                    event_data = event.get("data", {})
                                    output = event_data.get("output", {})
                                    risk_analysis = output.get("risk_analysis")

                                    if risk_analysis:
                                        # risk_briefing 이벤트 전송 (Frontend에서 특별 처리 가능)
                                        yield f"event: risk_briefing\ndata: {json.dumps({'agent': agent_name, 'risk_analysis': risk_analysis}, ensure_ascii=False)}\n\n"
                                        logger.info(f"🚨 [Risk Briefing] {agent_name} - Level: {risk_analysis.get('overall_risk_level')}, Action: {risk_analysis.get('recommended_action')}")
                                except Exception as exc:
                                    logger.warning(f"⚠️ [Risk Briefing] State 추출 실패: {exc}")
                    elif event_type == "on_chat_model_start":
                        model = event.get("name", "LLM")
                        yield f"event: agent_llm_start\ndata: {json.dumps({'agent': agent_name, 'model': model, 'message': 'AI 분석 중...'}, ensure_ascii=False)}\n\n"
                    elif event_type == "on_chat_model_stream":
                        # LLM 사고 과정 실시간 스트리밍 (stream_thinking=True 시)
                        if stream_thinking:
                            chunk = event.get("data", {}).get("chunk")
                            if chunk and hasattr(chunk, "content") and chunk.content:
                                yield f"event: agent_thinking\ndata: {json.dumps({'agent': agent_name, 'content': chunk.content}, ensure_ascii=False)}\n\n"
                    elif event_type == "on_tool_start":
                        # Tool 호출 추적 (향후 ReAct Agent 지원)
                        if stream_thinking:
                            tool_name = event.get("name", "")
                            tool_input = event.get("data", {}).get("input", {})
                            yield f"event: agent_tool_call\ndata: {json.dumps({'agent': agent_name, 'tool': tool_name, 'input': tool_input}, ensure_ascii=False)}\n\n"
                            logger.info(f"🔧 [Tool Call] {agent_name} - {tool_name}")
                    elif event_type == "on_tool_end":
                        # Tool 실행 결과 (향후 ReAct Agent 지원)
                        if stream_thinking:
                            tool_name = event.get("name", "")
                            tool_output = event.get("data", {}).get("output")
                            yield f"event: agent_tool_result\ndata: {json.dumps({'agent': agent_name, 'tool': tool_name, 'output': tool_output}, ensure_ascii=False)}\n\n"
                            logger.info(f"✅ [Tool Result] {agent_name} - {tool_name}")
                    elif event_type == "on_chat_model_end":
                        yield f"event: agent_llm_end\ndata: {json.dumps({'agent': agent_name, 'message': 'AI 분석 완료'}, ensure_ascii=False)}\n\n"

                final_result = await agent.ainvoke(input_state)
                agent_results[agent_name] = final_result

                consensus = final_result.get("consensus", {})
                logger.info(f"✅ [Agent/{agent_name.upper()}] 완료 - 추천: {consensus.get('recommendation')}, 목표가: {consensus.get('target_price')}, 신뢰도: {consensus.get('confidence')}")
                yield f"event: agent_complete\ndata: {json.dumps({'agent': agent_name, 'result': {'recommendation': consensus.get('recommendation'), 'target_price': consensus.get('target_price'), 'confidence': consensus.get('confidence')}}, ensure_ascii=False)}\n\n"

            elif agent_name == "strategy":
                yield f"event: agent_node\ndata: {json.dumps({'agent': agent_name, 'node': 'analyze_market', 'status': 'running'}, ensure_ascii=False)}\n\n"
                yield f"event: agent_node\ndata: {json.dumps({'agent': agent_name, 'node': 'generate_strategy', 'status': 'running'}, ensure_ascii=False)}\n\n"
                yield f"event: agent_complete\ndata: {json.dumps({'agent': agent_name, 'result': {'strategy': 'MOMENTUM', 'allocation': 0.3}}, ensure_ascii=False)}\n\n"

            elif agent_name == "risk":
                yield f"event: agent_node\ndata: {json.dumps({'agent': agent_name, 'node': 'calculate_risk', 'status': 'running'}, ensure_ascii=False)}\n\n"
                yield f"event: agent_complete\ndata: {json.dumps({'agent': agent_name, 'result': {'risk_level': 'MEDIUM', 'max_loss': 0.15}}, ensure_ascii=False)}\n\n"

            elif agent_name == "trading":
                # Trading Agent 실행
                from src.agents.trading.graph import build_trading_subgraph

                logger.info(f"💰 [Agent/TRADING] 매매 에이전트 시작")
                logger.info(f"  - 종목 코드: {resolved_stock_code}")
                logger.info(f"  - 쿼리: {message}")

                if not resolved_stock_code:
                    error_msg = "매매를 위한 종목 코드를 추출하지 못했습니다."
                    logger.error(f"❌ [Agent/TRADING] {error_msg}")
                    raise ValueError(error_msg)

                # automation_level을 hitl_config로 변환 (이미 위에서 했으므로 재사용)
                # hitl_config = automation_level_to_hitl_config(automation_level)

                logger.info(f"  - HITL 설정: preset={hitl_config.preset}, trade={hitl_config.phases.trade}")

                # 원문(query)을 그대로 Trading Agent에 전달
                # Trading Agent 내부에서 LLM으로 매수/매도, 수량 분석
                input_state = {
                    "messages": [HumanMessage(content=message)],
                    "stock_code": resolved_stock_code,
                    "user_id": user_id,
                    "portfolio_id": None,  # 기본 포트폴리오 사용
                    "hitl_config": hitl_config,  # hitl_config 사용
                    "automation_level": automation_level,  # 하위 호환성 유지 (추후 제거 예정)
                    "query": message,
                    # order_type, quantity는 Trading Agent에서 LLM으로 추출
                }

                yield f"event: agent_node\ndata: {json.dumps({'agent': agent_name, 'node': 'prepare_trade', 'status': 'running', 'message': '주문 분석 중...'}, ensure_ascii=False)}\n\n"

                try:
                    # 모든 automation level에서 Trading 서브그래프 사용
                    agent = build_trading_subgraph().compile()

                    # hitl_config의 trade 설정에 따라 처리 방식 분기
                    if hitl_config.phases.trade == "conditional" or hitl_config.phases.trade is False:
                        # Pilot 모드: Trading 서브그래프 완전 실행 (자동 승인)
                        logger.info(f"🚀 [Agent/TRADING] Pilot 모드 - 자동 실행")
                        result = await agent.ainvoke(input_state)

                        trade_result = result.get("trade_result", {})
                        agent_results[agent_name] = result

                        order_type = result.get("order_type", "BUY")
                        quantity = result.get("quantity", 0)

                        if result.get("trade_executed"):
                            summary = f"{order_type} {quantity}주 주문이 실행되었습니다. (KIS 주문번호: {trade_result.get('kis_order_no', 'N/A')})"
                            logger.info(f"✅ [Agent/TRADING] 주문 실행 완료: {summary}")
                            yield f"event: agent_complete\ndata: {json.dumps({'agent': agent_name, 'result': {'summary': summary, 'order_id': trade_result.get('order_id'), 'status': 'executed', 'kis_executed': True}}, ensure_ascii=False)}\n\n"
                        else:
                            error_msg = result.get("error", "실행 실패")
                            logger.error("=" * 80)
                            logger.error(f"❌ [Agent/TRADING] 주문 실행 실패!")
                            logger.error(f"  - error_msg: {error_msg}")
                            logger.error(f"  - result 전체: {result}")
                            logger.error("=" * 80)
                            yield f"event: agent_complete\ndata: {json.dumps({'agent': agent_name, 'result': {'error': error_msg}}, ensure_ascii=False)}\n\n"

                    else:
                        # Copilot/Advisor 모드: prepare_trade까지만 실행 (주문 생성만)
                        logger.info(f"⏸️  [Agent/TRADING] Copilot/Advisor 모드 - 승인 대기")

                        # Trading 서브그래프의 prepare_trade 노드만 실행
                        from src.agents.trading.nodes import prepare_trade_node

                        # prepare_trade_node 실행하여 order_type, quantity 추출
                        prepare_result = await prepare_trade_node(input_state)

                        if prepare_result.get("error"):
                            error_msg = prepare_result.get("error")
                            logger.error(f"❌ [Agent/TRADING] 주문 준비 실패: {error_msg}")

                            # 조회 요청인 경우 Portfolio Agent로 fallback
                            if prepare_result.get("is_query_only"):
                                logger.info(f"⏭️ [Trading] 조회 요청 감지 - Portfolio Agent로 전환")

                                # Portfolio Agent 실행
                                from src.agents.portfolio.graph import build_portfolio_subgraph
                                portfolio_agent = build_portfolio_subgraph().compile()

                                # automation_level을 hitl_config로 변환
                                hitl_config_fallback = automation_level_to_hitl_config(automation_level)

                                # Portfolio Agent가 query를 스스로 분석 (ReAct 패턴)
                                portfolio_input = {
                                    "messages": [HumanMessage(content=message)],
                                    "user_id": user_id,
                                    "portfolio_id": None,
                                    "hitl_config": hitl_config_fallback,  # hitl_config 사용
                                    "automation_level": automation_level,  # 하위 호환성 유지 (추후 제거 예정)
                                    "query": message,  # Portfolio Agent가 query 분석
                                    "view_only": True,
                                }

                                try:
                                    portfolio_result = await portfolio_agent.ainvoke(portfolio_input)
                                    agent_results["portfolio"] = portfolio_result

                                    summary = portfolio_result.get("summary", "포트폴리오 조회 완료")
                                    yield f"event: agent_complete\ndata: {json.dumps({'agent': 'portfolio', 'result': {'summary': summary}}, ensure_ascii=False)}\n\n"
                                    break
                                except Exception as e:
                                    logger.error(f"❌ [Portfolio] 에러: {e}")
                                    yield f"event: agent_complete\ndata: {json.dumps({'agent': agent_name, 'result': {'error': str(e)}}, ensure_ascii=False)}\n\n"
                                    continue
                            else:
                                # 일반 에러
                                logger.error(f"❌ [Trading] 주문 준비 실패: {error_msg}")
                                yield f"event: agent_complete\ndata: {json.dumps({'agent': agent_name, 'result': {'error': error_msg}}, ensure_ascii=False)}\n\n"
                                continue

                        order = prepare_result.get("trade_summary", {})
                        order_type = prepare_result.get("order_type", "BUY")
                        quantity = prepare_result.get("quantity", 0)

                        logger.info(f"✅ [Agent/TRADING] 주문 생성 완료: {order_type} {quantity}주")
                        logger.info(f"  - Order ID: {order.get('order_id')}")

                        # 포트폴리오 정보 조회 (비중, 보유 단가, 수익/손실 계산용)
                        current_weight = 0.0
                        expected_weight = 0.0
                        stock_name = ""
                        current_price = 0
                        average_price = 0  # 보유 단가
                        profit_loss = 0  # 수익/손실 금액
                        profit_loss_rate = 0  # 수익률

                        try:
                            from src.services import portfolio_service
                            from src.models.stock import Stock

                            # 종목명 조회
                            with get_db_context() as db:
                                stock = db.query(Stock).filter(Stock.stock_code == resolved_stock_code).first()
                                if stock:
                                    stock_name = stock.stock_name

                            # 현재가 조회
                            price_df = await stock_data_service.get_stock_price(resolved_stock_code, days=1)
                            if price_df is not None and not price_df.empty:
                                current_price = float(price_df["Close"].iloc[-1])

                            # 포트폴리오 스냅샷 조회
                            snapshot = await portfolio_service.get_portfolio_snapshot(
                                user_id=user_id,
                                portfolio_id=None
                            )
                            if snapshot and snapshot.portfolio_data:
                                holdings = snapshot.portfolio_data.get("holdings", [])
                                total_value = float(snapshot.portfolio_data.get("total_value", 0))

                                # 현재 비중 및 보유 단가 조회
                                for holding in holdings:
                                    if holding.get("stock_code") == resolved_stock_code:
                                        current_weight = float(holding.get("weight", 0))
                                        average_price = float(holding.get("average_price", 0))
                                        break

                                # 수익/손실 계산 (매도 시)
                                if order_type == "SELL" and average_price > 0:
                                    profit_loss = (current_price - average_price) * quantity
                                    profit_loss_rate = ((current_price - average_price) / average_price) * 100

                                # 예상 비중 계산
                                if total_value > 0 and current_price > 0:
                                    order_value = current_price * quantity
                                    if order_type == "BUY":
                                        new_total = total_value + order_value
                                        current_holding_value = total_value * current_weight
                                        expected_weight = (current_holding_value + order_value) / new_total
                                    else:  # SELL
                                        new_total = total_value - order_value
                                        current_holding_value = total_value * current_weight
                                        expected_weight = max(0, (current_holding_value - order_value) / new_total) if new_total > 0 else 0

                        except Exception as e:
                            logger.warning(f"⚠️ [Trading] 상세 정보 계산 실패: {e}")
                            import traceback
                            traceback.print_exc()

                        # agent_results에 상세 정보 저장 (Aggregator 전달용)
                        trading_result = {
                            'order': order,
                            'order_type': order_type,
                            'stock_code': resolved_stock_code,
                            'stock_name': stock_name or resolved_stock_code,
                            'quantity': quantity,
                            'price': current_price,
                            'total_amount': current_price * quantity,
                            'average_price': average_price,  # 보유 단가
                            'profit_loss': profit_loss,  # 수익/손실 금액
                            'profit_loss_rate': profit_loss_rate,  # 수익률 (%)
                            'current_weight': current_weight,
                            'expected_weight': expected_weight,
                            'status': 'pending',
                            'requires_approval': True,
                        }

                        agent_results[agent_name] = trading_result
                        summary = f"{order_type} {quantity}주 주문이 생성되었습니다. 승인이 필요합니다."
                        logger.info(f"✅ [Trading] Copilot 모드: {summary}")

                        # HITL 패널을 위한 상세 정보 포함 (프론트엔드 전달용)
                        result_data = {
                            'summary': summary,
                            'order_id': order.get('order_id'),
                            'status': 'pending',
                            'requires_approval': True,
                            # 프론트엔드 HITL 패널 필수 정보
                            'stock_code': resolved_stock_code,
                            'stock_name': stock_name or resolved_stock_code,
                            'action': order_type,
                            'quantity': quantity,
                            'price': current_price,
                            'total_amount': current_price * quantity,
                            'current_weight': round(current_weight * 100, 2),  # 퍼센트로 변환
                            'expected_weight': round(expected_weight * 100, 2),  # 퍼센트로 변환
                        }

                        yield f"event: agent_complete\ndata: {json.dumps({'agent': agent_name, 'result': result_data}, ensure_ascii=False)}\n\n"

                except Exception as e:
                    logger.error(f"❌ [Trading] 에러: {e}")
                    import traceback
                    traceback.print_exc()
                    yield f"event: agent_complete\ndata: {json.dumps({'agent': agent_name, 'result': {'error': str(e)}}, ensure_ascii=False)}\n\n"

            elif agent_name == "portfolio":
                # Portfolio Agent 실행
                from src.agents.portfolio.graph import build_portfolio_subgraph

                agent = build_portfolio_subgraph().compile()

                # automation_level을 hitl_config로 변환
                hitl_config = automation_level_to_hitl_config(automation_level)

                # Portfolio Agent가 query를 스스로 분석 (ReAct 패턴)
                input_state = {
                    "messages": [HumanMessage(content=message)],
                    "user_id": user_id,
                    "portfolio_id": None,  # 기본 포트폴리오 사용
                    "hitl_config": hitl_config,  # hitl_config 사용
                    "automation_level": automation_level,  # 하위 호환성 유지 (추후 제거 예정)
                    "query": message,  # Portfolio Agent가 query 분석
                    "view_only": True,  # 조회 전용 모드
                }

                try:
                    # 노드 실행 이벤트 스트리밍 + 최종 결과 캡처 (중복 실행 방지)
                    result = None
                    async for event in agent.astream_events(input_state, version="v2"):
                        event_type = event["event"]

                        if event_type == "on_chain_start":
                            node_name = event.get("name", "")
                            if node_name and node_name != "LangGraph":
                                yield f"event: agent_node\ndata: {json.dumps({'agent': agent_name, 'node': node_name, 'status': 'running', 'message': f'{node_name} 노드 실행 중...'}, ensure_ascii=False)}\n\n"
                        elif event_type == "on_chain_end":
                            node_name = event.get("name", "")
                            if node_name and node_name != "LangGraph":
                                yield f"event: agent_node\ndata: {json.dumps({'agent': agent_name, 'node': node_name, 'status': 'complete', 'message': f'{node_name} 완료'}, ensure_ascii=False)}\n\n"
                            # 최종 결과 캡처 (LangGraph의 마지막 on_chain_end)
                            if node_name == "LangGraph":
                                result = event.get("data", {}).get("output")
                        elif event_type == "on_chat_model_stream":
                            # LLM 사고 과정 실시간 스트리밍 (stream_thinking=True 시)
                            if stream_thinking:
                                chunk = event.get("data", {}).get("chunk")
                                if chunk and hasattr(chunk, "content") and chunk.content:
                                    yield f"event: agent_thinking\ndata: {json.dumps({'agent': agent_name, 'content': chunk.content}, ensure_ascii=False)}\n\n"
                        elif event_type == "on_tool_start":
                            # Tool 호출 추적 (Portfolio Agent는 ReAct 패턴 사용)
                            if stream_thinking:
                                tool_name = event.get("name", "")
                                tool_input = event.get("data", {}).get("input", {})
                                yield f"event: agent_tool_call\ndata: {json.dumps({'agent': agent_name, 'tool': tool_name, 'input': tool_input}, ensure_ascii=False)}\n\n"
                                logger.info(f"🔧 [Tool Call] {agent_name} - {tool_name}")
                        elif event_type == "on_tool_end":
                            # Tool 실행 결과
                            if stream_thinking:
                                tool_name = event.get("name", "")
                                tool_output = event.get("data", {}).get("output")
                                yield f"event: agent_tool_result\ndata: {json.dumps({'agent': agent_name, 'tool': tool_name, 'output': tool_output}, ensure_ascii=False)}\n\n"
                                logger.info(f"✅ [Tool Result] {agent_name} - {tool_name}")
                        elif event_type == "on_chat_model_start":
                            model = event.get("name", "LLM")
                            yield f"event: agent_llm_start\ndata: {json.dumps({'agent': agent_name, 'model': model, 'message': 'AI 분석 중...'}, ensure_ascii=False)}\n\n"
                        elif event_type == "on_chat_model_end":
                            yield f"event: agent_llm_end\ndata: {json.dumps({'agent': agent_name, 'message': 'AI 분석 완료'}, ensure_ascii=False)}\n\n"

                    # astream_events에서 결과를 못 얻은 경우 fallback (중복 실행 최소화)
                    if result is None:
                        logger.warning("⚠️ [Portfolio] astream_events에서 결과 미캡처, ainvoke로 재실행")
                        result = await agent.ainvoke(input_state)

                    agent_results[agent_name] = result

                    portfolio_report = result.get("portfolio_report", {})
                    summary = result.get("summary", "포트폴리오 분석 완료")

                    yield f"event: agent_complete\ndata: {json.dumps({'agent': agent_name, 'result': {'summary': summary, 'rebalancing_needed': portfolio_report.get('rebalancing_needed', False), 'expected_return': portfolio_report.get('expected_return'), 'trades_count': len(portfolio_report.get('trades_required', []))}}, ensure_ascii=False)}\n\n"

                except Exception as e:
                    logger.error(f"❌ [Portfolio] 에러: {e}")
                    import traceback
                    traceback.print_exc()

                    # 에러 시 안내 메시지
                    error_msg = str(e)
                    if "포트폴리오" in error_msg or "찾을 수 없습니다" in error_msg:
                        # 포트폴리오가 없는 경우 친절한 안내
                        friendly_msg = (
                            "📭 아직 포트폴리오가 없습니다.\n\n"
                            "포트폴리오를 만들려면:\n"
                            "1. 원하는 종목을 선택하세요\n"
                            "2. '삼성전자 10주 매수' 같은 명령으로 매수하세요\n"
                            "3. 포트폴리오가 자동으로 생성됩니다"
                        )
                        agent_results[agent_name] = {
                            "answer": friendly_msg,
                            "no_portfolio": True
                        }
                        yield f"event: agent_complete\ndata: {json.dumps({'agent': agent_name, 'result': {'answer': friendly_msg}}, ensure_ascii=False)}\n\n"
                    else:
                        agent_results[agent_name] = {
                            "error": error_msg
                        }
                        yield f"event: agent_complete\ndata: {json.dumps({'agent': agent_name, 'result': {'error': error_msg}}, ensure_ascii=False)}\n\n"

            else:
                logger.warning("⚠️ [MultiAgentStream] 지원되지 않는 에이전트 요청: %s", agent_name)
                yield f"event: agent_complete\ndata: {json.dumps({'agent': agent_name, 'result': {'warning': '지원되지 않는 에이전트입니다.'}}, ensure_ascii=False)}\n\n"

        if clarification_message:
            final_response = clarification_message
            logger.info("=" * 80)
            logger.info("📝 [Clarification] 종목명 확인 요청:")
            logger.info(final_response)
            logger.info("=" * 80)
            yield f"event: master_complete\ndata: {json.dumps({'message': final_response, 'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"
            yield f"event: done\ndata: {json.dumps({'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"
            logger.info("✅ [MultiAgentStream] 종목명 요청으로 응답 종료")
            return

        # 에이전트 실행 완료 요약
        logger.info("=" * 80)
        logger.info(f"🏁 [Agents] 실행 완료 - 총 {len(agent_results)}개 에이전트")
        for agent_name, result in agent_results.items():
            logger.info(f"  - {agent_name}: {type(result).__name__ if hasattr(result, '__name__') else 'dict'}")
        logger.info("=" * 80)

        # 5. Master가 결과 집계
        yield f"event: master_aggregating\ndata: {json.dumps({'message': '분석 결과를 종합하고 있습니다...'}, ensure_ascii=False)}\n\n"

        # 6. 최종 응답 생성
        # Portfolio Agent는 이미 완성된 답변을 가지고 있으므로 직접 사용
        if "portfolio" in agent_results and agent_results["portfolio"].get("summary"):
            final_response = agent_results["portfolio"]["summary"]
            logger.info("✅ [MultiAgentStream] Portfolio Agent 결과 직접 사용")
        else:
            # agent_results 직접 포맷팅
            final_response = _format_agent_results(agent_results)
            logger.info("✅ [MultiAgentStream] Agent 결과 직접 포맷팅")

        # 최종 답변 로그 출력 (전체 내용)
        logger.info("=" * 80)
        logger.info("📝 [MultiAgentStream] 최종 답변 (전체):")
        logger.info(final_response)
        logger.info("=" * 80)

        # 6.5. Assistant 메시지 저장
        await chat_history_service.append_message(
            conversation_id=conversation_uuid,
            role="assistant",
            content=final_response,
            metadata={"agents_called": agents_to_call, "agent_results": list(agent_results.keys())}
        )

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
            automation_level=request.automation_level,
            hitl_config_dict=request.hitl_config,  # hitl_config 전달
            stream_thinking=request.stream_thinking
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/sessions")
async def get_chat_sessions(
    limit: int = 20,
    offset: int = 0,
):
    """
    대화 세션 목록 조회

    Args:
        limit: 조회할 세션 수 (기본값: 20)
        offset: 건너뛸 세션 수 (기본값: 0)

    Returns:
        {
            "sessions": [
                {
                    "conversation_id": "uuid",
                    "title": "첫 메시지 내용",
                    "last_message": "마지막 메시지",
                    "created_at": "2025-01-09T10:00:00",
                    "updated_at": "2025-01-09T10:30:00",
                    "message_count": 10
                }
            ],
            "total": 100,
            "limit": 20,
            "offset": 0
        }
    """
    try:
        # Demo 사용자 UUID
        demo_user_uuid = settings.demo_user_uuid

        # 세션 목록 조회 (전체 조회 후 offset 적용)
        all_sessions = await chat_history_service.list_sessions(
            user_id=demo_user_uuid,
            limit=limit + offset  # offset만큼 더 가져옴
        )

        # offset 적용하여 슬라이싱
        sessions_slice = all_sessions[offset:offset + limit]

        # API 응답 형식으로 포맷팅
        formatted_sessions = []
        for session_data in sessions_slice:
            first_msg = session_data.get("first_user_message")
            last_msg = session_data.get("last_message")
            chat_session = session_data.get("session")

            formatted_sessions.append({
                "conversation_id": str(session_data["conversation_id"]),
                "title": first_msg.content[:50] if first_msg and first_msg.content else "새 대화",
                "last_message": last_msg.content[:100] if last_msg and last_msg.content else "",
                "created_at": chat_session.created_at.isoformat() if chat_session and hasattr(chat_session, "created_at") else None,
                "updated_at": chat_session.last_message_at.isoformat() if chat_session and hasattr(chat_session, "last_message_at") and chat_session.last_message_at else None,
                "message_count": session_data.get("message_count", 0)
            })

        return {
            "sessions": formatted_sessions,
            "total": len(all_sessions),
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        logger.error(f"❌ [ChatSessions] 세션 목록 조회 실패: {e}")
        import traceback
        traceback.print_exc()
        return {
            "sessions": [],
            "total": 0,
            "limit": limit,
            "offset": offset
        }


@router.get("/sessions/{conversation_id}")
async def get_chat_session(conversation_id: str):
    """
    특정 대화 세션의 메시지 조회

    Args:
        conversation_id: 대화 ID (UUID)

    Returns:
        {
            "conversation_id": "uuid",
            "messages": [
                {
                    "role": "user",
                    "content": "안녕하세요",
                    "created_at": "2025-01-09T10:00:00"
                },
                {
                    "role": "assistant",
                    "content": "안녕하세요! 무엇을 도와드릴까요?",
                    "created_at": "2025-01-09T10:00:05"
                }
            ]
        }
    """
    try:
        conversation_uuid = uuid.UUID(conversation_id)
        history = await chat_history_service.get_history(
            conversation_id=conversation_uuid,
            limit=100  # 최근 100개 메시지
        )

        if not history:
            return {
                "conversation_id": conversation_id,
                "messages": []
            }

        # 메시지 포맷팅
        messages = []
        for msg in history.get("messages", []):
            messages.append({
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat() if hasattr(msg, "created_at") else None
            })

        return {
            "conversation_id": conversation_id,
            "messages": messages
        }

    except ValueError:
        logger.error(f"❌ [ChatSession] 잘못된 UUID 형식: {conversation_id}")
        return {
            "conversation_id": conversation_id,
            "messages": [],
            "error": "Invalid conversation ID format"
        }
    except Exception as e:
        logger.error(f"❌ [ChatSession] 세션 조회 실패: {e}")
        return {
            "conversation_id": conversation_id,
            "messages": [],
            "error": str(e)
        }


@router.delete("/sessions/{conversation_id}")
async def delete_chat_session(conversation_id: str):
    """
    대화 세션 삭제

    Args:
        conversation_id: 대화 ID (UUID)

    Returns:
        {
            "success": true,
            "conversation_id": "uuid",
            "message": "세션이 삭제되었습니다."
        }
    """
    try:
        conversation_uuid = uuid.UUID(conversation_id)

        # 세션 삭제 (delete_history 사용)
        await chat_history_service.delete_history(conversation_id=conversation_uuid)

        return {
            "success": True,
            "conversation_id": conversation_id,
            "message": "세션이 삭제되었습니다."
        }

    except ValueError:
        logger.error(f"❌ [DeleteSession] 잘못된 UUID 형식: {conversation_id}")
        return {
            "success": False,
            "conversation_id": conversation_id,
            "error": "Invalid conversation ID format"
        }
    except Exception as e:
        logger.error(f"❌ [DeleteSession] 세션 삭제 실패: {e}")
        return {
            "success": False,
            "conversation_id": conversation_id,
            "error": str(e)
        }


class ApproveRequest(BaseModel):
    """승인 요청"""
    thread_id: str = Field(..., description="대화 스레드 ID (conversation_id)")
    decision: str = Field(..., description="승인 결정 (approved/rejected/modified)")
    modifications: Optional[dict] = Field(None, description="수정 내용 (decision=modified일 때)")


@router.post("/approve")
async def approve_trade(request: ApproveRequest):
    """
    매매 주문 승인 처리

    Args:
        request: 승인 요청 (thread_id, decision, modifications)

    Returns:
        {
            "status": "approved" | "rejected",
            "message": "처리 결과 메시지",
            "result": {...}  # 실행 결과 상세
        }
    """
    try:
        # 1. thread_id로 pending 주문 찾기
        from src.services import trading_service
        from src.models.database import get_db_context

        # thread_id는 실제로 conversation_id임
        # 최근 pending 주문을 찾는다
        with get_db_context() as db:
            from src.models.order import Order

            # conversation_id를 notes에서 찾거나, 가장 최근 pending 주문을 사용
            pending_order = (
                db.query(Order)
                .filter(Order.status == "pending")
                .filter(Order.notes.contains(request.thread_id))
                .order_by(Order.created_at.desc())
                .first()
            )

            # notes에서 못 찾으면 가장 최근 pending 주문 사용
            if not pending_order:
                pending_order = (
                    db.query(Order)
                    .filter(Order.status == "pending")
                    .order_by(Order.created_at.desc())
                    .first()
                )

            if not pending_order:
                return {
                    "status": "error",
                    "message": "대기 중인 주문을 찾을 수 없습니다.",
                    "thread_id": request.thread_id
                }

            order_id = str(pending_order.order_id)
            stock_code = pending_order.stock_code
            logger.info(f"✅ [Approve] Pending 주문 발견: {order_id} ({stock_code})")

        # 2. decision에 따라 처리
        if request.decision == "rejected":
            # 주문 취소
            logger.info(f"🚫 [Approve] 주문 거부: {order_id}")
            return {
                "status": "rejected",
                "message": "주문이 취소되었습니다.",
                "thread_id": request.thread_id,
                "order_id": order_id
            }

        elif request.decision == "approved" or request.decision == "modified":
            # 수정 사항 반영
            execution_price = None
            if request.modifications:
                # 가격 수정이 있으면 반영
                execution_price = request.modifications.get("price")
                logger.info(f"📝 [Approve] 수정 사항 반영: price={execution_price}")

            # 주문 실행
            logger.info(f"✅ [Approve] 주문 실행 시작: {order_id}")
            result = await trading_service.execute_order(
                order_id=order_id,
                execution_price=execution_price,
                automation_level=2  # Copilot 모드
            )

            if result.get("status") == "rejected":
                return {
                    "status": "error",
                    "message": f"주문 실행 실패: {result.get('error')}",
                    "thread_id": request.thread_id,
                    "result": result
                }

            # 성공
            order_type = result.get("order_type", "BUY")
            quantity = result.get("quantity", 0)
            price = result.get("price", 0)

            return {
                "status": "approved",
                "message": f"✅ {order_type} {quantity}주 @ {price:,.0f}원 주문이 실행되었습니다.",
                "thread_id": request.thread_id,
                "result": {
                    "order_id": result.get("order_id"),
                    "status": result.get("status"),
                    "kis_order_no": result.get("kis_order_no"),
                    "kis_executed": result.get("kis_executed", False),
                    "order_type": order_type,
                    "quantity": quantity,
                    "price": price,
                    "total": result.get("total", price * quantity)
                }
            }

        else:
            return {
                "status": "error",
                "message": f"알 수 없는 decision: {request.decision}",
                "thread_id": request.thread_id
            }

    except Exception as e:
        logger.error(f"❌ [Approve] 승인 처리 실패: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"승인 처리 중 오류 발생: {str(e)}",
            "thread_id": request.thread_id
        }
