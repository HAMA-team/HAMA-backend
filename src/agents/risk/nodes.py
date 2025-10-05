"""Risk Agent 노드 함수들."""
import logging
from decimal import Decimal

from langchain_core.messages import AIMessage

from src.agents.risk.state import RiskState

logger = logging.getLogger(__name__)


async def collect_portfolio_data_node(state: RiskState) -> dict:
    """
    1단계: 포트폴리오 데이터 수집

    TODO Phase 2:
    - DB에서 실제 포트폴리오 조회
    - 각 종목의 현재 가격 및 비중 계산
    """
    logger.info("📊 [Risk] 포트폴리오 데이터 수집 중...")

    # Mock 포트폴리오 데이터
    portfolio_data = {
        "total_value": 10000000,  # 1천만원
        "holdings": [
            {"stock_code": "005930", "stock_name": "삼성전자", "quantity": 50, "weight": 0.35},
            {"stock_code": "000660", "stock_name": "SK하이닉스", "quantity": 20, "weight": 0.20},
            {"stock_code": "035420", "stock_name": "NAVER", "quantity": 15, "weight": 0.15},
            {"stock_code": "005380", "stock_name": "현대차", "quantity": 30, "weight": 0.30},
        ],
        "sectors": {
            "IT/반도체": 0.55,
            "자동차": 0.30,
            "기타": 0.15,
        }
    }

    # Mock 시장 데이터
    market_data = {
        "kospi_volatility": 0.18,
        "beta": {
            "005930": 1.2,
            "000660": 1.5,
            "035420": 1.1,
            "005380": 0.9,
        }
    }

    logger.info(f"✅ [Risk] 포트폴리오 데이터 수집 완료: {len(portfolio_data['holdings'])}개 종목")

    return {
        "portfolio_data": portfolio_data,
        "market_data": market_data,
    }


async def concentration_check_node(state: RiskState) -> dict:
    """
    2단계: 집중도 리스크 체크

    - 개별 종목 집중도
    - 섹터 집중도
    - 경고 생성

    TODO Phase 2:
    - 실제 HHI (Herfindahl Index) 계산
    - 동적 임계값 설정
    """
    portfolio = state.get("portfolio_data", {})
    holdings = portfolio.get("holdings", [])
    sectors = portfolio.get("sectors", {})

    warnings = []

    # 개별 종목 집중도 체크
    for holding in holdings:
        weight = holding["weight"]
        if weight > 0.30:  # 30% 초과
            warnings.append(
                f"{holding['stock_name']} 비중 {weight:.0%}로 높음 (권장: 25% 이하)"
            )

    # 섹터 집중도 체크
    for sector, weight in sectors.items():
        if weight > 0.50:  # 50% 초과
            warnings.append(
                f"{sector} 섹터 집중도 {weight:.0%} 초과 (권장: 50% 이하)"
            )

    # 집중도 점수 계산 (HHI 간소화)
    hhi = sum(h["weight"] ** 2 for h in holdings)
    concentration_level = "high" if hhi > 0.25 else "medium" if hhi > 0.15 else "low"

    concentration_risk = {
        "hhi": hhi,
        "level": concentration_level,
        "warnings": warnings,
        "top_holding_weight": max((h["weight"] for h in holdings), default=0),
        "top_sector_weight": max(sectors.values(), default=0),
    }

    logger.info(f"✅ [Risk] 집중도 체크 완료: HHI={hhi:.3f}, 레벨={concentration_level}")

    return {
        "concentration_risk": concentration_risk,
    }


