"""거래소 가용성(venue_count) 점수 — 백필 데이터상 가장 깨끗한 신호.

백필 50건 분석(실패율, 단조):
  1개소    → 실패율 50% (반반, 중앙값 -1.1%)  → 낮음
  2-3개소  → 실패율 28% (중앙값 +3.8%)        → 중립+
  4+개소   → 실패율  5% (중앙값 +8.8%)        → 높음

직관과 반대(적은 곳=갭↑가 아님): 많은 곳에 있을수록 검증된 코인 → 업비트 매수세가
프리미엄을 지탱 → 안전+수익↑. (※ 매수가 '최저가'라 거래소 많으면 진입가가 기계적으로
낮아지는 효과도 일부 섞이지만, 실패율 신호는 매도(업비트)측이라 진짜.)

venue_count 출처: 구매처 탐색 결과(ctx.extra["venue_count"]). 라이브에선 구매처 조회
시 채워지고, 없으면 available=False(시총/소셜처럼 우아하게 비활성).
"""
from __future__ import annotations

from ...core.events import FeatureScore
from .base import FeatureContext, FeatureExtractor

# 가용성 구간별 점수(데이터 버킷에 맞춤).
SCORE_SINGLE = 0.2     # 1개소 — 실패율 50%
SCORE_FEW = 0.55       # 2-3개소 — 실패율 28%
SCORE_MANY = 0.9       # 4+개소 — 실패율 5%


def score_for(venue_count: int) -> float:
    if venue_count <= 1:
        return SCORE_SINGLE
    if venue_count <= 3:
        return SCORE_FEW
    return SCORE_MANY


class VenueCountFeature(FeatureExtractor):
    name = "venue_count"

    def extract(self, ctx: FeatureContext) -> FeatureScore:
        vc = ctx.extra.get("venue_count")
        if not isinstance(vc, int) or vc <= 0:
            return FeatureScore(
                name=self.name, score=0.5, weight=self.weight,
                available=False, detail="거래소 가용성 미상(구매처 조회 전)",
            )
        bucket = "1개소" if vc <= 1 else ("2-3개소" if vc <= 3 else "4+개소")
        return FeatureScore(
            name=self.name, score=score_for(vc), weight=self.weight,
            available=True, detail=f"구매처 {vc}곳({bucket}) — 많을수록 안전·수익↑",
        )
