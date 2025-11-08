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
        if research.get("summary"):
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

        # 2.5. 대화 세션 초기화 및 사용자 메시지 저장
        conversation_uuid = uuid.UUID(conversation_id)
        demo_user_uuid = settings.demo_user_uuid

        await chat_history_service.upsert_session(
            conversation_id=conversation_uuid,
            user_id=demo_user_uuid,
            automation_level=automation_level,
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
        except Exception as e:
            logger.warning(f"⚠️ [MultiAgentStream] 대화 히스토리 로드 실패: {e}")

        # 3. Router 판단 (어떤 에이전트를 호출할지)
        routing_decision = await route_query(
            query=message,
            user_profile=user_profile,
            conversation_history=conversation_history
        )

        agents_to_call = list(dict.fromkeys(routing_decision.agents_to_call))

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

                # 워커 결과 메시지 추출
                worker_message = worker_result.get("message", "데이터를 가져왔습니다.") if worker_result else "데이터를 가져오는 중 오류가 발생했습니다."

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

                # SSE 이벤트 전송
                yield f"event: worker_start\ndata: {json.dumps({'worker': routing_decision.worker_action, 'params': routing_decision.worker_params}, ensure_ascii=False)}\n\n"
                yield f"event: worker_complete\ndata: {json.dumps({'worker': routing_decision.worker_action, 'result': worker_result}, ensure_ascii=False)}\n\n"
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
            # Router가 종목을 추출했으면 사용, 아니면 fallback
            if stock_names:
                stock_name = stock_names[0]  # 첫 번째 종목 사용
                # 종목명으로 코드 검색
                for market in ("KOSPI", "KOSDAQ", "KONEX"):
                    code = await stock_data_service.get_stock_by_name(stock_name, market=market)
                    if code:
                        resolved_stock_code = code
                        logger.info(f"✅ [ResolveStock] 종목 코드 찾기 성공: {stock_name} -> {code}")
                        break

            # Fallback: Router가 종목을 못 찾았거나 코드 변환 실패
            if not resolved_stock_code:
                resolved_stock_code = await resolve_stock_code(message)

            if not resolved_stock_code:
                # trading이면 매매 관련 메시지, 아니면 분석 관련 메시지
                if "trading" in agents_to_call:
                    clarification_message = (
                        "어떤 종목을 매매하시겠습니까? "
                        "종목명이나 티커(예: 086790)를 알려주세요."
                    )
                else:
                    clarification_message = (
                        "어떤 종목을 장기 투자 관점에서 보고 싶으신가요? "
                        "종목명이나 티커(예: 128940)를 알려주시면 분석을 도와드릴게요."
                    )
                # Supervisor가 직접 처리하도록 agents_to_call 비움
                agents_to_call = []

        yield f"event: master_routing\ndata: {json.dumps({'agents': agents_to_call, 'depth_level': routing_decision.depth_level, 'stock_names': stock_names}, ensure_ascii=False)}\n\n"

        # 4. 각 에이전트 실행
        agent_results = {}

        for agent_name in agents_to_call:
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
                    elif event_type == "on_chat_model_start":
                        model = event.get("name", "LLM")
                        yield f"event: agent_llm_start\ndata: {json.dumps({'agent': agent_name, 'model': model, 'message': 'AI 분석 중...'}, ensure_ascii=False)}\n\n"
                    # elif event_type == "on_chat_model_stream":
                    #     ...
                    elif event_type == "on_chat_model_end":
                        yield f"event: agent_llm_end\ndata: {json.dumps({'agent': agent_name, 'message': 'AI 분석 완료'}, ensure_ascii=False)}\n\n"

                final_result = await agent.ainvoke(input_state)
                agent_results[agent_name] = final_result

                consensus = final_result.get("consensus", {})
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

                if not resolved_stock_code:
                    raise ValueError("매매를 위한 종목 코드를 추출하지 못했습니다.")

                # 원문(query)을 그대로 Trading Agent에 전달
                # Trading Agent 내부에서 LLM으로 매수/매도, 수량 분석
                input_state = {
                    "messages": [HumanMessage(content=message)],
                    "stock_code": resolved_stock_code,
                    "user_id": user_id,
                    "portfolio_id": None,  # 기본 포트폴리오 사용
                    "automation_level": automation_level,
                    "query": message,
                    # order_type, quantity는 Trading Agent에서 LLM으로 추출
                }

                yield f"event: agent_node\ndata: {json.dumps({'agent': agent_name, 'node': 'prepare_trade', 'status': 'running', 'message': '주문 분석 중...'}, ensure_ascii=False)}\n\n"

                try:
                    # 모든 automation level에서 Trading 서브그래프 사용
                    agent = build_trading_subgraph().compile()

                    # automation_level에 따라 처리 방식 분기
                    if automation_level == 1:
                        # Pilot 모드: Trading 서브그래프 완전 실행 (자동 승인)
                        result = await agent.ainvoke(input_state)

                        trade_result = result.get("trade_result", {})
                        agent_results[agent_name] = result

                        order_type = result.get("order_type", "BUY")
                        quantity = result.get("quantity", 0)

                        if result.get("trade_executed"):
                            summary = f"{order_type} {quantity}주 주문이 실행되었습니다. (KIS 주문번호: {trade_result.get('kis_order_no', 'N/A')})"
                            yield f"event: agent_complete\ndata: {json.dumps({'agent': agent_name, 'result': {'summary': summary, 'order_id': trade_result.get('order_id'), 'status': 'executed', 'kis_executed': True}}, ensure_ascii=False)}\n\n"
                        else:
                            error_msg = result.get("error", "실행 실패")
                            yield f"event: agent_complete\ndata: {json.dumps({'agent': agent_name, 'result': {'error': error_msg}}, ensure_ascii=False)}\n\n"

                    else:
                        # Copilot/Advisor 모드: prepare_trade까지만 실행 (주문 생성만)
                        # Trading 서브그래프의 prepare_trade 노드만 실행
                        from src.agents.trading.nodes import prepare_trade_node

                        # prepare_trade_node 실행하여 order_type, quantity 추출
                        prepare_result = await prepare_trade_node(input_state)

                        if prepare_result.get("error"):
                            error_msg = prepare_result.get("error")

                            # 조회 요청인 경우 Portfolio Agent로 fallback
                            if prepare_result.get("is_query_only"):
                                logger.info(f"⏭️ [Trading] 조회 요청 감지 - Portfolio Agent로 전환")

                                # Portfolio Agent 실행
                                from src.agents.portfolio.graph import build_portfolio_subgraph
                                portfolio_agent = build_portfolio_subgraph().compile()

                                # Portfolio Agent가 query를 스스로 분석 (ReAct 패턴)
                                portfolio_input = {
                                    "messages": [HumanMessage(content=message)],
                                    "user_id": user_id,
                                    "portfolio_id": None,
                                    "automation_level": automation_level,
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

                # Portfolio Agent가 query를 스스로 분석 (ReAct 패턴)
                input_state = {
                    "messages": [HumanMessage(content=message)],
                    "user_id": user_id,
                    "portfolio_id": None,  # 기본 포트폴리오 사용
                    "automation_level": automation_level,
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
            yield f"event: master_complete\ndata: {json.dumps({'message': final_response, 'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"
            yield f"event: done\ndata: {json.dumps({'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"
            logger.info("✅ [MultiAgentStream] 종목명 요청으로 응답 종료")
            return

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

        # 최종 답변 로그 출력 (디버깅용)
        logger.info("📝 [MultiAgentStream] 최종 답변: %s", final_response[:200] if len(final_response) > 200 else final_response)

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
            automation_level=request.automation_level
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
