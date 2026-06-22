"""수집된 케이스 통계 — 실패율/승률을 그룹별로 (순수 함수).

가설 검증용:
- 상장 유형(KRW만 추가 vs 신규 전체상장)별 실패율
- 거래소 가용성(1 / 2-3 / 4+ 개소)별 수익률 — "적은 곳에만 있을수록 갭↑"?
"""
from __future__ import annotations

import statistics
from typing import Any

from ..predictor.labeling import grade_from_return

WIN_PCT = 0.0    # 승리 기준: 0% 이상(약성공+성공+대성공)
FAIL_PCT = 0.0   # 실패 기준: 0% 미만


def _stats(rets: list[float]) -> dict[str, Any]:
    n = len(rets)
    if n == 0:
        return {"n": 0}
    wins = sum(1 for r in rets if r >= WIN_PCT)
    fails = sum(1 for r in rets if r < FAIL_PCT)
    return {
        "n": n,
        "win_rate": round(wins / n, 3),       # ret>=0% (승리)
        "fail_rate": round(fails / n, 3),      # ret<0% (손실)
        "median_ret": round(statistics.median(rets), 2),  # 이상치에 강함(대표값)
        "avg_ret": round(sum(rets) / n, 2),    # 이상치(대박)에 휘둘림 — 참고용
        "max_ret": round(max(rets), 1),        # 최대 대박(이상치 확인용)
    }


def summarize(cases: list[dict]) -> dict[str, Any]:
    rets_all: list[float] = []
    by_type: dict[str, list[float]] = {"KRW만추가(기존코인)": [], "신규전체상장": [], "미상": []}
    by_venue: dict[str, list[float]] = {"1개소": [], "2-3개소": [], "4+개소": []}
    grades: dict[str, int] = {}

    for c in cases:
        r = c.get("realized_return_pct")
        if r is None:
            continue
        rets_all.append(r)

        pre = c.get("pre_listed")
        key = "KRW만추가(기존코인)" if pre is True else ("신규전체상장" if pre is False else "미상")
        by_type[key].append(r)

        vc = (c.get("meta") or {}).get("venue_count")
        if isinstance(vc, int):
            bucket = "1개소" if vc <= 1 else ("2-3개소" if vc <= 3 else "4+개소")
            by_venue[bucket].append(r)

        g = grade_from_return(r)
        grades[g] = grades.get(g, 0) + 1

    return {
        "overall": _stats(rets_all),
        "grades": grades,
        "by_listing_type": {k: _stats(v) for k, v in by_type.items()},
        "by_venue_count": {k: _stats(v) for k, v in by_venue.items()},
    }
