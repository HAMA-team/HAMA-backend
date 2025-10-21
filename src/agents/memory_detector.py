"""
Memory Detector - 대화 중 프로파일 업데이트 신호 감지

사용자 대화에서 선호도 변화를 감지하여 프로파일 자동 업데이트
"""
import json
import logging
from typing import Optional, List, Dict, Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from src.config.settings import settings

logger = logging.getLogger(__name__)


class ProfileUpdate(BaseModel):
    """프로파일 업데이트 신호"""
    update_needed: bool
    field: Optional[str] = None  # "preferred_sectors", "wants_explanations", etc.
    value: Optional[Any] = None
    reasoning: str


async def detect_profile_updates(
    user_message: str,
    current_profile: Dict[str, Any],
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> Optional[ProfileUpdate]:
    """
    대화에서 프로파일 업데이트 신호 감지

    Args:
        user_message: 사용자 최신 메시지
        current_profile: 현재 프로파일
        conversation_history: 대화 히스토리

    Returns:
        ProfileUpdate 또는 None
    """
    if conversation_history is None:
        conversation_history = []

    logger.info(f"🧠 [MemoryDetector] 신호 감지 시작: {user_message[:50]}...")

    detector_prompt = ChatPromptTemplate.from_messages([
        ("system", """당신은 사용자 대화에서 투자 선호도 변화를 감지하는 전문가입니다.

**임무:**
사용자의 대화에서 다음과 같은 신호를 감지하세요:

1. **선호 섹터 변화**
   - "나는 반도체에 관심 많아" → preferred_sectors에 "반도체" 추가
   - "배터리는 이제 별로야" → preferred_sectors에서 "배터리" 제거
   - value: 업데이트된 섹터 리스트

2. **답변 깊이 선호**
   - "DCF는 너무 복잡해" → preferred_depth = "detailed" (comprehensive 제외)
   - "자세히 설명해줘" → preferred_depth = "comprehensive"
   - "간단히만 알려줘" → preferred_depth = "brief"

3. **설명 필요성**
   - "PER이 뭐야?" → wants_explanations = True
   - "용어 설명 불필요해" → wants_explanations = False

4. **비유 선호**
   - "쉽게 비유로 설명해줘" → wants_analogies = True
   - "비유 말고 팩트만" → wants_analogies = False

5. **기술적 수준**
   - "지표만 간단히 보여줘" → technical_level = "intermediate"
   - "민감도 분석까지 해줘" → technical_level = "advanced"
   - "기본만 알려줘" → technical_level = "basic"

6. **투자 성향 변화**
   - "요즘 보수적으로 가려고" → investment_style = "conservative"
   - "공격적으로 투자하고 싶어" → investment_style = "aggressive"

7. **리스크 허용도**
   - "변동성 괜찮아" → risk_tolerance = "high"
   - "안정적으로 가고 싶어" → risk_tolerance = "low"

**현재 프로파일:**
{current_profile}

**출력 형식:**
JSON으로 다음을 반환:
- update_needed: bool (업데이트 필요 여부)
- field: str (업데이트할 필드명, 예: "preferred_sectors", "wants_explanations")
- value: Any (새 값)
- reasoning: str (판단 근거)

**주의:**
- 명확한 신호가 없으면 update_needed = False
- 애매한 경우 업데이트하지 말 것
- preferred_sectors의 경우, value는 업데이트된 전체 리스트를 반환
  예: 현재 ["반도체"], "배터리에 관심" → value: ["반도체", "배터리"]
"""),
        ("human", """**사용자 메시지:**
{user_message}

**이전 대화:**
{conversation_history}

프로파일 업데이트가 필요한지 판단하세요.""")
    ])

    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        api_key=settings.OPENAI_API_KEY
    )

    structured_llm = llm.with_structured_output(ProfileUpdate)

    try:
        # 대화 히스토리 포맷팅
        history_text = "\n".join([
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
            for msg in conversation_history[-5:]  # 최근 5턴
        ])

        if not history_text:
            history_text = "(없음)"

        result = await structured_llm.ainvoke(
            detector_prompt.format_messages(
                user_message=user_message,
                current_profile=json.dumps(current_profile, ensure_ascii=False, indent=2),
                conversation_history=history_text
            )
        )

        if result.update_needed:
            logger.info(f"✅ [MemoryDetector] 업데이트 신호 감지:")
            logger.info(f"   - field: {result.field}")
            logger.info(f"   - value: {result.value}")
            logger.info(f"   - reasoning: {result.reasoning}")
            return result
        else:
            logger.info(f"ℹ️ [MemoryDetector] 업데이트 불필요")
            return None

    except Exception as e:
        logger.error(f"❌ [MemoryDetector] 에러: {e}")
        return None


async def apply_profile_update(
    user_id: str,
    update: ProfileUpdate,
    user_profile_service,
    db
) -> Dict[str, Any]:
    """
    감지된 프로파일 업데이트 적용

    Args:
        user_id: 사용자 ID
        update: ProfileUpdate 객체
        user_profile_service: UserProfileService 인스턴스
        db: DB 세션

    Returns:
        업데이트된 프로파일
    """
    if not update or not update.update_needed:
        logger.warning("⚠️ [MemoryDetector] 업데이트 불필요")
        return {}

    logger.info(f"🔄 [MemoryDetector] 프로파일 업데이트 적용: {update.field} = {update.value}")

    try:
        updated_profile = await user_profile_service.update_user_profile(
            user_id=user_id,
            updates={update.field: update.value},
            db=db
        )

        logger.info(f"✅ [MemoryDetector] 프로파일 업데이트 완료")
        return updated_profile

    except Exception as e:
        logger.error(f"❌ [MemoryDetector] 업데이트 실패: {e}")
        return {}
