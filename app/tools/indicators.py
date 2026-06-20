import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


def _last(series: Optional[pd.Series]) -> Optional[float]:
    """Return the last non-NaN value from a Series, rounded to 4dp."""
    if series is None or (hasattr(series, "empty") and series.empty):
        return None
    val = series.iloc[-1]
    if pd.isna(val):
        return None
    return round(float(val), 4)


def _prev(series: Optional[pd.Series]) -> Optional[float]:
    """Return the second-to-last value from a Series (for crossover detection)."""
    if series is None or (hasattr(series, "empty") and series.empty) or len(series) < 2:
        return None
    val = series.iloc[-2]
    if pd.isna(val):
        return None
    return round(float(val), 4)


def calculate_indicators(df: pd.DataFrame) -> dict:
    """Compute technical indicators for an OHLCV DataFrame.

    Returns a flat dict of indicator values. Keys prefixed with `_` are
    internal helpers consumed by interpret_indicators.
    """
    if df is None or df.empty or len(df) < 2:
        return {}

    df = df.copy()
    df.columns = [c.lower() for c in df.columns]

    from ta.momentum import RSIIndicator
    from ta.trend import MACD, EMAIndicator, SMAIndicator
    from ta.volatility import AverageTrueRange, BollingerBands

    close = df["close"]
    high = df.get("high", close)
    low = df.get("low", close)
    volume = df.get("volume")

    result: dict = {}

    # RSI(14)
    rsi_s = RSIIndicator(close=close, window=14).rsi()
    result["rsi_14"] = _last(rsi_s)

    # MACD(12,26,9)
    macd_obj = MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
    macd_line = macd_obj.macd()
    macd_signal = macd_obj.macd_signal()
    macd_hist = macd_obj.macd_diff()
    result["macd_line"] = _last(macd_line)
    result["macd_signal"] = _last(macd_signal)
    result["macd_hist"] = _last(macd_hist)
    result["_prev_macd_line"] = _prev(macd_line)
    result["_prev_macd_signal"] = _prev(macd_signal)

    # Bollinger Bands(20,2)
    bb_obj = BollingerBands(close=close, window=20, window_dev=2)
    result["bb_upper"] = _last(bb_obj.bollinger_hband())
    result["bb_middle"] = _last(bb_obj.bollinger_mavg())
    result["bb_lower"] = _last(bb_obj.bollinger_lband())

    # SMAs
    sma50 = SMAIndicator(close=close, window=50).sma_indicator()
    sma200 = SMAIndicator(close=close, window=200).sma_indicator()
    result["sma_50"] = _last(sma50)
    result["sma_200"] = _last(sma200)
    result["_prev_sma_50"] = _prev(sma50)
    result["_prev_sma_200"] = _prev(sma200)

    # ATR(14)
    result["atr_14"] = _last(
        AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range()
    )

    # EMA(20)
    result["ema_20"] = _last(EMAIndicator(close=close, window=20).ema_indicator())

    # 20-day volume SMA
    result["volume_sma_20"] = _last(volume.rolling(20).mean()) if volume is not None else None

    # Internal helper: current close for bb_position
    result["_close"] = _last(close)

    # India-specific: circuit limits (±20% from last close)
    last_close = _last(close)
    if last_close is not None:
        upper = round(last_close * 1.20, 2)
        lower = round(last_close * 0.80, 2)
        result["circuit_upper"] = upper
        result["circuit_lower"] = lower
        result["near_upper_circuit"] = bool(last_close > upper * 0.97)
        result["near_lower_circuit"] = bool(last_close < lower * 1.03)
    else:
        result["circuit_upper"] = None
        result["circuit_lower"] = None
        result["near_upper_circuit"] = False
        result["near_lower_circuit"] = False

    return result


def interpret_indicators(indicators: dict) -> dict:
    """Add human-readable signal labels to a calculate_indicators() result dict.

    Strips internal `_`-prefixed helper keys and adds:
      macd_signal_label, bb_position, sma_cross, rsi_zone.
    """
    result = {k: v for k, v in indicators.items() if not k.startswith("_")}

    # MACD crossover
    ml = indicators.get("macd_line")
    ms = indicators.get("macd_signal")
    pml = indicators.get("_prev_macd_line")
    pms = indicators.get("_prev_macd_signal")

    if all(v is not None for v in (ml, ms, pml, pms)):
        if pml < pms and ml > ms:
            result["macd_signal_label"] = "bullish_crossover"
        elif pml > pms and ml < ms:
            result["macd_signal_label"] = "bearish_crossover"
        else:
            result["macd_signal_label"] = "neutral"
    else:
        result["macd_signal_label"] = "neutral"

    # Bollinger Band position
    close = indicators.get("_close")
    bb_upper = indicators.get("bb_upper")
    bb_lower = indicators.get("bb_lower")

    if all(v is not None for v in (close, bb_upper, bb_lower)):
        if close >= bb_upper:
            result["bb_position"] = "upper_band"
        elif close <= bb_lower:
            result["bb_position"] = "lower_band"
        else:
            result["bb_position"] = "middle"
    else:
        result["bb_position"] = "middle"

    # SMA golden / death cross
    sma50 = indicators.get("sma_50")
    sma200 = indicators.get("sma_200")
    p50 = indicators.get("_prev_sma_50")
    p200 = indicators.get("_prev_sma_200")

    if all(v is not None for v in (sma50, sma200, p50, p200)):
        if p50 < p200 and sma50 > sma200:
            result["sma_cross"] = "golden_cross"
        elif p50 > p200 and sma50 < sma200:
            result["sma_cross"] = "death_cross"
        else:
            result["sma_cross"] = "none"
    else:
        result["sma_cross"] = "none"

    # RSI zone
    rsi = indicators.get("rsi_14")
    if rsi is not None:
        if rsi >= 70:
            result["rsi_zone"] = "overbought"
        elif rsi <= 30:
            result["rsi_zone"] = "oversold"
        else:
            result["rsi_zone"] = "neutral"
    else:
        result["rsi_zone"] = "neutral"

    # India-specific: circuit alert
    if indicators.get("near_upper_circuit"):
        result["circuit_alert"] = "NEAR_UPPER"
    elif indicators.get("near_lower_circuit"):
        result["circuit_alert"] = "NEAR_LOWER"
    else:
        result["circuit_alert"] = "NONE"

    return result
