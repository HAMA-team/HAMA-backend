"""
Trading Agent Intent Classifier 프롬프트
"""
from typing import Optional, Dict
from ..utils import build_prompt


def build_trading_intent_classifier_prompt(
    query: str,
    user_profile: Optional[Dict] = None,
    research_result: Optional[Dict] = None,
) -> str:
    """
    Trading Agent용 Intent Classifier 프롬프트

    Args:
        query: 사용자 쿼리
        user_profile: 사용자 프로필 (옵션)
        research_result: Research Agent 결과 (옵션)

    Returns:
        Claude 4.x 구조화 프롬프트
    """
    context = {}

    if user_profile:
        context["automation_level"] = user_profile.get("automation_level", 2)
        context["risk_tolerance"] = user_profile.get("risk_tolerance", "moderate")

    if research_result:
        context["has_research"] = True
        context["research_consensus"] = research_result.get("consensus", "NEUTRAL")

    task = f"""<role>당신은 매매 작업 의도를 분석하는 전문가입니다.</role>

<query>{query}</query>

<instructions>
쿼리를 분석하여 주문 유형, 분석 깊이, 필요한 정보를 추출하세요.

<order_types>
- buy: 매수 주문
- sell: 매도 주문
- unknown: 불명확
</order_types>

<depth_levels>
- quick: 즉시 실행 (명확한 주문, 분석 최소화)
- standard: 표준 분석 (매수/매도 점수)
- comprehensive: 종합 분석 (전략 + 리스크/리워드)
</depth_levels>

<available_specialists>
- buy_specialist: 매수 점수 (1-10점)
- sell_specialist: 매도 판단
- risk_reward_specialist: 손절가/목표가
</available_specialists>

<extraction_rules>
extracted_info에서 다음 정보를 추출하세요:
- stock_code: 6자리 종목 코드 (예: "005930")
- quantity: 수량 (숫자 또는 "all")
- order_price: 지정가 (있는 경우만)

추출 불가능하면 null 설정
</extraction_rules>

<decision_logic>
1. "~주 매수" → quick (즉시 실행)
2. "~사도 될까?" → comprehensive (분석 필요)
3. "매수" → buy_specialist + risk_reward
4. "매도" → sell_specialist
</decision_logic>
</instructions>"""

    output_format = """{
  "order_type": "buy",
  "depth": "standard",
  "focus_areas": ["trade_preparation", "buy_analysis", "risk_reward"],
  "specialists": ["buy_specialist", "risk_reward_specialist"],
  "extracted_info": {
    "stock_code": "005930",
    "quantity": 10,
    "order_price": null
  },
  "reasoning": "매수 주문 요청. 매수 타당성 분석 및 손절가/목표가 계산 필요.",
  "confidence": 0.85
}"""

    examples = [
        {
            "input": "삼성전자 10주 매수해줘",
            "output": """{
  "order_type": "buy",
  "depth": "quick",
  "focus_areas": ["trade_preparation", "execution"],
  "specialists": [],
  "extracted_info": {
    "stock_code": "005930",
    "quantity": 10,
    "order_price": null
  },
  "reasoning": "명확한 매수 주문. 즉시 실행 가능.",
  "confidence": 0.95
}"""
        },
        {
            "input": "삼성전자 지금 사도 될까?",
            "output": """{
  "order_type": "buy",
  "depth": "comprehensive",
  "focus_areas": ["trade_preparation", "buy_analysis", "risk_reward"],
  "specialists": ["buy_specialist", "risk_reward_specialist"],
  "extracted_info": {
    "stock_code": "005930",
    "quantity": null,
    "order_price": null
  },
  "reasoning": "매수 타이밍 확인 요청. 종합 분석 필요 (매수 점수 + 손절가/목표가).",
  "confidence": 0.90
}"""
        },
        {
            "input": "NAVER 전량 매도",
            "output": """{
  "order_type": "sell",
  "depth": "standard",
  "focus_areas": ["trade_preparation", "sell_analysis", "execution"],
  "specialists": ["sell_specialist"],
  "extracted_info": {
    "stock_code": "035420",
    "quantity": "all",
    "order_price": null
  },
  "reasoning": "전량 매도 주문. 매도 근거 분석 후 실행.",
  "confidence": 0.85
}"""
        },
        {
            "input": "카카오 70,000원에 20주 매수",
            "output": """{
  "order_type": "buy",
  "depth": "quick",
  "focus_areas": ["trade_preparation", "execution"],
  "specialists": [],
  "extracted_info": {
    "stock_code": "035720",
    "quantity": 20,
    "order_price": 70000
  },
  "reasoning": "지정가 매수 주문. 가격과 수량 명확하므로 즉시 실행.",
  "confidence": 0.95
}"""
        }
    ]

    guidelines = """1. order_type은 buy/sell/unknown 중 하나
2. quick depth는 specialists 빈 배열 (즉시 실행)
3. comprehensive depth는 모든 specialists 포함
4. extracted_info는 최선을 다해 추출 (null 허용)
5. stock_code는 6자리 숫자 형식
6. quantity는 "all"(전량) 가능
7. confidence는 추출 정보 완전성 반영"""

    return build_prompt(
        role="Trading Intent Classifier - 매매 작업 의도 분석 전문가",
        context=context,
        input_data=query,
        task=task,
        output_format=output_format,
        examples=examples,
        guidelines=guidelines,
    )


