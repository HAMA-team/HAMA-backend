"""
Prompt Building Utilities

Claude 4.x 모델에 최적화된 프롬프트 빌딩 유틸리티
"""
import json
import re
from typing import Any, Dict, List, Optional


def build_prompt(
    role: str,
    context: Optional[Dict[str, Any]] = None,
    input_data: Optional[str] = None,
    task: str = "",
    output_format: Optional[str] = None,
    examples: Optional[List[Dict[str, str]]] = None,
    guidelines: Optional[str] = None,
) -> str:
    """
    Claude 4.x 프롬프트 템플릿 빌더

    Args:
        role: LLM의 역할 (예: "투자 분석 전문가")
        context: 컨텍스트 정보 (사용자 프로필, 히스토리 등)
        input_data: 입력 데이터 (쿼리, 분석 대상 등)
        task: 수행할 작업 설명
        output_format: 출력 형식 (JSON 스키마, 마크다운 템플릿 등)
        examples: Few-shot 예시 리스트
        guidelines: 추가 가이드라인

    Returns:
        구조화된 프롬프트
    """
    prompt_parts = []

    # 역할 정의
    prompt_parts.append(f"당신은 {role}입니다.")

    # Context (선택적)
    if context:
        context_str = "\n".join([f"- {k}: {v}" for k, v in context.items()])
        prompt_parts.append(f"\n<context>\n{context_str}\n</context>")

    # Input (선택적)
    if input_data:
        prompt_parts.append(f"\n<input>\n{input_data}\n</input>")

    # Task (필수)
    if task:
        prompt_parts.append(f"\n<task>\n{task}\n</task>")

    # Output Format (선택적)
    if output_format:
        prompt_parts.append(f"\n<output_format>\n{output_format}\n</output_format>")

    # Examples (선택적)
    if examples:
        examples_str = "\n\n".join([
            f"입력: {ex['input']}\n출력: {ex['output']}"
            for ex in examples
        ])
        prompt_parts.append(f"\n<examples>\n{examples_str}\n</examples>")

    # Guidelines (선택적)
    if guidelines:
        prompt_parts.append(f"\n<guidelines>\n{guidelines}\n</guidelines>")

    return "\n".join(prompt_parts)


def parse_llm_json(response: str) -> Dict[str, Any]:
    """
    LLM 응답에서 JSON 추출 및 파싱

    LLM이 마크다운 코드 블록이나 추가 텍스트와 함께 JSON을 반환할 수 있으므로
    다양한 형식을 처리합니다.

    Args:
        response: LLM 응답 텍스트

    Returns:
        파싱된 JSON 딕셔너리

    Raises:
        ValueError: JSON 파싱 실패 시
    """
    # 1. 코드 블록 제거 시도
    # ```json\n{...}\n``` 또는 ```\n{...}\n``` 형식
    code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
    match = re.search(code_block_pattern, response, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        json_str = response

    # 2. 중괄호 또는 대괄호로 시작하는 JSON 찾기
    # 앞뒤 텍스트 제거
    json_str = json_str.strip()

    # JSON 객체 또는 배열 찾기
    if json_str.startswith("{"):
        # 객체 찾기
        try:
            # 첫 번째 { 부터 마지막 } 까지
            start = json_str.index("{")
            # 마지막 }의 위치를 역순으로 찾기
            end = json_str.rindex("}") + 1
            json_str = json_str[start:end]
        except ValueError:
            pass
    elif json_str.startswith("["):
        # 배열 찾기
        try:
            start = json_str.index("[")
            end = json_str.rindex("]") + 1
            json_str = json_str[start:end]
        except ValueError:
            pass

    # 3. JSON 파싱
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON from LLM response: {e}\nResponse: {response[:200]}...")


def add_formatting_guidelines() -> str:
    """
    Claude 4.x 마크다운 최소화 가이드라인

    Returns:
        포맷팅 가이드라인 텍스트
    """
    return """
<formatting_guidelines>
보고서나 분석을 작성할 때:
- 완전한 문단과 문장으로 작성하세요
- **굵게**, *이탤릭*을 과도하게 사용하지 마세요
- 목록(-)은 진정으로 별개의 항목을 나열할 때만 사용하세요
- 대부분의 내용은 자연스러운 산문 형태로 작성하세요
- 코드는 ```로 감싸고, 중요한 수치는 인라인 코드(``)로 표시하세요

당신의 목표는 독자를 아이디어를 통해 자연스럽게 안내하는 읽기 쉬운 텍스트입니다.
</formatting_guidelines>
"""


def add_parallel_tool_calls_guideline() -> str:
    """
    Claude 4.x 병렬 도구 호출 가이드라인

    Returns:
        병렬 도구 호출 가이드라인 텍스트
    """
    return """
<parallel_tool_calls>
여러 도구를 호출할 때 도구 호출 간 종속성이 없으면 모든 독립적인 도구 호출을 병렬로 실행하세요.

예시:
- 여러 종목 동시 분석 → 병렬 호출
- 분석 후 전략 수립 → 순차 호출

속도와 효율성을 위해 병렬 도구 호출을 최대한 활용하세요.
</parallel_tool_calls>
"""


def add_thinking_guidance() -> str:
    """
    Claude 4.x Extended Thinking 가이드라인

    Returns:
        Thinking 가이드라인 텍스트
    """
    return """
<thinking_guidance>
도구 결과를 받은 후, 그 품질을 신중하게 반영하고 진행하기 전에 최적의 다음 단계를 결정하세요.

중간 결과를 평가하고 다음 액션을 최적화하세요:
- 데이터 품질이 낮으면 → 추가 데이터 수집
- 분석 결과가 상충하면 → 그 이유 탐구
- 임계값 도달 → 다음 단계 진행

항상 사고 과정을 거쳐 최선의 결정을 내리세요.
</thinking_guidance>
"""
