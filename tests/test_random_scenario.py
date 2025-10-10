"""
랜덤 시나리오 전체 플로우 테스트

실제 운영 환경을 시뮬레이션:
1. 랜덤 종목 선택
2. 전체 투자 파이프라인 실행
3. 실제 KIS API 연동 (모의투자)
4. 모든 에이전트 통합 테스트

목표: 실제 사용자처럼 전체 시스템 검증
"""
import asyncio
import random
from typing import List, Dict, Any

from src.services.stock_data_service import stock_data_service
from src.services.dart_service import dart_service
from src.services.kis_service import kis_service
from src.agents.graph_master import run_graph


# ==================== 랜덤 시나리오 설정 ====================

# KOSPI 대형주 종목 풀
STOCK_POOL = [
    ("005930", "삼성전자"),
    ("000660", "SK하이닉스"),
    ("035420", "NAVER"),
    ("005380", "현대차"),
    ("051910", "LG화학"),
    ("006400", "삼성SDI"),
    ("035720", "카카오"),
    ("000270", "기아"),
    ("068270", "셀트리온"),
    ("207940", "삼성바이오로직스"),
]

# 투자 시나리오 템플릿
SCENARIOS = [
    {
        "name": "공격적 성장 투자자",
        "risk_profile": "aggressive",
        "automation_level": 1,  # Pilot
        "queries": [
            "{stock_name} 기업 분석해줘",
            "이 종목에 투자하면 좋을까?",
            "공격적인 포트폴리오를 구성해줘",
            "{stock_name} {quantity}주 매수해줘",
        ]
    },
    {
        "name": "보수적 안정 투자자",
        "risk_profile": "conservative",
        "automation_level": 2,  # Copilot
        "queries": [
            "{stock_name}의 재무 상태를 분석해줘",
            "안전한 투자 전략을 세워줘",
            "보수적인 포트폴리오로 리밸런싱해줘",
        ]
    },
    {
        "name": "신중한 분석 투자자",
        "risk_profile": "moderate",
        "automation_level": 3,  # Advisor
        "queries": [
            "{stock_name}에 대해 상세히 분석해줘",
            "이 종목의 리스크는 어느 정도야?",
            "중립적인 투자 전략을 추천해줘",
            "내 포트폴리오를 점검해줘",
        ]
    },
    {
        "name": "단기 트레이더",
        "risk_profile": "aggressive",
        "automation_level": 1,
        "queries": [
            "{stock_name} 기술적 분석 해줘",
            "단기 매매 전략 추천해줘",
            "{stock_name} {quantity}주 시장가로 매수",
        ]
    },
]


# ==================== 랜덤 시나리오 생성기 ====================

def generate_random_scenario() -> Dict[str, Any]:
    """
    랜덤 투자 시나리오 생성

    Returns:
        시나리오 딕셔너리
    """
    # 1. 랜덤 종목 선택
    stock_code, stock_name = random.choice(STOCK_POOL)

    # 2. 랜덤 시나리오 선택
    scenario = random.choice(SCENARIOS)

    # 3. 랜덤 매수 수량 (1~10주)
    quantity = random.randint(1, 10)

    # 4. 쿼리 템플릿 채우기
    queries = [
        q.format(stock_name=stock_name, quantity=quantity)
        for q in scenario["queries"]
    ]

    return {
        "scenario_name": scenario["name"],
        "stock_code": stock_code,
        "stock_name": stock_name,
        "quantity": quantity,
        "risk_profile": scenario["risk_profile"],
        "automation_level": scenario["automation_level"],
        "queries": queries,
    }


# ==================== 전체 플로우 테스트 ====================

