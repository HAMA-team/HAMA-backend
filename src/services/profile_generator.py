"""
AI 프로파일 생성 서비스

스크리닝 응답 + 포트폴리오 분석으로 사용자 투자 성향 프로파일 자동 생성
"""
import json
import logging
from typing import Optional, List, Dict, Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from src.config.settings import settings

logger = logging.getLogger(__name__)


class GeneratedProfile(BaseModel):
    """AI 생성 프로파일 스키마"""
    expertise_level: str  # beginner | intermediate | expert
    investment_style: str  # conservative | moderate | aggressive
    risk_tolerance: str  # low | medium | high
    preferred_sectors: List[str]
    trading_style: str  # short_term | long_term
    portfolio_concentration: float  # 0.0-1.0
    technical_level: str  # basic | intermediate | advanced
    preferred_depth: str  # brief | detailed | comprehensive
    wants_explanations: bool
    wants_analogies: bool
    llm_generated_profile: str  # 자연어 프로파일 (200자 이내)


def analyze_portfolio_pattern(portfolio_data: List[Dict[str, Any]]) -> str:
    """
    포트폴리오 패턴 분석

    Args:
        portfolio_data: 보유 종목 리스트
            예: [{"stock_code": "005930", "quantity": 10, "avg_price": 70000}]

    Returns:
        자연어 분석 결과
    """
    if not portfolio_data:
        return "(포트폴리오 데이터 없음)"

    # 1. 종목 수
    stock_count = len(portfolio_data)

    # 2. 집중도 계산 (HHI - Herfindahl-Hirschman Index)
    total_value = sum(item["quantity"] * item["avg_price"] for item in portfolio_data)

    if total_value == 0:
        concentration = 0.0
    else:
        hhi = sum(
            ((item["quantity"] * item["avg_price"]) / total_value) ** 2
            for item in portfolio_data
        )
        concentration = hhi

    # 3. 분석 텍스트 생성
    concentration_desc = "집중 투자" if concentration > 0.5 else "분산 투자"

    analysis = f"""
포트폴리오 분석:
- 종목 수: {stock_count}개
- 집중도: {concentration:.2f} (0=완전분산, 1=완전집중)
- 투자 패턴: {concentration_desc}
- 총 투자액: {total_value:,.0f}원
"""

    return analysis.strip()


