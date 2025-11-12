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
        logger.info(f"🎯 [Portfolio Tool] 포트폴리오 최적화 시작")
        logger.info(f"  - 제약 조건: {constraints}")
        logger.info(f"  - 목표 수익률: {target_return}")

        # TODO: 기존 Portfolio Agent 로직을 순수 함수로 변환하여 구현
        #
        # 구현 단계:
        # 1. 현재 포트폴리오 가져오기 (get_portfolio_positions)
        # 2. 종목별 기대 수익률 및 리스크 계산
        #    - 과거 데이터 기반 수익률/변동성 계산
        #    - 공분산 행렬 계산 (종목 간 상관관계)
        # 3. 최적화 알고리즘 실행
        #    - PyPortfolioOpt 라이브러리 사용
        #    - 샤프 비율 최대화 (또는 목표 수익률 달성)
        #    - 제약 조건 적용 (max_concentration 등)
        # 4. 리밸런싱 필요 여부 판단
        #    - 현재 vs 최적 배분 비교
        #    - rebalance_threshold 초과 시 리밸런싱 필요
        # 5. 권장 사항 생성
        #
        # 참고: src/agents/portfolio/specialists/ 로직 활용
        #       src/services/portfolio_optimizer.py 활용

        # 임시 구현 (TODO 제거 시 삭제)
        return {
            "success": False,
            "message": "TODO: 포트폴리오 최적화 로직 구현 필요",
            "optimal_allocation": {},
            "current_allocation": {},
            "rebalance_needed": False,
            "expected_return": 0.0,
            "expected_risk": 0.0,
            "sharpe_ratio": 0.0,
            "recommendations": []
        }

    except Exception as e:
        logger.error(f"❌ [Portfolio Tool] 포트폴리오 최적화 실패: {e}")
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
        logger.info(f"🔄 [Portfolio Tool] 리밸런싱 시작")
        logger.info(f"  - 목표 배분: {target_allocation}")
        logger.info(f"  - 실행 모드: {execution_mode}")

        # TODO: 기존 Portfolio Agent 로직을 순수 함수로 변환하여 구현
        #
        # 구현 단계:
        # 1. 현재 포트폴리오 가져오기
        # 2. 목표 배분 검증
        #    - 비중 합계 = 1.0 확인
        #    - 종목 코드 유효성 확인
        # 3. 매매 계획 생성
        #    - 현재 vs 목표 배분 비교
        #    - 매수/매도 수량 계산
        #    - 거래 비용 추정 (수수료, 세금)
        # 4. execution_mode='execute'인 경우
        #    - calculate_portfolio_risk 호출
        #    - HITL 승인 대기
        #    - 승인 후 execute_trade 호출
        #
        # 참고: src/agents/portfolio/specialists/rebalance_planner.py 활용

        # 임시 구현 (TODO 제거 시 삭제)
        return {
            "success": False,
            "message": "TODO: 리밸런싱 로직 구현 필요",
            "trades": [],
            "estimated_cost": {
                "trading_fee": 0,
                "tax": 0,
                "total": 0
            },
            "before_allocation": {},
            "after_allocation": {},
            "execution_mode": execution_mode
        }

    except Exception as e:
        logger.error(f"❌ [Portfolio Tool] 리밸런싱 실패: {e}")
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
