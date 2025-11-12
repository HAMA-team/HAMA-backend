"""
포트폴리오 리스크 계산 도구

매매 실행 전 포트폴리오 리스크 변화를 계산하여 HITL 승인에 필요한 정보를 제공합니다.

TODO: 기존 Risk Agent (src/agents/risk/) 로직을 순수 함수로 변환
"""
import logging
from typing import Dict, Any

from langchain_core.tools import tool
from pydantic.v1 import BaseModel, Field

logger = logging.getLogger(__name__)


# ==================== Input Schema ====================

class PortfolioRiskInput(BaseModel):
    """포트폴리오 리스크 계산 입력"""
    portfolio: dict = Field(
        description=(
            "현재 포트폴리오 (get_portfolio_positions 결과). "
            "예: {'positions': [{'ticker': '005930', 'weight': 0.3, ...}], 'total_evaluation': 10000000}"
        )
    )
    proposed_trade: dict = Field(
        description=(
            "실행할 매매 주문. "
            "예: {'ticker': '005930', 'action': 'buy', 'quantity': 10, 'price': 75000}"
        )
    )


# ==================== Tool ====================

@tool(args_schema=PortfolioRiskInput)
async def calculate_portfolio_risk(
    portfolio: dict,
    proposed_trade: dict
) -> Dict[str, Any]:
    """
    [언제] 매매 실행 전, 포트폴리오 리스크 변화를 확인할 때 사용합니다.
    [무엇] 현재 리스크와 매매 후 예상 리스크를 계산합니다.
    [필수] execute_trade 호출 전에 반드시 이 tool을 먼저 호출하세요.

    계산 항목:
    - 집중도 리스크 (상위 종목 비중)
    - 변동성 (포트폴리오 표준편차)
    - 베타 (시장 대비 민감도)
    - VaR (손실 가능성)

    Args:
        portfolio: 현재 포트폴리오 (get_portfolio_positions 결과)
        proposed_trade: 실행할 매매 주문

    Returns:
        dict: {
            "current_risk": {
                "concentration": 0.30,      # 집중도: 상위 종목 비중
                "volatility": 0.15,         # 변동성: 표준편차
                "beta": 1.2,                # 베타: 시장 민감도
                "var_95": 0.10              # VaR 95%: 5% 확률로 10% 이상 손실
            },
            "after_trade_risk": {
                "concentration": 0.45,
                "volatility": 0.18,
                "beta": 1.3,
                "var_95": 0.12
            },
            "risk_change": {
                "concentration": "+15%p",   # 집중도 증가
                "volatility": "+3%p",       # 변동성 증가
                "beta": "+0.1",             # 베타 증가
                "var_95": "+2%p"            # VaR 증가
            },
            "warnings": [
                "⚠️ 집중도 리스크 증가: 30% → 45% (권장: 40% 이하)",
                "⚠️ 변동성 증가: 15% → 18%"
            ]
        }

    예시:
    사용자: "삼성전자 10주 매수해줘"
    → get_portfolio_positions()
    → calculate_portfolio_risk(portfolio, {"ticker": "005930", "action": "buy", "quantity": 10})
    → [사용자에게 리스크 보고]
    → 사용자: "승인"
    → execute_trade(...)
    """
    try:
        logger.info(f"⚖️ [Risk Tool] 포트폴리오 리스크 계산 시작")
        logger.info(f"  - 현재 포트폴리오: {len(portfolio.get('positions', []))} 종목")
        logger.info(f"  - 제안 매매: {proposed_trade.get('action')} {proposed_trade.get('ticker')}")

        # TODO: 기존 Risk Agent 로직을 순수 함수로 변환하여 구현
        #
        # 구현 단계:
        # 1. 현재 포트폴리오 리스크 계산
        #    - concentration_specialist: 집중도 계산
        #    - market_risk_specialist: 변동성, 베타, VaR 계산
        #
        # 2. 매매 후 포트폴리오 시뮬레이션
        #    - 보유 종목에 proposed_trade 적용
        #    - 비중 재계산
        #
        # 3. 매매 후 리스크 재계산
        #
        # 4. 리스크 변화 계산 및 경고 생성
        #
        # 참고: src/agents/risk/specialists/ 로직 활용

        # 임시 구현 (TODO 제거 시 삭제)
        return {
            "success": False,
            "message": "TODO: 리스크 계산 로직 구현 필요",
            "current_risk": {
                "concentration": 0.0,
                "volatility": 0.0,
                "beta": 0.0,
                "var_95": 0.0
            },
            "after_trade_risk": {
                "concentration": 0.0,
                "volatility": 0.0,
                "beta": 0.0,
                "var_95": 0.0
            },
            "risk_change": {},
            "warnings": []
        }

    except Exception as e:
        logger.error(f"❌ [Risk Tool] 리스크 계산 실패: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": f"리스크 계산 중 오류가 발생했습니다: {e}"
        }


# ==================== Tool 목록 ====================

def get_risk_tools():
    """리스크 도구 목록 반환"""
    return [
        calculate_portfolio_risk,
    ]
