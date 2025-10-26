"""
포트폴리오 미리보기 서비스

HITL 승인 전 예상 포트폴리오를 계산합니다.
"""
from typing import Dict, List, Optional
import logging

from src.schemas.hitl import PortfolioPreview, ExpectedPortfolioPreview
from src.data.stock_sectors import get_sector_color

logger = logging.getLogger(__name__)


async def calculate_portfolio_preview(
    current_holdings: List[Dict],
    new_order: Dict,
    total_value: float,
    cash: float
) -> Optional[ExpectedPortfolioPreview]:
    """
    예상 포트폴리오 미리보기 계산

    Args:
        current_holdings: 현재 보유 종목 리스트
            [{"stock_code": "005930", "stock_name": "삼성전자", "quantity": 10, "current_price": 76300}]
        new_order: 신규 주문 정보
            {"action": "buy", "stock_code": "005930", "quantity": 131, "price": 76300, "total_amount": 10000000}
        total_value: 현재 총 평가금액
        cash: 현재 현금

    Returns:
        ExpectedPortfolioPreview 또는 None
    """
    try:
        action = new_order.get("action", "buy")
        order_stock_code = new_order.get("stock_code")
        order_quantity = new_order.get("quantity", 0)
        order_price = new_order.get("price", 0)
        order_total = new_order.get("total_amount", order_quantity * order_price)

        # 1. 현재 포트폴리오 계산
        current_preview: List[PortfolioPreview] = []
        current_stock_value = 0.0

        for holding in current_holdings:
            stock_code = holding.get("stock_code")
            if stock_code and stock_code.upper() != "CASH":
                quantity = holding.get("quantity", 0)
                current_price = holding.get("current_price", 0)
                market_value = quantity * current_price
                current_stock_value += market_value

                weight = market_value / total_value if total_value > 0 else 0.0

                # 섹터별 색상
                from src.data.stock_sectors import get_sector, get_sector_color
                sector = get_sector(stock_code)
                color = get_sector_color(sector)

                current_preview.append(
                    PortfolioPreview(
                        stock_name=holding.get("stock_name", stock_code),
                        weight=round(weight, 4),
                        color=color
                    )
                )

        # 현금 비중
        cash_weight = cash / total_value if total_value > 0 else 0.0
        if cash_weight > 0.01:  # 1% 이상일 때만 표시
            current_preview.append(
                PortfolioPreview(
                    stock_name="현금",
                    weight=round(cash_weight, 4),
                    color="#6B7280"
                )
            )

        # 2. 예상 포트폴리오 계산
        after_preview: List[PortfolioPreview] = []

        # 매수/매도에 따른 현금 및 보유량 변경
        if action == "buy":
            new_total_value = total_value + order_total
            new_cash = cash - order_total
        elif action == "sell":
            new_total_value = total_value - order_total
            new_cash = cash + order_total
        else:
            new_total_value = total_value
            new_cash = cash

        # 보유 종목 업데이트
        holdings_map = {}
        for holding in current_holdings:
            stock_code = holding.get("stock_code")
            if stock_code and stock_code.upper() != "CASH":
                holdings_map[stock_code] = {
                    "stock_name": holding.get("stock_name", stock_code),
                    "quantity": holding.get("quantity", 0),
                    "current_price": holding.get("current_price", 0)
                }

        # 신규 주문 반영
        if order_stock_code:
            if order_stock_code in holdings_map:
                if action == "buy":
                    holdings_map[order_stock_code]["quantity"] += order_quantity
                elif action == "sell":
                    holdings_map[order_stock_code]["quantity"] -= order_quantity
                    if holdings_map[order_stock_code]["quantity"] <= 0:
                        del holdings_map[order_stock_code]
            else:
                if action == "buy":
                    holdings_map[order_stock_code] = {
                        "stock_name": new_order.get("stock_name", order_stock_code),
                        "quantity": order_quantity,
                        "current_price": order_price
                    }

        # 예상 포트폴리오 비중 계산
        for stock_code, holding in holdings_map.items():
            quantity = holding["quantity"]
            current_price = holding["current_price"]
            market_value = quantity * current_price

            weight = market_value / new_total_value if new_total_value > 0 else 0.0

            # 섹터별 색상
            from src.data.stock_sectors import get_sector, get_sector_color
            sector = get_sector(stock_code)

            # 변경된 종목은 강조 색상
            if stock_code == order_stock_code:
                color = "#EF4444"  # 빨강 (강조)
            else:
                color = get_sector_color(sector)

            after_preview.append(
                PortfolioPreview(
                    stock_name=holding["stock_name"],
                    weight=round(weight, 4),
                    color=color
                )
            )

        # 예상 현금 비중
        new_cash_weight = new_cash / new_total_value if new_total_value > 0 else 0.0
        if new_cash_weight > 0.01:
            after_preview.append(
                PortfolioPreview(
                    stock_name="현금",
                    weight=round(new_cash_weight, 4),
                    color="#6B7280"
                )
            )

        # 비중 합계 검증 (디버그용)
        current_total = sum(p.weight for p in current_preview)
        after_total = sum(p.weight for p in after_preview)

        logger.debug(f"Current total weight: {current_total:.4f}")
        logger.debug(f"After total weight: {after_total:.4f}")

        return ExpectedPortfolioPreview(
            current=current_preview,
            after_approval=after_preview
        )

    except Exception as e:
        logger.error(f"포트폴리오 미리보기 계산 실패: {e}")
        return None


async def calculate_weight_change(
    current_holdings: List[Dict],
    new_order: Dict,
    total_value: float,
    cash: float
) -> tuple[float, float]:
    """
    현재 비중 및 예상 비중 계산

    Args:
        current_holdings: 현재 보유 종목
        new_order: 신규 주문
        total_value: 총 평가금액
        cash: 현금

    Returns:
        (current_weight, expected_weight)
    """
    try:
        action = new_order.get("action", "buy")
        order_stock_code = new_order.get("stock_code")
        order_quantity = new_order.get("quantity", 0)
        order_price = new_order.get("price", 0)
        order_total = new_order.get("total_amount", order_quantity * order_price)

        # 현재 비중 계산
        current_quantity = 0
        current_price = order_price

        for holding in current_holdings:
            if holding.get("stock_code") == order_stock_code:
                current_quantity = holding.get("quantity", 0)
                current_price = holding.get("current_price", order_price)
                break

        current_value = current_quantity * current_price
        current_weight = current_value / total_value if total_value > 0 else 0.0

        # 예상 비중 계산
        if action == "buy":
            expected_quantity = current_quantity + order_quantity
            new_total_value = total_value + order_total
        elif action == "sell":
            expected_quantity = current_quantity - order_quantity
            new_total_value = total_value - order_total
        else:
            expected_quantity = current_quantity
            new_total_value = total_value

        expected_value = expected_quantity * current_price
        expected_weight = expected_value / new_total_value if new_total_value > 0 else 0.0

        return round(current_weight, 4), round(expected_weight, 4)

    except Exception as e:
        logger.error(f"비중 계산 실패: {e}")
        return 0.0, 0.0
