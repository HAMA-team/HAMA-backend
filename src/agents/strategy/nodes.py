"""
Strategy Agent 노드 함수들

Langgraph 서브그래프 노드 구현
ReAct 패턴: Intent Classifier → Planner → Task Router → Specialists → Synthesis
"""
from .state import StrategyState
from src.schemas.strategy import InvestmentStyle
from langchain_core.messages import AIMessage
from typing import Literal
import logging

logger = logging.getLogger(__name__)


# ==================== ReAct Pattern Nodes ====================

async def query_intent_classifier_node(state: StrategyState) -> StrategyState:
    """
    Query Intent Classifier (쿼리 의도 분석기) - LLM 완전 판단 기반

    사용자 쿼리를 분석하여 필요한 전략 분석 범위를 결정합니다.
    """
    query = state.get("query", "")
    user_profile = state.get("user_profile") or {}

    logger.info("🎯 [Strategy/IntentClassifier] 쿼리 의도 분석 시작: %s", query[:50])

    # UserProfile 추출
    expertise_level = user_profile.get("expertise_level", "intermediate")

    # Claude 4.x 프롬프트 사용
    from src.prompts.common.intent_classifier import build_strategy_intent_classifier_prompt
    from src.utils.llm_factory import get_default_agent_llm as get_llm

    try:
        llm = get_llm(temperature=0, max_tokens=1000)

        # Claude 4.x 최적화 프롬프트 생성
        prompt = build_strategy_intent_classifier_prompt(
            query=query,
            user_profile={"expertise_level": expertise_level},
        )

        # LLM 호출
        response = await llm.ainvoke(prompt)

        # JSON 파싱
        from src.prompts import parse_llm_json

        intent = parse_llm_json(response.content)

        # 결과 추출
        final_depth = intent.get("depth", "standard")
        focus_areas = intent.get("focus_areas", [])
        specialists = intent.get("specialists", [])
        reasoning = intent.get("reasoning", "LLM 기반 분류")

        logger.info(
            "✅ [Strategy/IntentClassifier] LLM 판단 완료: %s | 집중 영역: %s | Specialists: %s",
            final_depth,
            focus_areas,
            specialists,
        )

        depth_reason = reasoning

    except Exception as exc:
        logger.warning("⚠️ [Strategy/IntentClassifier] LLM 분류 실패, fallback 사용: %s", exc)

        # Fallback: 기본값
        final_depth = "standard"
        focus_areas = ["full_strategy"]
        specialists = ["market_specialist", "sector_specialist", "asset_specialist"]
        depth_reason = "기본 전략 분석"

    logger.info(
        "📋 [Strategy/IntentClassifier] 최종 결정: %s | Specialists: %s",
        final_depth,
        specialists,
    )

    message = AIMessage(
        content=(
            f"전략 분석 범위: {final_depth}\n"
            f"이유: {depth_reason}\n"
            f"실행 Specialists: {', '.join(specialists)}"
        )
    )

    return {
        "analysis_depth": final_depth,
        "focus_areas": focus_areas,
        "depth_reason": depth_reason,
        "messages": [message],
    }