def build_trading_planner_prompt(
    query: str,
    order_type: str,
    analysis_depth: str,
    stock_code: Optional[str] = None,
) -> str:
    """
    Trading Agent용 Planner 프롬프트

    Args:
        query: 사용자 쿼리
        order_type: 주문 유형
        analysis_depth: 분석 깊이
        stock_code: 종목 코드 (옵션)

    Returns:
        Claude 4.x 구조화 프롬프트
    """
    context = {
        "order_type": order_type,
        "analysis_depth": analysis_depth,
    }

    if stock_code:
        context["stock_code"] = stock_code

    task = f"""매매 작업 계획을 수립하세요.

쿼리: "{query}"
주문 유형: {order_type}
분석 깊이: {analysis_depth}

계획 수립 기준:

**1. Specialist 선택**:
Available Specialists:
- prepare_trade: 거래 준비 (항상 필요)
- buy_specialist: 매수 점수 산정 (buy order only)
- sell_specialist: 매도 판단 (sell order only)
- risk_reward_specialist: 손절가/목표가 계산
- approval_trade: HITL 승인 (자동화 레벨에 따라)
- execute_trade: 주문 실행 (항상 마지막)

**2. 실행 순서**:
항상 sequential (매매는 순차적)

**3. 예상 시간**:
- prepare_trade: 5초
- buy_specialist: 10초
- sell_specialist: 10초
- risk_reward_specialist: 10초
- approval_trade: 0초 (사용자 대기)
- execute_trade: 5초

Order Type별 기본 전략:
- **buy + quick**: prepare → execute (10초)
- **buy + standard**: prepare → buy_specialist → risk_reward → approval → execute (30초)
- **buy + comprehensive**: prepare → buy_specialist → risk_reward → approval → execute (30초)
- **sell + quick**: prepare → execute (10초)
- **sell + standard**: prepare → sell_specialist → approval → execute (20초)"""

    output_format = """{
  "specialists": ["prepare_trade", "buy_specialist", "risk_reward_specialist", "approval_trade", "execute_trade"],
  "execution_order": "sequential",
  "estimated_time": "30",
  "reasoning": "매수 주문이므로 매수 분석 및 리스크/리워드 계산 필요. HITL 승인 후 실행.",
  "skip_steps": ["sell_specialist"]
}"""

    examples = [
        {
            "input": "buy, quick depth",
            "output": """{
  "specialists": ["prepare_trade", "execute_trade"],
  "execution_order": "sequential",
  "estimated_time": "10",
  "reasoning": "즉시 매수 주문. 분석 생략하고 바로 실행.",
  "skip_steps": ["buy_specialist", "sell_specialist", "risk_reward_specialist", "approval_trade"]
}"""
        },
        {
            "input": "sell, standard depth",
            "output": """{
  "specialists": ["prepare_trade", "sell_specialist", "approval_trade", "execute_trade"],
  "execution_order": "sequential",
  "estimated_time": "20",
  "reasoning": "매도 주문이므로 매도 근거 분석 후 승인 및 실행.",
  "skip_steps": ["buy_specialist", "risk_reward_specialist"]
}"""
        }
    ]

    guidelines = """1. prepare_trade와 execute_trade는 항상 포함
2. buy_specialist는 buy order만, sell_specialist는 sell order만
3. quick depth는 specialist 최소화
4. approval_trade는 자동화 레벨에 따라 포함 (일단 항상 포함)
5. execution_order는 항상 sequential"""

    return build_prompt(
        role="Trading Planner - 매매 작업 계획 수립 전문가",
        context=context,
        task=task,
        output_format=output_format,
        examples=examples,
        guidelines=guidelines,
    )
