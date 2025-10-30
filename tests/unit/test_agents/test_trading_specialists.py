"""
Trading Agent Specialist 노드 단위 테스트

테스트 범위:
1. Buy Specialist 노드 (매수 점수 시스템)
2. Sell Specialist 노드 (매도 결정 로직)
3. Risk/Reward Calculator 노드 (손절가/목표가)

사용법:
    pytest tests/unit/test_agents/test_trading_specialists.py -v
    python tests/unit/test_agents/test_trading_specialists.py
"""
import asyncio
import pytest
from uuid import uuid4

from langchain_core.messages import HumanMessage

from src.agents.trading.nodes import (
    buy_specialist_node,
    sell_specialist_node,
    risk_reward_calculator_node,
)
from src.agents.trading.state import TradingState


class TestTradingSpecialists:
    """Trading Agent Specialist 노드 테스트"""

    @pytest.mark.asyncio
    async def test_buy_specialist_strong_buy(self):
        """
        Buy Specialist 테스트: 강력 매수 시나리오 (8~10점)

        Research 결과가 모두 긍정적일 때 높은 매수 점수를 반환하는지 검증
        """
        print("\n[Test] Buy Specialist - 강력 매수")

        state: TradingState = {
            "messages": [HumanMessage(content="삼성전자 매수")],
            "request_id": str(uuid4()),
            "user_id": "test_user",
            "portfolio_id": "test_portfolio",
            "query": "삼성전자 10주 매수",
            "automation_level": 2,
            "stock_code": "005930",
            "quantity": 10,
            "order_type": "BUY",
            "order_price": 75000.0,
            "trade_prepared": False,
            "trade_approved": False,
            "trade_executed": False,
            # Research 결과 (매우 긍정적)
            "research_result": {
                "recommendation": "BUY",
                "confidence": 5,
                "current_price": 75000,
                "target_price": 90000,
                "upside_potential": "20.0%",
                "technical_summary": {
                    "trend": "상승추세",
                    "signals": {"rsi_signal": "과매도", "macd_signal": "매수"},
                },
                "trading_flow_summary": {
                    "foreign": "순매수",
                    "institutional": "순매수",
                    "outlook": "긍정적",
                },
                "information_summary": {
                    "sentiment": "긍정적",
                    "risk_level": "낮음",
                },
                "fundamental_summary": {
                    "PER": 12.0,
                    "PBR": 1.0,
                    "valuation": "저평가",
                },
            },
        }

        # 실행
        result = await buy_specialist_node(state)

        # 검증
        assert "buy_score" in result, "매수 점수가 있어야 함"
        assert "buy_rationale" in result, "매수 근거가 있어야 함"
        assert "investment_period" in result, "투자 기간이 있어야 함"

        buy_score = result["buy_score"]
        assert 1 <= buy_score <= 10, "매수 점수는 1~10 범위여야 함"
        assert buy_score >= 7, "긍정적인 시나리오에서는 7점 이상이어야 함"

        investment_period = result["investment_period"]
        assert investment_period in ["단기", "중기", "장기"], "투자 기간은 정의된 값이어야 함"

        print(f"  ✅ 매수 점수: {buy_score}/10")
        print(f"  ✅ 투자 기간: {investment_period}")
        print(f"  ✅ 매수 근거: {result['buy_rationale'][:80]}...")

    @pytest.mark.asyncio
    async def test_buy_specialist_weak_buy(self):
        """
        Buy Specialist 테스트: 약한 매수 시나리오 (6점 이하)

        Research 결과가 혼재되거나 부정적일 때 낮은 매수 점수를 반환하는지 검증
        """
        print("\n[Test] Buy Specialist - 약한 매수")

        state: TradingState = {
            "messages": [HumanMessage(content="매수 고려")],
            "request_id": str(uuid4()),
            "stock_code": "005930",
            "order_type": "BUY",
            # Research 결과 (혼재)
            "research_result": {
                "recommendation": "HOLD",
                "confidence": 2,
                "current_price": 75000,
                "target_price": 76000,
                "upside_potential": "1.3%",
                "technical_summary": {
                    "trend": "횡보",
                    "signals": {"rsi_signal": "과매수", "macd_signal": "중립"},
                },
                "trading_flow_summary": {
                    "foreign": "순매도",
                    "institutional": "보합",
                    "outlook": "중립",
                },
                "information_summary": {
                    "sentiment": "부정적",
                    "risk_level": "높음",
                },
                "fundamental_summary": {
                    "PER": 35.0,
                    "PBR": 4.0,
                    "valuation": "고평가",
                },
            },
        }

        # 실행
        result = await buy_specialist_node(state)

        # 검증
        buy_score = result["buy_score"]
        assert buy_score <= 6, "부정적인 시나리오에서는 6점 이하여야 함"

        print(f"  ✅ 매수 점수: {buy_score}/10 (낮은 점수 확인)")

    @pytest.mark.asyncio
    async def test_sell_specialist_sell_decision(self):
        """
        Sell Specialist 테스트: 매도 권장 시나리오

        부정적 시장 상황에서 매도를 권장하는지 검증
        """
        print("\n[Test] Sell Specialist - 매도 권장")

        state: TradingState = {
            "messages": [HumanMessage(content="매도 결정")],
            "request_id": str(uuid4()),
            "stock_code": "005930",
            "order_type": "SELL",
            # Research 결과 (부정적)
            "research_result": {
                "recommendation": "SELL",
                "current_price": 70000,
                "target_price": 65000,
                "technical_summary": {
                    "trend": "하락추세",
                },
                "trading_flow_summary": {
                    "outlook": "부정적",
                },
                "information_summary": {
                    "sentiment": "부정적",
                },
            },
        }

        # 실행
        result = await sell_specialist_node(state)

        # 검증
        assert "sell_rationale" in result, "매도 근거가 있어야 함"

        print(f"  ✅ 매도 근거: {result['sell_rationale'][:80]}...")

    @pytest.mark.asyncio
    async def test_risk_reward_calculator_short_term(self):
        """
        Risk/Reward Calculator 테스트: 단기 투자

        단기 투자 목표가/손절가가 올바르게 계산되는지 검증
        - 목표 수익률: 5%
        - 손절 비율: -3%
        - Risk/Reward Ratio: 최소 1.5:1
        """
        print("\n[Test] Risk/Reward Calculator - 단기 투자")

        state: TradingState = {
            "messages": [HumanMessage(content="단기 투자")],
            "stock_code": "005930",
            "order_type": "BUY",
            "order_price": 100000.0,
            "buy_score": 8,
            "investment_period": "단기",
            "research_result": {
                "current_price": 100000,
                "target_price": 105000,  # 5% 상승
            },
        }

        # 실행
        result = await risk_reward_calculator_node(state)

        # 검증
        assert "target_price" in result, "목표가가 있어야 함"
        assert "stop_loss" in result, "손절가가 있어야 함"
        assert "risk_reward_ratio" in result, "Risk/Reward 비율이 있어야 함"

        target_price = result["target_price"]
        stop_loss = result["stop_loss"]
        risk_reward_ratio = result["risk_reward_ratio"]

        # 목표가는 현재가보다 높아야 함
        assert target_price > 100000, "목표가는 현재가보다 높아야 함"

        # 손절가는 현재가보다 낮아야 함
        assert stop_loss < 100000, "손절가는 현재가보다 낮아야 함"

        # Risk/Reward Ratio는 최소 1.5:1 이상
        assert risk_reward_ratio >= 1.5, "Risk/Reward 비율은 최소 1.5:1 이상이어야 함"

        reward = target_price - 100000
        risk = 100000 - stop_loss
        actual_ratio = reward / risk if risk > 0 else 0

        print(f"  ✅ 목표가: {target_price:,.0f}원 (+{((target_price/100000-1)*100):.1f}%)")
        print(f"  ✅ 손절가: {stop_loss:,.0f}원 ({((stop_loss/100000-1)*100):.1f}%)")
        print(f"  ✅ Risk/Reward: {risk_reward_ratio:.2f}:1 (실제: {actual_ratio:.2f}:1)")

    @pytest.mark.asyncio
    async def test_risk_reward_calculator_long_term(self):
        """
        Risk/Reward Calculator 테스트: 장기 투자

        장기 투자 목표가/손절가가 올바르게 계산되는지 검증
        - 목표 수익률: 20%
        - 손절 비율: -7%
        """
        print("\n[Test] Risk/Reward Calculator - 장기 투자")

        state: TradingState = {
            "messages": [HumanMessage(content="장기 투자")],
            "stock_code": "005930",
            "order_type": "BUY",
            "order_price": 100000.0,
            "buy_score": 9,
            "investment_period": "장기",
            "research_result": {
                "current_price": 100000,
                "target_price": 130000,  # 30% 상승 (높은 매수 점수로 상향)
            },
        }

        # 실행
        result = await risk_reward_calculator_node(state)

        target_price = result["target_price"]
        stop_loss = result["stop_loss"]

        # 장기 투자는 더 높은 목표 수익률
        target_return = (target_price - 100000) / 100000
        assert target_return >= 0.15, "장기 투자는 15% 이상 목표 수익률이어야 함"

        # 장기 투자는 더 큰 손절 허용
        stop_loss_pct = (stop_loss - 100000) / 100000
        assert stop_loss_pct <= -0.05, "장기 투자는 -5% 이상 손절 허용해야 함"

        print(f"  ✅ 목표가: {target_price:,.0f}원 (+{(target_return*100):.1f}%)")
        print(f"  ✅ 손절가: {stop_loss:,.0f}원 ({(stop_loss_pct*100):.1f}%)")

    @pytest.mark.asyncio
    async def test_specialists_skip_on_wrong_order_type(self):
        """
        Specialist 노드 건너뛰기 테스트

        - Buy Specialist는 SELL 주문에서 건너뛰어야 함
        - Sell Specialist는 BUY 주문에서 건너뛰어야 함
        """
        print("\n[Test] Specialist 노드 건너뛰기")

        # Buy Specialist with SELL order
        sell_state: TradingState = {
            "messages": [],
            "stock_code": "005930",
            "order_type": "SELL",
            "research_result": {},
        }

        buy_result = await buy_specialist_node(sell_state)
        assert buy_result == {}, "Buy Specialist는 SELL 주문에서 건너뛰어야 함"
        print("  ✅ Buy Specialist는 SELL 주문 건너뜀")

        # Sell Specialist with BUY order
        buy_state: TradingState = {
            "messages": [],
            "stock_code": "005930",
            "order_type": "BUY",
            "research_result": {},
        }

        sell_result = await sell_specialist_node(buy_state)
        assert sell_result == {}, "Sell Specialist는 BUY 주문에서 건너뛰어야 함"
        print("  ✅ Sell Specialist는 BUY 주문 건너뜀")


if __name__ == "__main__":
    """직접 실행 시"""
    async def run_tests():
        test_suite = TestTradingSpecialists()

        print("=" * 80)
        print("Trading Agent Specialist 노드 테스트 시작")
        print("=" * 80)

        try:
            await test_suite.test_buy_specialist_strong_buy()
            await test_suite.test_buy_specialist_weak_buy()
            await test_suite.test_sell_specialist_sell_decision()
            await test_suite.test_risk_reward_calculator_short_term()
            await test_suite.test_risk_reward_calculator_long_term()
            await test_suite.test_specialists_skip_on_wrong_order_type()

            print("\n" + "=" * 80)
            print("✅ 모든 테스트 통과!")
            print("=" * 80)

        except AssertionError as e:
            print(f"\n❌ 테스트 실패: {e}")
        except Exception as e:
            print(f"\n❌ 예외 발생: {e}")
            import traceback
            traceback.print_exc()

    asyncio.run(run_tests())
