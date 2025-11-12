"""
포트폴리오 관리 도구

포트폴리오 최적화 및 리밸런싱 기능을 Supervisor가 직접 사용할 수 있도록 tool로 노출합니다.

TODO: 기존 Portfolio Agent (src/agents/portfolio/) 로직을 순수 함수로 변환
"""
import logging
from typing import Dict, Any, List, Optional

from langchain_core.tools import tool
from pydantic.v1 import BaseModel, Field

logger = logging.getLogger(__name__)


# ==================== Input Schemas ====================

class OptimizePortfolioInput(BaseModel):
    """포트폴리오 최적화 입력"""
    constraints: dict = Field(
        default_factory=dict,
        description=(
            "최적화 제약 조건. "
            "예: {'max_concentration': 0.4, 'min_diversification': 5, 'risk_tolerance': 'moderate'}"
        )
    )
    target_return: Optional[float] = Field(
        default=None,
        description="목표 수익률 (예: 0.15 = 15%)"
    )
    rebalance_threshold: Optional[float] = Field(
        default=0.05,
        description="리밸런싱 임계값 (예: 0.05 = 5%p 이상 차이나면 리밸런싱)"
    )


class RebalancePortfolioInput(BaseModel):
    """포트폴리오 리밸런싱 입력"""
    target_allocation: dict = Field(
        description=(
            "목표 자산 배분. "
            "예: {'005930': 0.30, '000660': 0.25, '035420': 0.20, 'cash': 0.25}"
        )
    )
    execution_mode: str = Field(
        default="preview",
        description="실행 모드: 'preview' (계획만 생성) 또는 'execute' (실제 주문 생성)"
    )


# ==================== Tools ====================

