"""
온보딩 관련 API

초기 스크리닝 및 AI 프로파일 생성
"""
import logging
import uuid
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.services.profile_generator import generate_ai_profile
from src.services.user_profile_service import user_profile_service
from src.models.database import get_db_context

logger = logging.getLogger(__name__)

router = APIRouter()


class RiskQuestion(BaseModel):
    """위험 성향 질문"""
    q: str
    a: str


class ScreeningAnswers(BaseModel):
    """스크리닝 설문 응답"""
    investment_goal: str = Field(
        description="투자 목표: long_term_growth | short_term_profit | stable_income"
    )
    investment_period: str = Field(
        description="투자 기간: less_than_1year | 1_to_3_years | 3_years_plus"
    )
    risk_questions: List[RiskQuestion] = Field(
        description="위험 성향 질문 응답 리스트"
    )
    preferred_sectors: List[str] = Field(
        default=[],
        description="관심 섹터 리스트 (예: 반도체, 배터리, 바이오)"
    )
    expected_trade_frequency: str = Field(
        description="예상 매매 빈도: daily | weekly | monthly | quarterly"
    )


class PortfolioItem(BaseModel):
    """포트폴리오 항목"""
    stock_code: str
    quantity: int
    avg_price: float


class OnboardingRequest(BaseModel):
    """온보딩 요청"""
    user_id: Optional[str] = None
    screening_answers: ScreeningAnswers
    portfolio_data: Optional[List[PortfolioItem]] = None


class OnboardingResponse(BaseModel):
    """온보딩 응답"""
    user_id: str
    profile: Dict[str, Any]
    message: str


@router.post("/screening", response_model=OnboardingResponse)
async def create_profile_from_screening(request: OnboardingRequest):
    """
    초기 스크리닝을 통한 AI 프로파일 생성

    **플로우:**
    1. 스크리닝 응답 분석
    2. 포트폴리오 패턴 분석 (있는 경우)
    3. LLM으로 투자 성향 프로파일 생성
    4. DB에 저장

    **예시 요청:**
    ```json
    {
      "user_id": "optional-uuid",
      "screening_answers": {
        "investment_goal": "long_term_growth",
        "investment_period": "3_years_plus",
        "risk_questions": [
          {"q": "시장 급락 시 행동은?", "a": "추가 매수"},
          {"q": "손실 허용 범위는?", "a": "10-20%"},
          {"q": "변동성 수용도는?", "a": "높음"}
        ],
        "preferred_sectors": ["반도체", "배터리", "바이오"],
        "expected_trade_frequency": "weekly"
      },
      "portfolio_data": [
        {"stock_code": "005930", "quantity": 10, "avg_price": 70000},
        {"stock_code": "000660", "quantity": 5, "avg_price": 140000}
      ]
    }
    ```

    **응답:**
    - user_id: 생성된 사용자 ID
    - profile: AI가 생성한 투자 성향 프로파일
    - message: 환영 메시지
    """
    logger.info("🎯 [Onboarding] 스크리닝 시작")

    # 1. user_id 생성 또는 확인
    if request.user_id:
        try:
            user_uuid = uuid.UUID(request.user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user_id format")
    else:
        user_uuid = uuid.uuid4()

    user_id_str = str(user_uuid)

    # 2. 스크리닝 데이터 변환
    screening_answers_dict = request.screening_answers.dict()

    portfolio_data_dict = None
    if request.portfolio_data:
        portfolio_data_dict = [item.dict() for item in request.portfolio_data]

    # 3. AI 프로파일 생성
    try:
        generated_profile = await generate_ai_profile(
            screening_answers=screening_answers_dict,
            portfolio_data=portfolio_data_dict
        )
    except Exception as e:
        logger.error(f"❌ [Onboarding] 프로파일 생성 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"프로파일 생성 실패: {str(e)}"
        )

    # 4. DB 저장
    with get_db_context() as db:
        try:
            # 기존 프로파일 확인
            existing_profile = user_profile_service.get_user_profile(user_uuid, db)

            # 업데이트
            updated_profile = user_profile_service.update_user_profile(
                user_id=user_uuid,
                updates=generated_profile,
                db=db
            )

            logger.info(f"✅ [Onboarding] 프로파일 저장 완료: {user_id_str}")

        except Exception as e:
            logger.error(f"❌ [Onboarding] DB 저장 실패: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"DB 저장 실패: {str(e)}"
            )

    # 5. 응답 생성
    expertise_level = generated_profile["expertise_level"]
    investment_style = generated_profile["investment_style"]

    welcome_message = f"""🎉 환영합니다!

당신의 투자 프로파일이 생성되었습니다:
- 투자 경험: {expertise_level}
- 투자 성향: {investment_style}
- 선호 섹터: {', '.join(generated_profile['preferred_sectors'])}

{generated_profile['llm_generated_profile']}

이제 AI가 당신에게 맞는 맞춤형 투자 정보를 제공할 거예요!
"""

    return OnboardingResponse(
        user_id=user_id_str,
        profile=generated_profile,
        message=welcome_message
    )


@router.get("/profile/{user_id}")
async def get_investment_profile(user_id: str):
    """
    사용자 투자 프로파일 조회

    **응답:**
    - user_id: 사용자 ID
    - profile_summary: 프로파일 요약
    - key_characteristics: 주요 특징
    - llm_generated_profile: AI 생성 자연어 프로파일
    - last_updated: 마지막 업데이트 시각
    """
    logger.info(f"📋 [Onboarding] 프로파일 조회: {user_id}")

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")

    with get_db_context() as db:
        try:
            profile = user_profile_service.get_user_profile(user_uuid, db)
        except Exception as e:
            logger.error(f"❌ [Onboarding] 프로파일 조회 실패: {e}")
            raise HTTPException(
                status_code=404,
                detail=f"프로파일을 찾을 수 없습니다: {user_id}"
            )

    # 프로파일 요약 생성
    expertise = profile.get("expertise_level", "intermediate")
    style = profile.get("investment_style", "moderate")
    trading = profile.get("trading_style", "long_term")

    profile_summary = f"{style} {expertise} 투자자 | {trading} 성향"

    # 주요 특징 추출
    key_characteristics = []

    sectors = profile.get("preferred_sectors", [])
    if sectors:
        key_characteristics.append(f"{'/'.join(sectors[:3])} 선호")

    risk = profile.get("risk_tolerance", "medium")
    key_characteristics.append(f"위험 수용도: {risk}")

    concentration = profile.get("portfolio_concentration", 0.5)
    concentration_desc = "집중 투자" if concentration > 0.5 else "분산 투자"
    key_characteristics.append(concentration_desc)

    return {
        "user_id": user_id,
        "profile_summary": profile_summary,
        "key_characteristics": key_characteristics,
        "llm_generated_profile": profile.get("llm_generated_profile", ""),
        "last_updated": profile.get("last_updated"),
        "full_profile": profile
    }
