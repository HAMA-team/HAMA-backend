"""
분석 깊이 레벨 정의 (Analysis Depth Levels)

사용자 쿼리와 성향에 따라 Research Agent의 worker를 동적으로 선택하여
비용과 시간을 절약하면서도 필요한 분석 깊이를 제공합니다.
"""
from typing import Dict, List, TypedDict


class AnalysisDepthConfig(TypedDict):
    """분석 깊이 설정"""
    name: str
    description: str
    required_workers: List[str]
    optional_workers: List[str]
    max_workers: int
    estimated_time: str
    use_cases: List[str]


# 3-Tier 분석 깊이 시스템 (UI 기반)
ANALYSIS_DEPTH_LEVELS: Dict[str, AnalysisDepthConfig] = {
    "brief": {  # quick → brief 변경
        "name": "빠른 분석",
        "description": "핵심 정보만 빠르게 확인",
        "required_workers": ["data"],
        "optional_workers": ["technical"],
        "max_workers": 3,
        "estimated_time": "10-20초",
        "use_cases": [
            "현재가 확인",
            "간단한 정보 조회",
            "빠른 판단",
            "가격 알림"
        ]
    },
    "detailed": {  # standard → detailed 변경
        "name": "표준 분석",
        "description": "균형잡힌 분석 (기본값)",
        "required_workers": ["data", "technical"],
        "optional_workers": ["trading_flow", "bull", "bear", "macro"],  # information 제거
        "max_workers": 5,
        "estimated_time": "30-45초",
        "use_cases": [
            "일반적인 종목 분석",
            "매매 판단",
            "포트폴리오 검토",
            "정기 모니터링"
        ]
    },
    "comprehensive": {
        "name": "종합 분석",
        "description": "모든 관점에서 심층 분석",
        "required_workers": ["data", "technical", "trading_flow"],  # information 제거
        "optional_workers": ["macro", "bull", "bear"],
        "max_workers": 6,  # information 제거로 7 → 6
        "estimated_time": "60-90초",
        "use_cases": [
            "신규 종목 발굴",
            "장기 투자 결정",
            "상세 리포트 생성",
            "매수/매도 최종 판단"
        ]
    }
}


# Scope 설정 (UI 기반 - 새로 추가)
class ScopeConfig(TypedDict):
    """분석 범위 설정"""
    name: str
    max_workers: int


SCOPE_CONFIGS: Dict[str, ScopeConfig] = {
    "key_points": {
        "name": "핵심만",
        "max_workers": 3,
    },
    "balanced": {
        "name": "균형잡힌",
        "max_workers": 5,
    },
    "wide_coverage": {
        "name": "광범위",
        "max_workers": 6,  # information 제거로 7 → 6
    }
}


# 쿼리 키워드 매핑 (intent classification에 사용)
QUERY_KEYWORDS_MAPPING = {
    "quick": [
        "빠르게", "간단히", "현재가", "지금", "얼마", "가격만",
        "간략히", "요약", "짧게"
    ],
    "comprehensive": [
        "상세히", "종합", "심층", "자세히", "전체", "모든", "완전히",
        "매수", "매도", "판단", "결정", "투자", "분석해줘"
    ],
    # "standard"는 키워드 없음 (기본값)
}


# Perspectives → Workers 매핑 (UI 기반)
PERSPECTIVE_TO_WORKER_MAPPING = {
    "macro": ["macro"],
    "fundamental": ["data"],  # data_worker가 재무제표 포함
    "technical": ["technical"],
    "flow": ["trading_flow"],
    "strategy": ["bull", "bear"],  # Strategy는 bull + bear 통합
    "bull_case": ["bull"],
    "bear_case": ["bear"],
}


# Focus Area 매핑 (특정 분석 영역 요청 시 - DEPRECATED)
FOCUS_AREA_WORKER_MAPPING = {
    "기술적": ["technical"],
    "차트": ["technical"],
    "지표": ["technical"],
    "이평선": ["technical"],

    "수급": ["trading_flow"],
    "거래": ["trading_flow"],
    "외국인": ["trading_flow"],
    "기관": ["trading_flow"],

    "거시경제": ["macro"],
    "금리": ["macro"],
    "환율": ["macro"],
    "경기": ["macro"],

    "재무": ["data"],
    "실적": ["data"],
    "매출": ["data"],
}


def get_default_depth() -> str:
    """기본 분석 깊이 반환"""
    return "detailed"  # standard → detailed 변경


def get_depth_config(depth: str) -> AnalysisDepthConfig:
    """
    분석 깊이 설정 조회

    Args:
        depth: 분석 깊이 ("brief" | "detailed" | "comprehensive")

    Returns:
        해당 깊이의 설정. 유효하지 않으면 "detailed" 반환
    """
    if depth not in ANALYSIS_DEPTH_LEVELS:
        return ANALYSIS_DEPTH_LEVELS["detailed"]  # standard → detailed 변경
    return ANALYSIS_DEPTH_LEVELS[depth]


def get_scope_config(scope: str) -> ScopeConfig:
    """
    분석 범위 설정 조회

    Args:
        scope: 분석 범위 ("key_points" | "balanced" | "wide_coverage")

    Returns:
        해당 범위의 설정. 유효하지 않으면 "balanced" 반환
    """
    if scope not in SCOPE_CONFIGS:
        return SCOPE_CONFIGS["balanced"]
    return SCOPE_CONFIGS[scope]


def classify_depth_by_keywords(query: str) -> str:
    """
    쿼리 키워드 기반 분석 깊이 분류 (간단한 규칙 기반)

    Note: DEPRECATED - planner_node에서 LLM 기반 분석으로 대체됨

    Args:
        query: 사용자 쿼리

    Returns:
        "brief" | "detailed" | "comprehensive"
    """
    query_lower = query.lower()

    # Brief 키워드 체크 (quick → brief)
    for keyword in QUERY_KEYWORDS_MAPPING.get("brief", QUERY_KEYWORDS_MAPPING.get("quick", [])):
        if keyword in query_lower:
            return "brief"

    # Comprehensive 키워드 체크
    for keyword in QUERY_KEYWORDS_MAPPING["comprehensive"]:
        if keyword in query_lower:
            return "comprehensive"

    # 기본값: detailed (standard → detailed)
    return "detailed"


def extract_focus_areas(query: str) -> List[str]:
    """
    쿼리에서 집중 영역 추출

    Args:
        query: 사용자 쿼리

    Returns:
        집중 영역 리스트 (예: ["technical", "trading_flow"])
    """
    query_lower = query.lower()
    focus_workers = set()

    for keyword, workers in FOCUS_AREA_WORKER_MAPPING.items():
        if keyword in query_lower:
            focus_workers.update(workers)

    return list(focus_workers)


def get_recommended_workers(
    depth: str,
    focus_areas: List[str] = None
) -> List[str]:
    """
    분석 깊이와 집중 영역을 기반으로 추천 worker 리스트 생성

    Args:
        depth: 분석 깊이
        focus_areas: 집중해야 할 worker 리스트

    Returns:
        추천 worker 리스트 (중복 제거됨)
    """
    config = get_depth_config(depth)
    workers = config["required_workers"].copy()

    # Focus areas가 있으면 우선 추가
    if focus_areas:
        for worker in focus_areas:
            if worker not in workers and len(workers) < config["max_workers"]:
                workers.append(worker)

    # Optional workers 추가 (max_workers까지)
    for worker in config["optional_workers"]:
        if worker not in workers and len(workers) < config["max_workers"]:
            workers.append(worker)

    return workers
