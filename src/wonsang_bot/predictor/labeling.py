"""실현 결과 → 등급 라벨.

과거 케이스의 "따리로 실제로 먹을 수 있었던 수익률(%)"을 등급으로 변환한다.
(국내 매도가 대비 해외 매집가 기준의 실현 수익 등 — 데이터 출처는 백필 입력에 따름)

임계값은 캘리브레이션 대상(기능 8). 기본값은 합리적 출발점.
"""
from __future__ import annotations

import math

# (최소 수익률%, 등급) 내림차순
DEFAULT_RETURN_THRESHOLDS: tuple[tuple[float, str], ...] = (
    (100.0, "대성공"),
    (40.0, "성공"),
    (15.0, "보통"),
    (0.0, "실패"),
    (-math.inf, "큰실패"),
)


def grade_from_return(
    return_pct: float,
    thresholds: tuple[tuple[float, str], ...] = DEFAULT_RETURN_THRESHOLDS,
) -> str:
    for min_pct, grade in thresholds:
        if return_pct >= min_pct:
            return grade
    return thresholds[-1][1]