async def planner_node(state: StrategyState) -> StrategyState:
    """
    Smart Planner - 분석 깊이에 따라 동적으로 Specialist 선택

    Intent Classifier가 결정한 analysis_depth와 focus_areas를 기반으로
    필요한 Specialist만 선택하여 비용과 시간을 최적화합니다.
    """
    query = state.get("query", "")
    analysis_depth = state.get("analysis_depth", "standard")
    focus_areas = state.get("focus_areas") or []
    depth_reason = state.get("depth_reason", "")

    logger.info(
        "🧠 [Strategy/Planner] Smart Planner 시작 | 깊이: %s | 집중 영역: %s",
        analysis_depth,
        focus_areas,
    )

    # Claude 4.x 프롬프트 사용
    from src.prompts.common.planner import build_strategy_planner_prompt
    from src.utils.llm_factory import get_default_agent_llm as get_llm

    try:
        llm = get_llm(temperature=0, max_tokens=1000)

        # Planner 프롬프트 생성
        prompt = build_strategy_planner_prompt(
            query=query,
            analysis_depth=analysis_depth,
            focus_areas=focus_areas,
        )

        # LLM 호출
        response = await llm.ainvoke(prompt)

        # JSON 파싱
        from src.prompts import parse_llm_json

        plan = parse_llm_json(response.content)

        # 결과 추출
        specialists = plan.get("specialists", [])
        execution_order = plan.get("execution_order", "sequential")
        reasoning = plan.get("reasoning", "")
        estimated_time = plan.get("estimated_time", "30")

        logger.info(
            "✅ [Strategy/Planner] 계획 수립 완료: %s개 Specialist | 실행 방식: %s | 예상 시간: %s초",
            len(specialists),
            execution_order,
            estimated_time,
        )

    except Exception as exc:
        logger.warning("⚠️ [Strategy/Planner] 계획 수립 실패, fallback 사용: %s", exc)

        # Fallback: 기본 Specialist 선택
        if "buy_decision" in focus_areas:
            specialists = ["buy_specialist", "risk_reward_specialist"]
        elif "sell_decision" in focus_areas:
            specialists = ["sell_specialist"]
        elif "full_strategy" in focus_areas:
            specialists = ["market_specialist", "sector_specialist", "asset_specialist"]
        else:
            specialists = ["market_specialist", "sector_specialist"]

        execution_order = "sequential"
        reasoning = "Fallback 기본 계획"

    # pending_tasks 생성
    pending_tasks = [
        {
            "id": f"task_{i}",
            "specialist": specialist,
            "status": "pending",
            "description": f"{specialist} 실행",
        }
        for i, specialist in enumerate(specialists)
    ]

    logger.info("📋 [Strategy/Planner] %s개 작업 생성: %s", len(pending_tasks), specialists)

    message = AIMessage(
        content=f"전략 분석 계획: {len(specialists)}개 Specialist 실행 ({execution_order})\n이유: {reasoning}"
    )

    return {
        "pending_tasks": pending_tasks,
        "completed_tasks": [],
        "task_notes": [f"계획 수립: {len(specialists)}개 Specialist"],
        "messages": [message],
    }


async def task_router_node(state: StrategyState) -> StrategyState:
    """
    Task Router - 다음 작업 선택

    pending_tasks에서 다음 작업을 가져와 current_task로 설정합니다.
    """
    pending_tasks = list(state.get("pending_tasks") or [])

    if not pending_tasks:
        logger.info("✅ [Strategy/TaskRouter] 모든 작업 완료, synthesis로 이동")
        return {"current_task": None}

    # 다음 작업 선택
    current_task = pending_tasks.pop(0)
    specialist = current_task.get("specialist")

    logger.info("🔀 [Strategy/TaskRouter] 다음 작업 선택: %s", specialist)

    return {
        "current_task": current_task,
        "pending_tasks": pending_tasks,
    }


# ==================== Market Analysis Node ====================

async def market_analysis_node(state: StrategyState) -> StrategyState:
    """
    1단계: 시장 사이클 분석

    LLM 기반 거시경제 분석
    """
    logger.info(f"📈 [Strategy/Market] 시장 분석 시작")

    try:
        # market_analyzer 사용
        from src.agents.strategy.market_analyzer import market_analyzer

        market_outlook = await market_analyzer.analyze()

        logger.info(f"✅ [Strategy/Market] 시장 분석 완료: {market_outlook.cycle}")

        # Supervisor 호환성: messages 전파
        messages = list(state.get("messages", []))

        return {
            "market_outlook": {
                "cycle": market_outlook.cycle,
                "confidence": market_outlook.confidence,
                "summary": market_outlook.summary,
            },
            "messages": messages,
        }

    except Exception as e:
        logger.error(f"❌ [Strategy/Market] 에러: {e}")

        # 에러 시에도 messages 전파
        messages = list(state.get("messages", []))

        return {
            "error": f"시장 분석 실패: {str(e)}",
            "messages": messages,
        }


# ==================== Sector Rotation Node ====================