@tool(args_schema=OptimizePortfolioInput)
async def optimize_portfolio(
    constraints: dict = None,
    target_return: Optional[float] = None,
    rebalance_threshold: Optional[float] = 0.05
) -> Dict[str, Any]:
    """
    [언제] 사용자가 포트폴리오 최적화나 자산 배분 조정을 요청할 때 사용합니다.
    [무엇] 현재 보유 종목과 제약 조건을 바탕으로 최적의 자산 배분을 계산합니다.
    [주의] 실제 주문 생성은 하지 않으며, 최적 배분 계획만 제공합니다.

    최적화 방법:
    - 샤프 비율 최대화 (수익률 대비 리스크 최소화)
    - 제약 조건 준수 (집중도, 다각화, 리스크 허용도)
    - 거래 비용 고려

    Args:
        constraints: 최적화 제약 조건
            - max_concentration: 단일 종목 최대 비중 (기본: 0.4 = 40%)
            - min_diversification: 최소 보유 종목 수 (기본: 5개)
            - risk_tolerance: 리스크 허용도 ('conservative', 'moderate', 'aggressive')
        target_return: 목표 수익률 (선택적)
        rebalance_threshold: 리밸런싱 임계값 (기본: 5%p)

    Returns:
        dict: {
            "optimal_allocation": {
                "005930": 0.30,   # 삼성전자 30%
                "000660": 0.25,   # SK하이닉스 25%
                "035420": 0.20,   # NAVER 20%
                "cash": 0.25      # 현금 25%
            },
            "current_allocation": {...},
            "rebalance_needed": True,
            "expected_return": 0.18,     # 예상 수익률 18%
            "expected_risk": 0.12,       # 예상 리스크 12%
            "sharpe_ratio": 1.5,         # 샤프 비율
            "recommendations": [
                "삼성전자 비중 축소: 40% → 30%",
                "NAVER 비중 확대: 10% → 20%"
            ]
        }

    예시:
    - 사용자: "내 포트폴리오 최적화해줘"
      → optimize_portfolio()
    - 사용자: "수익률 15% 목표로 포트폴리오 조정해줘"
      → optimize_portfolio(target_return=0.15)
    """
    try:
        logger.info("🎯 [Portfolio Tool] 포트폴리오 최적화 시작")
        logger.info(f"  - 제약 조건: {constraints}")
        logger.info(f"  - 목표 수익률: {target_return}")

        # 기본 제약 조건 설정
        if constraints is None:
            constraints = {}

        risk_profile = constraints.get("risk_tolerance", "moderate")
        max_concentration = constraints.get("max_concentration", 0.4)
        min_diversification = constraints.get("min_diversification", 5)

        # 1. Portfolio Optimizer로 최적 배분 계산
        from src.services.portfolio_optimizer import portfolio_optimizer

        # TODO: 현재 보유 종목 가져오기 (KIS API)
        # 임시로 빈 리스트 사용
        current_holdings = []
        strategy_result = None
        total_value = 0.0

        proposed, metrics = await portfolio_optimizer.calculate_target_allocation(
            current_holdings=current_holdings,
            strategy_result=strategy_result,
            risk_profile=risk_profile,
            total_value=total_value
        )

        logger.info(f"✅ [Portfolio Tool] 최적 배분 계산 완료: {len(proposed)}개 자산")

        # 2. 현재 배분과 비교
        current_allocation = {h.get("stock_code"): h.get("weight", 0.0) for h in current_holdings}
        optimal_allocation = {p.get("stock_code"): p.get("weight", 0.0) for p in proposed}

        # 3. 리밸런싱 필요 여부 판단
        rebalance_needed = False
        recommendations = []

        for stock_code, target_weight in optimal_allocation.items():
            current_weight = current_allocation.get(stock_code, 0.0)
            delta = target_weight - current_weight

            if abs(delta) >= rebalance_threshold:
                rebalance_needed = True
                stock_name = next((p.get("stock_name") for p in proposed if p.get("stock_code") == stock_code), stock_code)

                if delta > 0:
                    recommendations.append(f"{stock_name} 비중 확대: {current_weight*100:.0f}% → {target_weight*100:.0f}%")
                else:
                    recommendations.append(f"{stock_name} 비중 축소: {current_weight*100:.0f}% → {target_weight*100:.0f}%")

        # 4. 결과 반환
        return {
            "success": True,
            "optimal_allocation": optimal_allocation,
            "current_allocation": current_allocation,
            "rebalance_needed": rebalance_needed,
            "expected_return": metrics.get("expected_return", 0.12),
            "expected_risk": metrics.get("expected_volatility", 0.17),
            "sharpe_ratio": metrics.get("sharpe_ratio", 0.80),
            "recommendations": recommendations,
            "rationale": metrics.get("rationale", "균형 포트폴리오 구성"),
        }

    except Exception as e:
        logger.error(f"❌ [Portfolio Tool] 포트폴리오 최적화 실패: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "message": f"포트폴리오 최적화 중 오류가 발생했습니다: {e}"
        }


