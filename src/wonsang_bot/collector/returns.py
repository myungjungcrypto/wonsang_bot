"""가격 시계열 → 실현 수익률(%) 계산 (순수 함수).

따리 라벨 방법론(사용자 정의):
- 진입: 상장 +entry_offset(기본 5분) 시점 가격에 매수
- 청산: 상장 +exit_offset(상장 직후, 고점 아님) 시점 가격에 매도
- return = (매도가 / 진입가 - 1) * 100

series: [(epoch_seconds, price)] (정렬 무관, 내부 정렬). 국내 KRW 캔들 기준 권장.
"""
from __future__ import annotations

from typing import Optional

Series = list[tuple[float, float]]


def _price_at(series: Series, target_ts: float) -> Optional[tuple[float, float]]:
    """target_ts 이상 첫 포인트(없으면 마지막 직전 포인트)."""
    after = [pt for pt in series if pt[0] >= target_ts]
    if after:
        return after[0]
    return series[-1] if series else None


def point_return_pct(
    series: Series,
    start_ts: float,
    entry_offset_sec: float,
    exit_offset_sec: float,
) -> Optional[float]:
    """진입(start+entry_offset) 대비 매도(start+exit_offset) *시점 가격* 수익률(%)."""
    if not series:
        return None
    s = sorted(series)
    entry = _price_at(s, start_ts + entry_offset_sec)
    exit_ = _price_at(s, start_ts + exit_offset_sec)
    if entry is None or exit_ is None or entry[1] <= 0:
        return None
    return round((exit_[1] / entry[1] - 1.0) * 100.0, 2)


def peak_return_pct(
    series: Series,
    start_ts: float,
    window_sec: float,
    entry_offset_sec: float = 0.0,
) -> Optional[float]:
    """(참고용) 진입 대비 윈도 내 고점 수익률(%). 현 라벨은 point_return_pct 사용."""
    if not series:
        return None
    s = sorted(series)
    entry = _price_at(s, start_ts + entry_offset_sec)
    if entry is None:
        return None
    entry_ts, entry_px = entry
    if entry_px <= 0:
        return None
    end = start_ts + window_sec
    window = [px for ts, px in s if entry_ts <= ts <= end]
    if not window:
        window = [entry_px]
    peak = max(window)
    return round((peak / entry_px - 1.0) * 100.0, 2)