async def sector_rotation_node(state: StrategyState) -> StrategyState:
    """
    2단계: 섹터 전략 수립

    시장 사이클에 따른 섹터 로테이션
    """
    if state.get("error"):
        # 에러 시에도 messages 전파
        messages = list(state.get("messages", []))
        return {**state, "messages": messages}

    logger.info(f"🔄 [Strategy/Sector] 섹터 전략 수립 시작")

    try:
        from src.agents.strategy.sector_rotator import sector_rotator

        market_outlook = state.get("market_outlook", {})
        market_cycle = market_outlook.get("cycle", "expansion")
        user_preferences = state.get("user_preferences", {})

        sector_strategy = await sector_rotator.create_strategy(
            market_cycle=market_cycle,
            user_preferences=user_preferences
        )

        logger.info(f"✅ [Strategy/Sector] 섹터 전략 완료: {', '.join(sector_strategy.overweight[:2])}")

        # Supervisor 호환성: messages 전파
        messages = list(state.get("messages", []))

        return {
            "sector_strategy": {
                "overweight": sector_strategy.overweight,
                "underweight": sector_strategy.underweight,
                "rationale": sector_strategy.rationale,
                "sectors": [w.model_dump() for w in sector_strategy.sectors],
            },
            "messages": messages,
        }

    except Exception as e:
        logger.error(f"❌ [Strategy/Sector] 에러: {e}")

        # 에러 시에도 messages 전파
        messages = list(state.get("messages", []))

        return {
            "error": f"섹터 전략 수립 실패: {str(e)}",
            "messages": messages,
        }


# ==================== Asset Allocation Node ====================

async def asset_allocation_node(state: StrategyState) -> StrategyState:
    """
    3단계: 자산 배분 결정

    리스크 허용도에 따른 자산 배분
    """
    if state.get("error"):
        # 에러 시에도 messages 전파
        messages = list(state.get("messages", []))
        return {**state, "messages": messages}

    logger.info(f"💰 [Strategy/Asset] 자산 배분 결정 시작")

    try:
        from src.agents.strategy.risk_stance import risk_stance_analyzer

        market_outlook = state.get("market_outlook", {})
        market_cycle = market_outlook.get("cycle", "expansion")
        risk_tolerance = state.get("risk_tolerance", "moderate")

        asset_allocation = await risk_stance_analyzer.determine_allocation(
            market_cycle=market_cycle,
            risk_tolerance=risk_tolerance
        )

        logger.info(f"✅ [Strategy/Asset] 자산 배분 완료: 주식 {asset_allocation.stocks:.0%}")

        # Supervisor 호환성: messages 전파
        messages = list(state.get("messages", []))

        return {
            "asset_allocation": {
                "stocks": float(asset_allocation.stocks),
                "cash": float(asset_allocation.cash),
                "rationale": asset_allocation.rationale,
            },
            "messages": messages,
        }

    except Exception as e:
        logger.error(f"❌ [Strategy/Asset] 에러: {e}")

        # 에러 시에도 messages 전파
        messages = list(state.get("messages", []))

        return {
            "error": f"자산 배분 실패: {str(e)}",
            "messages": messages,
        }


# ==================== Buy Specialist Node ====================

async def buy_specialist_node(state: StrategyState) -> StrategyState:
    """
    매수 점수 산정 Specialist

    1-10점 스케일로 매수 매력도 평가
    """
    logger.info("💰 [Strategy/BuySpecialist] 매수 점수 산정 시작")

    try:
        from src.prompts.strategy.specialists import build_buy_specialist_prompt
        from src.utils.llm_factory import get_default_agent_llm as get_llm

        query = state.get("query", "")
        market_outlook = state.get("market_outlook")
        sector_strategy = state.get("sector_strategy")

        # 프롬프트 생성
        prompt = build_buy_specialist_prompt(
            query=query,
            market_outlook=market_outlook,
            sector_strategy=sector_strategy,
        )

        # LLM 호출
        llm = get_llm(temperature=0, max_tokens=1500)
        response = await llm.ainvoke(prompt)

        # JSON 파싱
        from src.prompts import parse_llm_json
        result = parse_llm_json(response.content)

        buy_score = result.get("buy_score", 5)
        score_reason = result.get("score_reason", "분석 결과")

        logger.info(
            "✅ [Strategy/BuySpecialist] 매수 점수 산정 완료: %s점 (%s)",
            buy_score,
            score_reason[:50],
        )

        # Supervisor 호환성: messages 전파
        messages = list(state.get("messages", []))
        messages.append(
            AIMessage(content=f"매수 점수: {buy_score}점\n이유: {score_reason}")
        )

        return {
            "buy_score": buy_score,
            "buy_analysis": result,
            "messages": messages,
        }

    except Exception as e:
        logger.error("❌ [Strategy/BuySpecialist] 에러: %s", e)

        # 에러 시에도 messages 전파
        messages = list(state.get("messages", []))
        error_msg = f"매수 점수 산정 실패: {str(e)}"
        messages.append(AIMessage(content=error_msg))

        return {
            "error": error_msg,
            "messages": messages,
        }


