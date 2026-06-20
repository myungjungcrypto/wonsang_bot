"""실현 결과 → 등급 라벨.

방법론(사용자 정의): 상장 공지 +5분 가격에 매수 → 상장 직후 업비트/빗썸 국내가
고점에 매도했을 때의 수익률(%)을 등급으로 변환.

임계값(2026-06-20 확정):
  대성공 ≥ 25% / 성공 10~25% / 보통 0~10% / 실패 -10~0% / 큰실패 ≤ -10%
"""
from __future__ import annotations

import math

# (최소 수익률%, 등급) 내림차순
DEFAULT_RETURN_THRESHOLDS: tuple[tuple[float, str], ...] = (
    (25.0, "대성공"),
    (10.0, "성공"),
    (0.0, "보통"),
    (-10.0, "실패"),
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
