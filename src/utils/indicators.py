"""
기술적 지표 계산 모듈

주가 데이터를 기반으로 각종 기술적 지표를 계산합니다.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """
    RSI (Relative Strength Index) 계산

    과매수/과매도 지표:
    - 70 이상: 과매수 (매도 시그널)
    - 30 이하: 과매도 (매수 시그널)

    Args:
        prices: 종가 시리즈
        period: RSI 계산 기간 (기본 14일)

    Returns:
        RSI 시리즈
    """
    delta = prices.diff()

    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_macd(
    prices: pd.Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Dict[str, pd.Series]:
    """
    MACD (Moving Average Convergence Divergence) 계산

    추세 전환 시그널:
    - MACD > Signal: 상승 추세
    - MACD < Signal: 하락 추세
    - MACD가 Signal을 상향 돌파: 매수 시그널 (골든 크로스)
    - MACD가 Signal을 하향 돌파: 매도 시그널 (데드 크로스)

    Args:
        prices: 종가 시리즈
        fast_period: 빠른 EMA 기간 (기본 12일)
        slow_period: 느린 EMA 기간 (기본 26일)
        signal_period: 시그널 라인 기간 (기본 9일)

    Returns:
        dict: {"macd": MACD 라인, "signal": 시그널 라인, "histogram": MACD 히스토그램}
    """
    ema_fast = prices.ewm(span=fast_period, adjust=False).mean()
    ema_slow = prices.ewm(span=slow_period, adjust=False).mean()

    macd = ema_fast - ema_slow
    signal = macd.ewm(span=signal_period, adjust=False).mean()
    histogram = macd - signal

    return {
        "macd": macd,
        "signal": signal,
        "histogram": histogram
    }


def calculate_bollinger_bands(
    prices: pd.Series,
    period: int = 20,
    num_std: float = 2.0
) -> Dict[str, pd.Series]:
    """
    Bollinger Bands 계산

    변동성 측정:
    - 밴드 폭이 좁아질 때: 변동성 축소, 큰 움직임 예상
    - 가격이 상단 밴드 터치: 과매수 가능성
    - 가격이 하단 밴드 터치: 과매도 가능성

    Args:
        prices: 종가 시리즈
        period: 이동평균 기간 (기본 20일)
        num_std: 표준편차 배수 (기본 2.0)

    Returns:
        dict: {"upper": 상단 밴드, "middle": 중간 밴드 (이동평균), "lower": 하단 밴드}
    """
    middle = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()

    upper = middle + (std * num_std)
    lower = middle - (std * num_std)

    return {
        "upper": upper,
        "middle": middle,
        "lower": lower
    }


def calculate_moving_averages(prices: pd.Series) -> Dict[str, float]:
    """
    이동평균선 계산

    Args:
        prices: 종가 시리즈

    Returns:
        dict: {"MA5": 5일선, "MA20": 20일선, "MA60": 60일선, "MA120": 120일선}
    """
    return {
        "MA5": prices.rolling(window=5).mean().iloc[-1] if len(prices) >= 5 else None,
        "MA20": prices.rolling(window=20).mean().iloc[-1] if len(prices) >= 20 else None,
        "MA60": prices.rolling(window=60).mean().iloc[-1] if len(prices) >= 60 else None,
        "MA120": prices.rolling(window=120).mean().iloc[-1] if len(prices) >= 120 else None,
    }


def calculate_volume_analysis(volume: pd.Series) -> Dict[str, Any]:
    """
    거래량 분석

    Args:
        volume: 거래량 시리즈

    Returns:
        dict: 거래량 통계 정보
    """
    avg_volume = volume.mean()
    current_volume = volume.iloc[-1]
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0

    return {
        "current_volume": int(current_volume),
        "avg_volume": int(avg_volume),
        "volume_ratio": round(volume_ratio, 2),
        "is_high_volume": volume_ratio > 1.5,  # 평균 대비 1.5배 이상
    }


def calculate_all_indicators(df: pd.DataFrame) -> Dict[str, Any]:
    """
    모든 기술적 지표를 한 번에 계산

    Args:
        df: 주가 데이터 DataFrame (Open, High, Low, Close, Volume 필수)

    Returns:
        dict: 모든 지표 계산 결과
    """
    if df is None or len(df) == 0:
        return {}

    prices = df["Close"]
    volume = df["Volume"]

    # RSI 계산
    rsi = calculate_rsi(prices)
    current_rsi = rsi.iloc[-1] if not rsi.empty else None

    # MACD 계산
    macd_data = calculate_macd(prices)
    current_macd = macd_data["macd"].iloc[-1] if not macd_data["macd"].empty else None
    current_signal = macd_data["signal"].iloc[-1] if not macd_data["signal"].empty else None
    current_histogram = macd_data["histogram"].iloc[-1] if not macd_data["histogram"].empty else None

    # Bollinger Bands 계산
    bb_data = calculate_bollinger_bands(prices)
    current_price = prices.iloc[-1]
    bb_upper = bb_data["upper"].iloc[-1] if not bb_data["upper"].empty else None
    bb_middle = bb_data["middle"].iloc[-1] if not bb_data["middle"].empty else None
    bb_lower = bb_data["lower"].iloc[-1] if not bb_data["lower"].empty else None

    # 이동평균선 계산
    ma_data = calculate_moving_averages(prices)

    # 거래량 분석
    volume_data = calculate_volume_analysis(volume)

    # 시그널 판단
    signals = []

    # RSI 시그널
    if current_rsi is not None:
        if current_rsi > 70:
            signals.append("RSI 과매수 (매도 고려)")
        elif current_rsi < 30:
            signals.append("RSI 과매도 (매수 고려)")

    # MACD 시그널
    if current_macd is not None and current_signal is not None:
        if current_histogram > 0:
            signals.append("MACD 상승 추세")
        else:
            signals.append("MACD 하락 추세")

    # Bollinger Bands 시그널
    if bb_upper is not None and bb_lower is not None:
        if current_price >= bb_upper:
            signals.append("볼린저 밴드 상단 터치 (과매수 가능성)")
        elif current_price <= bb_lower:
            signals.append("볼린저 밴드 하단 터치 (과매도 가능성)")

    # 이동평균 배열 시그널
    if all(ma is not None for ma in [ma_data["MA5"], ma_data["MA20"], ma_data["MA60"]]):
        if ma_data["MA5"] > ma_data["MA20"] > ma_data["MA60"]:
            signals.append("이동평균 정배열 (상승 추세)")
        elif ma_data["MA5"] < ma_data["MA20"] < ma_data["MA60"]:
            signals.append("이동평균 역배열 (하락 추세)")

    return {
        "rsi": {
            "value": round(current_rsi, 2) if current_rsi is not None else None,
            "signal": "과매수" if current_rsi and current_rsi > 70 else "과매도" if current_rsi and current_rsi < 30 else "중립"
        },
        "macd": {
            "macd": round(current_macd, 2) if current_macd is not None else None,
            "signal": round(current_signal, 2) if current_signal is not None else None,
            "histogram": round(current_histogram, 2) if current_histogram is not None else None,
            "trend": "상승" if current_histogram and current_histogram > 0 else "하락" if current_histogram else "중립"
        },
        "bollinger_bands": {
            "upper": round(bb_upper, 2) if bb_upper is not None else None,
            "middle": round(bb_middle, 2) if bb_middle is not None else None,
            "lower": round(bb_lower, 2) if bb_lower is not None else None,
            "current_price": round(current_price, 2),
            "position": "상단" if bb_upper and current_price >= bb_upper else "하단" if bb_lower and current_price <= bb_lower else "중간"
        },
        "moving_averages": {
            "MA5": round(ma_data["MA5"], 2) if ma_data["MA5"] is not None else None,
            "MA20": round(ma_data["MA20"], 2) if ma_data["MA20"] is not None else None,
            "MA60": round(ma_data["MA60"], 2) if ma_data["MA60"] is not None else None,
            "MA120": round(ma_data["MA120"], 2) if ma_data["MA120"] is not None else None,
        },
        "volume": volume_data,
        "signals": signals,
        "overall_trend": _determine_overall_trend(current_rsi, current_histogram, signals)
    }


def _determine_overall_trend(rsi: float, macd_histogram: float, signals: list) -> str:
    """
    전체 추세 판단

    Args:
        rsi: RSI 값
        macd_histogram: MACD 히스토그램 값
        signals: 시그널 리스트

    Returns:
        str: "강세", "약세", "중립"
    """
    bullish_count = 0
    bearish_count = 0

    # RSI
    if rsi is not None:
        if rsi < 30:
            bullish_count += 1
        elif rsi > 70:
            bearish_count += 1

    # MACD
    if macd_histogram is not None:
        if macd_histogram > 0:
            bullish_count += 1
        else:
            bearish_count += 1

    # 시그널 분석
    for signal in signals:
        if "상승" in signal or "매수" in signal or "정배열" in signal:
            bullish_count += 1
        elif "하락" in signal or "매도" in signal or "역배열" in signal:
            bearish_count += 1

    if bullish_count > bearish_count:
        return "강세"
    elif bearish_count > bullish_count:
        return "약세"
    else:
        return "중립"
