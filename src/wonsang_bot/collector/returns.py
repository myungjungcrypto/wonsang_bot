"""가격 시계열 → 실현 수익률(%) 계산 (순수 함수).

따리 라벨 방법론:
- 진입: 상장 공지 +entry_offset(기본 5분) 시점 가격에 매수
- 청산: 진입~(상장+window) 구간의 국내(업비트/빗썸) 고점에 매도
- return = (고점 / 진입가 - 1) * 100

series: [(epoch_seconds, price)] (정렬 무관, 내부 정렬). 국내 KRW 캔들 기준 권장.
"""
from __future__ import annotations

from typing import Optional

Series = list[tuple[float, float]]


def _entry(series: Series, entry_ts: float) -> Optional[tuple[float, float]]:
    after = [pt for pt in series if pt[0] >= entry_ts]
    if after:
        return after[0]
    return series[-1] if series else None


def peak_return_pct(
    series: Series,
    start_ts: float,
    window_sec: float,
    entry_offset_sec: float = 0.0,
) -> Optional[float]:
    """진입(start_ts+entry_offset) 대비 [진입, start_ts+window] 구간 고점 수익률(%)."""
    if not series:
        return None
    s = sorted(series)
    entry = _entry(s, start_ts + entry_offset_sec)
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