# ==================== Sell Specialist Node ====================

async def sell_specialist_node(state: StrategyState) -> StrategyState:
    """
    매도 판단 Specialist

    익절/손절/홀드 판단
    """
    logger.info("📤 [Strategy/SellSpecialist] 매도 판단 시작")

    try:
        from src.prompts.strategy.specialists import build_sell_specialist_prompt
        from src.utils.llm_factory import get_default_agent_llm as get_llm

        query = state.get("query", "")
        market_outlook = state.get("market_outlook")

        # 프롬프트 생성
        prompt = build_sell_specialist_prompt(
            query=query,
            market_outlook=market_outlook,
        )

        # LLM 호출
        llm = get_llm(temperature=0, max_tokens=1500)
        response = await llm.ainvoke(prompt)

        # JSON 파싱
        from src.prompts import parse_llm_json
        result = parse_llm_json(response.content)

        decision = result.get("decision", "홀드")
        decision_reason = result.get("decision_reason", "분석 결과")

        logger.info(
            "✅ [Strategy/SellSpecialist] 매도 판단 완료: %s (%s)",
            decision,
            decision_reason[:50],
        )

        # Supervisor 호환성: messages 전파
        messages = list(state.get("messages", []))
        messages.append(
            AIMessage(content=f"매도 판단: {decision}\n이유: {decision_reason}")
        )

        return {
            "sell_decision": result,
            "messages": messages,
        }

    except Exception as e:
        logger.error("❌ [Strategy/SellSpecialist] 에러: %s", e)

        # 에러 시에도 messages 전파
        messages = list(state.get("messages", []))
        error_msg = f"매도 판단 실패: {str(e)}"
        messages.append(AIMessage(content=error_msg))

        return {
            "error": error_msg,
            "messages": messages,
        }


# ==================== Risk/Reward Specialist Node ====================

async def risk_reward_specialist_node(state: StrategyState) -> StrategyState:
    """
    손절가/목표가 계산 Specialist

    Risk/Reward Ratio 기반 가격대 설정
    """
    logger.info("⚖️ [Strategy/RiskRewardSpecialist] 손절가/목표가 계산 시작")

    try:
        from src.prompts.strategy.specialists import build_risk_reward_specialist_prompt
        from src.utils.llm_factory import get_default_agent_llm as get_llm

        query = state.get("query", "")

        # 프롬프트 생성
        prompt = build_risk_reward_specialist_prompt(query=query)

        # LLM 호출
        llm = get_llm(temperature=0, max_tokens=1500)
        response = await llm.ainvoke(prompt)

        # JSON 파싱
        from src.prompts import parse_llm_json
        result = parse_llm_json(response.content)

        stop_loss_price = result.get("stop_loss_price", 0)
        target_price_1 = result.get("target_price_1", 0)
        risk_reward_ratio = result.get("risk_reward_ratio", "1:2")

        logger.info(
            "✅ [Strategy/RiskRewardSpecialist] 계산 완료: 손절가 %s원 | 목표가 %s원 | R:R %s",
            f"{stop_loss_price:,.0f}" if stop_loss_price else "N/A",
            f"{target_price_1:,.0f}" if target_price_1 else "N/A",
            risk_reward_ratio,
        )

        # Supervisor 호환성: messages 전파
        messages = list(state.get("messages", []))
        messages.append(
            AIMessage(
                content=f"손절가: {stop_loss_price:,.0f}원\n목표가: {target_price_1:,.0f}원\nR:R: {risk_reward_ratio}"
            )
        )

        return {
            "risk_reward": result,
            "messages": messages,
        }

    except Exception as e:
        logger.error("❌ [Strategy/RiskRewardSpecialist] 에러: %s", e)

        # 에러 시에도 messages 전파
        messages = list(state.get("messages", []))
        error_msg = f"손절가/목표가 계산 실패: {str(e)}"
        messages.append(AIMessage(content=error_msg))

        return {
            "error": error_msg,
            "messages": messages,
        }


# ==================== Blueprint Creation Node ====================