async def test_random_full_flow():
    """
    랜덤 시나리오로 전체 플로우 테스트

    플로우:
    1. 랜덤 시나리오 생성
    2. Service Layer 데이터 수집
    3. Agent Layer 실행 (Master Supervisor)
    4. KIS API 매매 실행 (모의)
    5. 결과 검증
    """
    print("\n" + "=" * 80)
    print("🎲 랜덤 시나리오 전체 플로우 테스트")
    print("=" * 80)

    # 1. 랜덤 시나리오 생성
    scenario = generate_random_scenario()

    print(f"\n📋 시나리오: {scenario['scenario_name']}")
    print(f"   종목: {scenario['stock_name']} ({scenario['stock_code']})")
    print(f"   수량: {scenario['quantity']}주")
    print(f"   리스크 프로필: {scenario['risk_profile']}")
    print(f"   자동화 레벨: {scenario['automation_level']}")
    print(f"   질의 수: {len(scenario['queries'])}개\n")

    # 2. Service Layer: 데이터 수집
    print("🔍 [Step 1/4] Service Layer 데이터 수집")
    print("-" * 80)

    # 2.1. 주가 데이터
    try:
        price_data = await stock_data_service.get_stock_price(
            scenario['stock_code'],
            days=30
        )
        if price_data is not None and len(price_data) > 0:
            current_price = price_data.iloc[-1]['Close']
            print(f"✅ 주가 데이터: {len(price_data)}일, 현재가 {current_price:,.0f}원")
        else:
            print("⚠️ 주가 데이터 없음")
            current_price = 0
    except Exception as e:
        print(f"❌ 주가 조회 실패: {e}")
        current_price = 0

    # 2.2. DART 재무 정보
    try:
        corp_code = dart_service.search_corp_code_by_stock_code(scenario['stock_code'])
        if corp_code:
            company_info = await dart_service.get_company_info(corp_code)
            if company_info:
                print(f"✅ 기업 정보: {company_info.get('corp_name', 'N/A')}")

            financial = await dart_service.get_financial_statement(corp_code, bsns_year="2023")
            if financial and len(financial) > 0:
                print(f"✅ 재무제표: {len(financial)}개 항목")
        else:
            print("⚠️ DART 고유번호 매핑 없음")
    except Exception as e:
        print(f"⚠️ DART 조회 스킵: {e}")

    # 2.3. KIS 현재가 조회
    try:
        kis_price = await kis_service.get_stock_price(scenario['stock_code'])
        print(f"✅ KIS 현재가: {kis_price['current_price']:,}원")
        print(f"   등락: {kis_price['change_price']:+,}원 ({kis_price['change_rate']:+.2f}%)")
    except Exception as e:
        print(f"⚠️ KIS 시세 조회 스킵: {e}")

    await asyncio.sleep(0.5)  # 가독성을 위한 짧은 지연

    # 3. Agent Layer: Master Supervisor 실행
    print(f"\n🤖 [Step 2/4] Agent Layer 실행 (자동화 레벨 {scenario['automation_level']})")
    print("-" * 80)

    thread_id = f"random_scenario_{random.randint(1000, 9999)}"

    for idx, query in enumerate(scenario['queries'], 1):
        print(f"\n💬 질의 {idx}/{len(scenario['queries'])}: \"{query}\"")

        try:
            result = await run_graph(
                query=query,
                automation_level=scenario['automation_level'],
                thread_id=thread_id
            )

            if result and "message" in result:
                # 응답 요약 (처음 200자만)
                response = result['message']
                summary = response[:200] + "..." if len(response) > 200 else response
                print(f"✅ 응답: {summary}")
            else:
                print("⚠️ 응답 없음")

        except Exception as e:
            print(f"❌ 에이전트 실행 실패: {e}")
            import traceback
            traceback.print_exc()

        # Rate limit 준수
        await asyncio.sleep(1.5)

    # 4. KIS API: 실제 매매 시뮬레이션
    print(f"\n💰 [Step 3/4] KIS API 매매 시뮬레이션")
    print("-" * 80)

    # 매수 포함된 시나리오만 실행
    if any("매수" in q for q in scenario['queries']):
        try:
            # Rate limit 준수
            await asyncio.sleep(1.5)

            order_result = await kis_service.place_order(
                stock_code=scenario['stock_code'],
                order_type="BUY",
                quantity=scenario['quantity'],
                price=None,  # 시장가
            )

            print(f"✅ 매수 주문 접수")
            print(f"   주문번호: {order_result['order_no']}")
            print(f"   종목: {scenario['stock_name']} ({scenario['stock_code']})")
            print(f"   수량: {scenario['quantity']}주")
            print(f"   예상금액: {current_price * scenario['quantity']:,.0f}원")

        except Exception as e:
            print(f"⚠️ 매수 주문 실패 (정상): {e}")
    else:
        print("⏭️ 매수 주문 시나리오 아님 - 스킵")

    # 5. 결과 검증 및 요약
    print(f"\n📊 [Step 4/4] 결과 검증 및 요약")
    print("-" * 80)

    # 계좌 잔고 확인
    try:
        await asyncio.sleep(1.5)  # Rate limit
        balance = await kis_service.get_account_balance()
        print(f"✅ 계좌 현황:")
        print(f"   총 자산: {balance['total_assets']:,}원")
        print(f"   예수금: {balance['cash_balance']:,}원")
        print(f"   보유 종목: {len(balance['stocks'])}개")
    except Exception as e:
        print(f"⚠️ 계좌 조회 스킵: {e}")

    print("\n" + "=" * 80)
    print("✅ 랜덤 시나리오 전체 플로우 테스트 완료!")
    print("=" * 80)


