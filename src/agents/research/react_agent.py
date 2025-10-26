"""
Research Agent - ReAct 패턴 구현

Router의 depth_level과 user_profile에 따라 동적으로 에이전트 생성
"""
import logging
from typing import Optional

from langgraph.prebuilt import create_react_agent

from src.config.settings import settings
from src.utils.llm_factory import get_llm
from .tools import (
    get_stock_price,
    get_basic_ratios,
    get_financial_statement,
    get_company_info,
    calculate_dcf_valuation,
    get_sector_comparison,
)

logger = logging.getLogger(__name__)


def create_research_agent(
    depth_level: str = "detailed",
    user_profile: Optional[dict] = None
):
    """
    Router의 판단에 따라 Research Agent 생성

    Args:
        depth_level: "brief" | "detailed" | "comprehensive"
        user_profile: 사용자 프로파일 (선호 섹터, 투자 성향 등)

    Returns:
        create_react_agent로 생성된 에이전트
    """
    if user_profile is None:
        user_profile = {}

    # 프로파일 정보 추출
    preferred_sectors = user_profile.get("preferred_sectors", [])
    investment_style = user_profile.get("investment_style", "moderate")
    technical_level = user_profile.get("technical_level", "intermediate")

    # depth_level에 따른 프롬프트 조절
    if depth_level == "brief":
        system_message = f"""당신은 종목 분석 전문가입니다.

**목표:** 사용자 질문에 간결하고 명확하게 답변

**도구 선택 원칙:**
- 최소한의 도구만 사용
- get_stock_price (현재가 확인)
- get_basic_ratios (핵심 지표 1-2개만)
- 빠른 응답 우선

**출력 형식:**
- 1-2문장으로 간결하게
- 핵심 지표 1-2개만 언급
- 전문 용어 최소화
- 명확한 결론 (BUY/HOLD/SELL)

**예시:**
"삼성전자는 현재 75,000원으로, PER 8.5로 업종 평균보다 저평가되어 있습니다. 매수 고려 가능합니다."
"""

    elif depth_level == "detailed":
        system_message = f"""당신은 종목 분석 전문가입니다.

**목표:** 근거와 함께 상세한 분석 제공

**도구 선택 원칙:**
- 필요한 도구를 자율적으로 선택
- 기본: get_stock_price + get_basic_ratios
- 필요 시: get_financial_statement (최근 3년)
- 업종 비교: get_sector_comparison (선호 섹터가 있으면 활용)

**사용자 정보:**
- 선호 섹터: {', '.join(preferred_sectors) if preferred_sectors else '없음'}
- 투자 성향: {investment_style}
- 기술적 수준: {technical_level}

**출력 형식:**
- 핵심 지표 3-5개
- 근거 포함 (왜 긍정적/부정적인지)
- 선호 섹터와 비교 (있는 경우)
- 투자 의견 (BUY/HOLD/SELL) + 이유

**예시:**
"삼성전자 분석:
- 현재가: 75,000원
- PER 8.5 (업종 평균 12 대비 저평가)
- PBR 1.2 (적정 수준)
- ROE 15.3% (업종 평균 12% 대비 우수)

반도체 섹터 평균 대비 저평가 상태입니다. 최근 실적 개선 추세를 고려하면 매수 타이밍으로 판단됩니다."
"""

    else:  # comprehensive
        system_message = f"""당신은 종목 분석 전문가입니다.

**목표:** 전문가 수준의 심층 분석 제공

**도구 선택 원칙:**
- 모든 필요한 도구 적극 활용
- get_financial_statement (최소 3년, 가능하면 5년)
- calculate_dcf_valuation (DCF 요청 시)
- get_sector_comparison (업종 비교)
- 기술적 지표 추가 분석

**출력 형식:**
- 모든 주요 재무 지표
- 계산 과정 포함 (DCF, WACC 등)
- 민감도 분석
- 대안 시나리오 (Bull/Bear)
- 정량적 근거

**분석 구조:**
1. **기업 개요**
2. **재무 분석** (3-5년 추세)
3. **밸류에이션** (DCF, PER/PBR/ROE)
4. **업종 비교**
5. **투자 의견** (목표가, 상승여력, 리스크)

**예시:**
"삼성전자 심층 분석:

## 1. 기업 개요
- 종목코드: 005930
- 업종: 반도체
- 시가총액: 450조원

## 2. 재무 분석 (2021-2023)
- 매출액: 270조 → 300조 (CAGR +5%)
- 영업이익률: 12% → 15% (개선 추세)
- ROE: 12% → 15.3% (우수)

## 3. 밸류에이션
- DCF 적정가: 85,000원 (WACC 8%, g 3%)
- 민감도 분석: WACC 7-9% 범위에서 78,000-92,000원
- 현재가 75,000원 대비 상승여력 13%

## 4. 투자 의견
- 추천: BUY
- 목표가: 85,000원
- 리스크: 반도체 사이클 하락 가능성"
"""

    # LLM 생성 (환경 모드에 맞춰 provider/model 자동 선택)
    llm = get_llm(
        temperature=0.3,
        model=settings.llm_model_name,
    )

    # 도구 리스트 (depth_level에 따라 조절 가능)
    tools = [
        get_stock_price,
        get_basic_ratios,
        get_company_info,
    ]

    # detailed 이상이면 재무제표 추가
    if depth_level in ["detailed", "comprehensive"]:
        tools.append(get_financial_statement)

    # comprehensive이면 DCF, 섹터 비교 추가
    if depth_level == "comprehensive":
        tools.append(calculate_dcf_valuation)

    # 선호 섹터가 있으면 섹터 비교 도구 추가
    if preferred_sectors:
        tools.append(get_sector_comparison)

    logger.info(f"🔧 [Research/ReAct] 에이전트 생성: depth={depth_level}, tools={[t.name for t in tools]}")

    # ReAct Agent 생성
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_message  # prompt 파라미터 사용 (state_modifier 아님)
    )

    return agent