async def generate_ai_profile(
    screening_answers: Dict[str, Any],
    portfolio_data: Optional[List[Dict[str, Any]]] = None,
    config: Optional[RunnableConfig] = None,
) -> Dict[str, Any]:
    """
    스크리닝 응답 + 포트폴리오 데이터를 LLM으로 분석하여 프로파일 생성

    Args:
        screening_answers: 온보딩 설문 응답
            예: {
                "investment_goal": "long_term_growth",
                "investment_period": "3_years_plus",
                "risk_questions": [...],
                "preferred_sectors": ["반도체", "배터리"],
                "expected_trade_frequency": "주 1회"
            }
        portfolio_data: 기존 포트폴리오 (선택적)

    Returns:
        생성된 프로파일 (dict)
    """
    logger.info("🤖 [ProfileGenerator] AI 프로파일 생성 시작")

    # 1. 포트폴리오 분석
    portfolio_analysis = ""
    if portfolio_data:
        portfolio_analysis = analyze_portfolio_pattern(portfolio_data)
        logger.info(f"📊 [Portfolio Analysis]:\n{portfolio_analysis}")

    # 2. LLM 프롬프트 구성
    profile_prompt = ChatPromptTemplate.from_messages([
        ("system", """당신은 투자자 성향 분석 전문가입니다.

**임무:**
1. 스크리닝 응답 분석
2. 포트폴리오 보유 패턴 분석 (있는 경우)
3. 투자 성향 프로파일 생성

**출력 형식:**
JSON으로 다음 필드를 반환하세요:

- **expertise_level**: "beginner" | "intermediate" | "expert"
  - beginner: 투자 경험 1년 미만, 기본 용어 이해 필요
  - intermediate: 투자 경험 1-3년, 주요 지표 이해
  - expert: 투자 경험 3년 이상, DCF/밸류에이션 이해

- **investment_style**: "conservative" | "moderate" | "aggressive"
  - conservative: 안정적 수익, 낮은 변동성 선호
  - moderate: 균형잡힌 접근, 중간 위험
  - aggressive: 고위험 고수익, 변동성 수용

- **risk_tolerance**: "low" | "medium" | "high"
  - 손실 허용 범위, 변동성 수용도 기반

- **preferred_sectors**: list[str]
  - 관심 섹터 리스트

- **trading_style**: "short_term" | "long_term"
  - short_term: 단타, 스윙 (매매 빈도 주 3회 이상)
  - long_term: 장기 보유 (월 1회 이하)

- **portfolio_concentration**: 0.0-1.0
  - 포트폴리오 집중도 (0=완전분산, 1=완전집중)
  - 포트폴리오 데이터가 있으면 계산값 사용, 없으면 추정

- **technical_level**: "basic" | "intermediate" | "advanced"
  - basic: PER, PBR 정도만 이해
  - intermediate: ROE, 부채비율 등 주요 지표 이해
  - advanced: DCF, WACC, 민감도 분석 이해

- **preferred_depth**: "brief" | "detailed" | "comprehensive"
  - expertise_level에 따라 자동 설정
  - beginner → brief
  - intermediate → detailed
  - expert → comprehensive

- **wants_explanations**: bool
  - beginner → true (용어 설명 필요)
  - intermediate → false (핵심만)
  - expert → false

- **wants_analogies**: bool
  - beginner → true (비유 사용)
  - 그 외 → false

- **llm_generated_profile**: str (200자 이내)
  - 자연어로 사용자 투자 성향 요약
  - 예: "이 투자자는 장기 성장을 목표로 하며, 반도체와 배터리 섹터에 집중 투자하는 공격적 성향입니다..."

**분석 기준:**
1. investment_goal → investment_style 결정
2. risk_questions 응답 → risk_tolerance 결정
3. expected_trade_frequency → trading_style 결정
4. portfolio_data (있으면) → portfolio_concentration 계산
5. 종합 판단 → expertise_level, technical_level 결정
"""),
        ("human", """**스크리닝 응답:**
{screening_answers}

**포트폴리오 분석:**
{portfolio_analysis}

위 정보를 바탕으로 투자자 프로파일을 생성하세요.""")
    ])

    # 3. LLM 호출
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.3,
        api_key=settings.OPENAI_API_KEY
    )

    structured_llm = llm.with_structured_output(GeneratedProfile)
    profile_chain = profile_prompt | structured_llm

    try:
        prompt_inputs = {
            "screening_answers": json.dumps(
                screening_answers, ensure_ascii=False, indent=2
            ),
            "portfolio_analysis": portfolio_analysis or "(포트폴리오 데이터 없음)",
        }

        if config is not None:
            result = await profile_chain.ainvoke(prompt_inputs, config=config)
        else:
            result = await profile_chain.ainvoke(prompt_inputs)

        profile_dict = result.dict()

        logger.info(f"✅ [ProfileGenerator] 프로파일 생성 완료")
        logger.info(f"   - expertise_level: {profile_dict['expertise_level']}")
        logger.info(f"   - investment_style: {profile_dict['investment_style']}")
        logger.info(f"   - risk_tolerance: {profile_dict['risk_tolerance']}")
        logger.info(f"   - trading_style: {profile_dict['trading_style']}")

        return profile_dict

    except Exception as e:
        logger.error(f"❌ [ProfileGenerator] 에러: {e}")

        # Fallback: 기본 프로파일
        fallback_profile = {
            "expertise_level": "intermediate",
            "investment_style": "moderate",
            "risk_tolerance": "medium",
            "preferred_sectors": screening_answers.get("preferred_sectors", []),
            "trading_style": "long_term",
            "portfolio_concentration": 0.5,
            "technical_level": "intermediate",
            "preferred_depth": "detailed",
            "wants_explanations": True,
            "wants_analogies": False,
            "llm_generated_profile": f"기본 프로파일 (에러 발생: {str(e)})"
        }

        logger.warning(f"⚠️ [ProfileGenerator] Fallback 프로파일 사용")
        return fallback_profile
