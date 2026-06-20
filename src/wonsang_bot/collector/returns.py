"""가격 시계열 → 실현 수익률(%) 계산 (순수 함수).

따리 라벨용 지표. 기본은 "상장 직후 진입가 대비 윈도 내 고점 수익률"(펌핑 크기 프록시).
- series: [(epoch_seconds, price)] (정렬 무관, 내부에서 정렬)
- 진입가: 상장시각 이후 첫 포인트(없으면 직전 마지막 포인트)
- 고점: [진입시각, 상장시각+window] 구간의 최대가

⚠️ 이는 글로벌 가격 기준 프록시. 정밀한 코프(국내 KRW vs 해외) 라벨이 필요하면
provider 단에서 국내/해외 두 시계열을 받아 동일 구조로 계산하도록 교체하면 된다.
"""
from __future__ import annotations

from typing import Optional

Series = list[tuple[float, float]]


def _entry(series: Series, start_ts: float) -> Optional[tuple[float, float]]:
    after = [pt for pt in series if pt[0] >= start_ts]
    if after:
        return after[0]
    return series[-1] if series else None


def peak_return_pct(
    series: Series, start_ts: float, window_sec: float
) -> Optional[float]:
    if not series:
        return None
    s = sorted(series)
    entry = _entry(s, start_ts)
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