async def blueprint_creation_node(state: StrategyState) -> StrategyState:
    """
    Synthesis: Strategic Blueprint Dashboard 생성

    모든 분석을 통합하여 최종 Blueprint Dashboard 생성
    """
    if state.get("error"):
        # 에러 시에도 messages 전파
        messages = list(state.get("messages", []))
        return {**state, "messages": messages}

    logger.info("📋 [Strategy/Blueprint] Blueprint Dashboard 생성 시작")

    try:
        market_outlook = state.get("market_outlook", {})
        sector_strategy = state.get("sector_strategy", {})
        asset_allocation = state.get("asset_allocation", {})
        user_preferences = state.get("user_preferences", {})
        risk_tolerance = state.get("risk_tolerance", "moderate")

        # 투자 스타일 결정
        investment_style = {
            "type": user_preferences.get("style", "growth"),
            "horizon": user_preferences.get("horizon", "mid_term"),
            "approach": user_preferences.get("approach", "dollar_cost_averaging"),
            "size_preference": user_preferences.get("size", "large")
        }

        # 제약 조건
        constraints = {
            "max_stocks": 10,
            "max_per_stock": 0.20,
            "min_stocks": 5
        }

        # 신뢰도 및 주요 가정
        confidence_score = market_outlook.get("confidence", 0.75)
        key_assumptions = [
            f"{market_outlook.get('cycle', 'expansion')} 국면 지속",
            f"핵심 섹터: {', '.join(sector_strategy.get('overweight', [])[:2])}",
            f"주식 비중 {asset_allocation.get('stocks', 0.7):.0%}"
        ]

        # Blueprint 구성
        blueprint = {
            "market_outlook": market_outlook,
            "sector_strategy": sector_strategy,
            "asset_allocation": asset_allocation,
            "investment_style": investment_style,
            "risk_tolerance": risk_tolerance,
            "constraints": constraints,
            "confidence_score": confidence_score,
            "key_assumptions": key_assumptions,
        }

        # Dashboard 프롬프트 생성
        from src.prompts.templates.strategy_dashboard import build_strategy_dashboard_prompt

        dashboard_prompt = build_strategy_dashboard_prompt(
            market_outlook=market_outlook,
            sector_strategy=sector_strategy,
            asset_allocation=asset_allocation,
            investment_style=investment_style,
            risk_tolerance=risk_tolerance,
            constraints=constraints,
            confidence_score=confidence_score,
            key_assumptions=key_assumptions,
        )

        # LLM 호출하여 Dashboard 생성
        from src.utils.llm_factory import get_default_agent_llm as get_llm

        llm = get_llm(temperature=0.3, max_tokens=3000)
        dashboard_response = await llm.ainvoke(dashboard_prompt)
        dashboard_content = dashboard_response.content

        logger.info("✅ [Strategy/Blueprint] Blueprint Dashboard 생성 완료")

        # Supervisor 호환성을 위해 messages 포함
        messages = list(state.get("messages", []))
        messages.append(AIMessage(content=dashboard_content))

        # 간단한 요약도 생성
        summary = (
            f"{market_outlook.get('cycle', '확장')} 국면, "
            f"주식 {asset_allocation.get('stocks', 0):.0%}/현금 {asset_allocation.get('cash', 0):.0%}, "
            f"핵심 섹터: {', '.join(sector_strategy.get('overweight', [])[:2])}"
        )

        # MasterState(GraphState)로 결과 전달
        return {
            "blueprint": blueprint,  # StrategyState 내부용
            "agent_results": {  # MasterState 공유용
                "strategy": {
                    "summary": summary,
                    "dashboard": dashboard_content,
                    "market_cycle": market_outlook.get('cycle', 'expansion'),
                    "stock_ratio": asset_allocation.get('stocks', 0.7),
                    "confidence": confidence_score,
                }
            },
            "messages": messages,
        }

    except Exception as e:
        logger.error("❌ [Strategy/Blueprint] 에러: %s", e)

        # 에러 시에도 messages 포함
        messages = list(state.get("messages", []))
        error_msg = f"Blueprint 생성 실패: {str(e)}"
        messages.append(AIMessage(content=error_msg))

        return {
            "error": error_msg,
            "agent_results": {  # 에러도 MasterState에 전달
                "strategy": {"error": error_msg}
            },
            "messages": messages,
        }
