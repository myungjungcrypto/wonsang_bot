"""투명한 가중합 스코어링 → 등급.

- 가용(available) 피처만으로 가중평균 → score(0..1)
- confidence = 가용 피처 가중치 비중 (데이터 적으면 점수는 내되 신뢰도로 표시)
- score → 등급 매핑(임계값 조정 가능, 기능 8에서 캘리브레이션)
"""
from __future__ import annotations

from ..core.events import FeatureScore

# (최소 점수, 등급) 내림차순. score >= 임계값 이면 해당 등급.
DEFAULT_THRESHOLDS: tuple[tuple[float, str], ...] = (
    (0.80, "대성공"),
    (0.62, "성공"),
    (0.42, "약성공"),
    (0.25, "실패"),
    (0.0, "큰실패"),
)


def combine(features: list[FeatureScore]) -> tuple[float, float]:
    """반환: (score, confidence) 둘 다 0..1."""
    total_w = sum(f.weight for f in features)
    avail = [f for f in features if f.available]
    avail_w = sum(f.weight for f in avail)
    if avail_w <= 0:
        return 0.0, 0.0
    score = sum(f.score * f.weight for f in avail) / avail_w
    confidence = avail_w / total_w if total_w > 0 else 0.0
    return round(score, 4), round(confidence, 4)


def to_grade(
    score: float, thresholds: tuple[tuple[float, str], ...] = DEFAULT_THRESHOLDS
) -> str:
    for min_score, grade in thresholds:
        if score >= min_score:
            return grade
    return thresholds[-1][1]