@tool(args_schema=RebalancePortfolioInput)
async def rebalance_portfolio(
    target_allocation: dict,
    execution_mode: str = "preview"
) -> Dict[str, Any]:
    """
    [언제] 사용자가 특정 자산 배분으로 리밸런싱을 요청할 때 사용합니다.
    [무엇] 현재 포트폴리오를 목표 배분으로 조정하기 위한 매매 계획을 생성합니다.
    [필수] execution_mode='execute'인 경우 HITL 승인이 필요합니다.

    Args:
        target_allocation: 목표 자산 배분
            - 키: 종목 코드 또는 'cash'
            - 값: 비중 (0~1, 합계 1.0)
        execution_mode: 실행 모드
            - 'preview': 매매 계획만 생성 (기본값)
            - 'execute': 실제 주문 생성 (HITL 승인 필요)

    Returns:
        dict: {
            "trades": [
                {"ticker": "005930", "action": "sell", "quantity": 5, "reason": "비중 축소 40% → 30%"},
                {"ticker": "035420", "action": "buy", "quantity": 10, "reason": "비중 확대 10% → 20%"}
            ],
            "estimated_cost": {
                "trading_fee": 15000,        # 거래 수수료
                "tax": 30000,                # 거래세
                "total": 45000               # 총 비용
            },
            "before_allocation": {...},
            "after_allocation": {...},
            "execution_mode": "preview"
        }

    예시:
    - 사용자: "삼성전자 30%, SK하이닉스 25%, 현금 45%로 리밸런싱해줘"
      → rebalance_portfolio({"005930": 0.30, "000660": 0.25, "cash": 0.45})
      → [매매 계획 제시]
      → 사용자: "실행해"
      → rebalance_portfolio(..., execution_mode="execute")  # HITL 승인 후 실행
    """
    try:
        logger.info("🔄 [Portfolio Tool] 리밸런싱 시작")
        logger.info(f"  - 목표 배분: {target_allocation}")
        logger.info(f"  - 실행 모드: {execution_mode}")

        # 1. 목표 배분 검증
        total_weight = sum(target_allocation.values())
        if abs(total_weight - 1.0) > 0.01:
            return {
                "success": False,
                "message": f"목표 배분 비중 합계가 100%가 아닙니다: {total_weight*100:.1f}%"
            }

        # 2. 현재 포트폴리오 가져오기
        # TODO: KIS API에서 실제 포트폴리오 조회
        # 임시로 빈 리스트 사용
        current_holdings = []
        total_value = 10000000  # 임시 총 자산 1000만원

        # 현재 배분 계산
        current_allocation = {}
        for h in current_holdings:
            stock_code = h.get("stock_code")
            if stock_code:
                pos_value = h.get("quantity", 0) * h.get("current_price", 0)
                weight = pos_value / total_value if total_value > 0 else 0
                current_allocation[stock_code] = weight

        # 3. 매매 계획 생성
        trades = []
        processed_codes = set()

        for stock_code, target_weight in target_allocation.items():
            if stock_code.lower() == "cash":
                processed_codes.add(stock_code)
                continue

            current_weight = current_allocation.get(stock_code, 0.0)
            delta = target_weight - current_weight

            # 5%p 이상 차이날 때만 리밸런싱
            if abs(delta) < 0.005:
                processed_codes.add(stock_code)
                continue

            action = "buy" if delta > 0 else "sell"
            amount = abs(total_value * delta)
            # 가격은 TODO (실제 현재가 조회 필요)
            estimated_price = 50000
            quantity = int(amount / estimated_price)

            if quantity > 0:
                trades.append({
                    "ticker": stock_code,
                    "action": action,
                    "quantity": quantity,
                    "reason": f"비중 조정 {current_weight*100:.0f}% → {target_weight*100:.0f}%"
                })

            processed_codes.add(stock_code)

        # 현재 보유하지만 목표에 없는 종목 전량 매도
        for stock_code, current_weight in current_allocation.items():
            if stock_code not in processed_codes and abs(current_weight) > 0.005:
                amount = total_value * current_weight
                estimated_price = 50000
                quantity = int(amount / estimated_price)

                if quantity > 0:
                    trades.append({
                        "ticker": stock_code,
                        "action": "sell",
                        "quantity": quantity,
                        "reason": f"포트폴리오에서 제외"
                    })

        # 4. 거래 비용 추정
        total_trading_amount = sum(
            t["quantity"] * 50000  # TODO: 실제 가격
            for t in trades
        )
        trading_fee = total_trading_amount * 0.00015  # 0.015% 수수료
        tax = sum(
            t["quantity"] * 50000 * 0.0023  # 0.23% 거래세 (매도만)
            for t in trades
            if t["action"] == "sell"
        )
        total_cost = trading_fee + tax

        logger.info(f"✅ [Portfolio Tool] 리밸런싱 계획 생성 완료: {len(trades)}건")

        # 5. 결과 반환
        return {
            "success": True,
            "trades": trades,
            "estimated_cost": {
                "trading_fee": trading_fee,
                "tax": tax,
                "total": total_cost
            },
            "before_allocation": current_allocation,
            "after_allocation": target_allocation,
            "execution_mode": execution_mode,
            "message": f"{len(trades)}건의 매매 계획이 생성되었습니다. "
                      + ("실제 실행을 원하시면 승인해주세요." if execution_mode == "execute" else "")
        }

    except Exception as e:
        logger.error(f"❌ [Portfolio Tool] 리밸런싱 실패: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "message": f"리밸런싱 중 오류가 발생했습니다: {e}"
        }


# ==================== Tool 목록 ====================

def get_portfolio_tools():
    """포트폴리오 도구 목록 반환"""
    return [
        optimize_portfolio,
        rebalance_portfolio,
    ]