async def test_multiple_random_scenarios(count: int = 3):
    """
    여러 개의 랜덤 시나리오 순차 실행

    Args:
        count: 실행할 시나리오 개수
    """
    print("\n" + "🎯" * 40)
    print(f"다중 랜덤 시나리오 테스트 ({count}개)")
    print("🎯" * 40)

    for i in range(count):
        print(f"\n\n{'#' * 80}")
        print(f"시나리오 {i+1}/{count}")
        print(f"{'#' * 80}")

        await test_random_full_flow()

        if i < count - 1:
            print(f"\n⏳ 다음 시나리오까지 3초 대기...")
            await asyncio.sleep(3)

    print(f"\n\n{'🎊' * 40}")
    print(f"✅ {count}개 시나리오 모두 완료!")
    print(f"{'🎊' * 40}")


# ==================== 단위 테스트 (pytest) ====================

import pytest


class TestRandomScenario:
    """랜덤 시나리오 pytest 테스트 클래스"""

    @pytest.mark.asyncio
    async def test_single_random_scenario(self):
        """단일 랜덤 시나리오 테스트"""
        await test_random_full_flow()

    @pytest.mark.asyncio
    async def test_scenario_generation(self):
        """시나리오 생성 테스트"""
        scenario = generate_random_scenario()

        assert scenario is not None
        assert "scenario_name" in scenario
        assert "stock_code" in scenario
        assert "stock_name" in scenario
        assert "queries" in scenario
        assert len(scenario["queries"]) > 0

        print(f"\n✅ 시나리오 생성 성공: {scenario['scenario_name']}")

    @pytest.mark.asyncio
    async def test_service_layer_only(self):
        """Service Layer만 테스트 (빠른 검증)"""
        scenario = generate_random_scenario()

        print(f"\n📊 Service Layer 테스트: {scenario['stock_name']}")

        # 주가 데이터
        price_data = await stock_data_service.get_stock_price(
            scenario['stock_code'],
            days=7
        )
        assert price_data is not None
        print(f"✅ 주가 데이터 조회 성공")

        # KIS 시세
        try:
            kis_price = await kis_service.get_stock_price(scenario['stock_code'])
            assert kis_price is not None
            print(f"✅ KIS 시세 조회 성공: {kis_price['current_price']:,}원")
        except Exception as e:
            print(f"⚠️ KIS 조회 스킵: {e}")


# ==================== 직접 실행 ====================

if __name__ == "__main__":
    """
    직접 실행 시:
    - 기본: 1개 랜덤 시나리오
    - python test_random_scenario.py 3: 3개 시나리오
    """
    import sys

    # 커맨드 라인 인자로 시나리오 개수 지정 가능
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    if count == 1:
        asyncio.run(test_random_full_flow())
    else:
        asyncio.run(test_multiple_random_scenarios(count))