async def market_risk_node(state: RiskState) -> dict:
    """
    3단계: 시장 리스크 분석

    - 포트폴리오 변동성 (Portfolio Volatility)
    - VaR (Value at Risk) 95%
    - 최대 손실 추정

    TODO Phase 2:
    - 실제 과거 수익률 데이터 기반 계산
    - Monte Carlo 시뮬레이션
    - 상관관계 행렬 고려
    """
    portfolio = state.get("portfolio_data", {})
    market_data = state.get("market_data", {})

    # Mock 계산 (실제로는 과거 데이터 기반)
    kospi_vol = market_data.get("kospi_volatility", 0.18)

    # 포트폴리오 가중 베타
    holdings = portfolio.get("holdings", [])
    beta_dict = market_data.get("beta", {})

    portfolio_beta = sum(
        h["weight"] * beta_dict.get(h["stock_code"], 1.0)
        for h in holdings
    )

    # 포트폴리오 변동성 = 베타 * 시장 변동성 (간소화)
    portfolio_volatility = portfolio_beta * kospi_vol

    # VaR 95% = 1.65 * volatility (정규분포 가정)
    var_95 = 1.65 * portfolio_volatility

    # 최대 손실 추정 (VaR * 1.5)
    max_drawdown_estimate = var_95 * 1.5

    market_risk = {
        "portfolio_volatility": portfolio_volatility,
        "portfolio_beta": portfolio_beta,
        "var_95": var_95,
        "max_drawdown_estimate": max_drawdown_estimate,
        "risk_level": "high" if var_95 > 0.10 else "medium" if var_95 > 0.05 else "low",
    }

    logger.info(f"✅ [Risk] 시장 리스크 분석 완료: VaR={var_95:.2%}, 변동성={portfolio_volatility:.2%}")

    return {
        "market_risk": market_risk,
    }


async def final_assessment_node(state: RiskState) -> dict:
    """
    4단계: 최종 리스크 평가

    - 전체 리스크 점수 산출
    - 리스크 레벨 결정
    - 권고사항 생성
    - HITL 트리거 여부 결정
    """
    concentration = state.get("concentration_risk", {})
    market = state.get("market_risk", {})

    # 리스크 점수 계산 (0-100)
    concentration_score = {
        "high": 70,
        "medium": 40,
        "low": 10,
    }.get(concentration.get("level"), 50)

    market_score = {
        "high": 70,
        "medium": 40,
        "low": 10,
    }.get(market.get("risk_level"), 50)

    risk_score = (concentration_score + market_score) / 2

    # 최종 리스크 레벨
    if risk_score >= 60:
        risk_level = "high"
    elif risk_score >= 30:
        risk_level = "medium"
    else:
        risk_level = "low"

    # 경고 및 권고사항
    all_warnings = concentration.get("warnings", [])

    recommendations = []
    if concentration.get("top_holding_weight", 0) > 0.30:
        recommendations.append("주요 종목 비중을 25% 이하로 분산 권장")
    if market.get("var_95", 0) > 0.10:
        recommendations.append("포트폴리오 변동성이 높음, 안전자산 비중 확대 검토")
    if concentration.get("top_sector_weight", 0) > 0.50:
        recommendations.append("섹터 분산 투자 필요")

    # HITL 트리거 (고위험일 때)
    should_trigger_hitl = risk_level == "high"

    risk_assessment = {
        "risk_level": risk_level,
        "risk_score": risk_score,
        "concentration_risk": concentration.get("hhi"),
        "volatility": market.get("portfolio_volatility"),
        "var_95": market.get("var_95"),
        "max_drawdown_estimate": market.get("max_drawdown_estimate"),
        "warnings": all_warnings,
        "recommendations": recommendations,
        "should_trigger_hitl": should_trigger_hitl,
        "sector_breakdown": state.get("portfolio_data", {}).get("sectors", {}),
    }

    logger.info(f"✅ [Risk] 최종 평가 완료: {risk_level} (점수: {risk_score:.0f})")

    summary = (
        f"리스크 수준: {risk_level.upper()} / 점수 {risk_score:.0f}. "
        f"예상 변동성 {market.get('portfolio_volatility', 0):.1%}, VaR95 {market.get('var_95', 0):.1%}."
    )

    messages = list(state.get("messages", []))
    messages.append(AIMessage(content=summary))

    return {
        "risk_assessment": risk_assessment,
        "messages": messages,
    }
