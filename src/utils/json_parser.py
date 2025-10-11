"""
LLM 응답에서 안전하게 JSON 파싱하는 유틸리티

Gemini와 Claude의 응답 형식 차이를 처리
"""
import json
import logging

logger = logging.getLogger(__name__)


def safe_json_parse(content: str, logger_name: str = "LLM") -> dict:
    """
    안전한 JSON 파싱 (Gemini/Claude 호환)

    Args:
        content: LLM 응답 내용
        logger_name: 로그에 표시할 이름

    Returns:
        dict: 파싱된 JSON 객체

    Raises:
        ValueError: JSON 파싱 실패 시

    Note:
        - Gemini는 때때로 불완전한 JSON 또는 이스케이프 문제가 있는 응답 반환
        - Claude는 보통 ```json ... ``` 마커로 감싸서 반환
        - 빈 응답이나 닫는 마커가 없는 경우도 처리
    """
    if not content or len(content.strip()) == 0:
        raise ValueError("빈 응답 수신")

    # 1. ```json ... ``` 마커 제거
    if "```json" in content:
        json_start = content.find("```json") + 7
        json_end = content.find("```", json_start)
        if json_end == -1:
            # 닫는 마커가 없는 경우
            json_str = content[json_start:].strip()
        else:
            json_str = content[json_start:json_end].strip()
    elif "```" in content:
        json_start = content.find("```") + 3
        json_end = content.find("```", json_start)
        if json_end == -1:
            json_str = content[json_start:].strip()
        else:
            json_str = content[json_start:json_end].strip()
    else:
        json_str = content.strip()

    # 2. JSON 파싱 시도
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"⚠️ [{logger_name}] JSON 파싱 실패: {e}")
        logger.error(f"   원본 내용 (처음 200자): {json_str[:200]}")

        # 3. 대안: 마지막 완전한 객체만 추출 시도
        last_brace = json_str.rfind("}")
        if last_brace != -1:
            json_str_trimmed = json_str[:last_brace + 1]
            try:
                result = json.loads(json_str_trimmed)
                logger.info(f"✅ [{logger_name}] 부분 JSON 파싱 성공 (마지막 중괄호까지)")
                return result
            except:
                pass

        raise ValueError(f"JSON 파싱 불가: {e}")
