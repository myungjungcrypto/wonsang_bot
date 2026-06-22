"""상장 유형 점수.

가설(사용자): KRW 마켓만 추가(=이미 업비트 BTC/USDT에 있던 코인)는 따리 모멘텀이
약해 실패 경향. → **백필 데이터(50건)로 검증한 결과 반대**였다: KRW만추가의 실패율은
8%로 신규(24%)보다 오히려 낮음(안전). 다만 대박(대성공)은 신규 쪽에 몰린다.
즉 KRW만추가 = "안전하지만 천장 낮음"(중립), 신규 = "고위험·고대박"(분산 큼).
→ pre_listed 를 '실패 예측(0.2)'에서 '중립(0.5)'으로 보정.
(n=12로 작고 상폐/개명 코인 생존편향 가능 → 데이터 쌓이면 재캘리브레이션.)

listing.pre_listed:
  True  → KRW만 추가(기존 코인) → 중립(안전·저천장)
  False → 신규 전체상장        → 약간 높음(대박 여지)
  None  → 미상 → available=False (가중합 제외)
"""
from __future__ import annotations

from ...core.events import FeatureScore
from .base import FeatureContext, FeatureExtractor

# 기본 점수(데이터로 캘리브레이션). KRW만추가는 '실패'가 아니라 '중립(안전·저천장)'.
SCORE_PRE_LISTED = 0.5
SCORE_FRESH = 0.7


class ListingTypeFeature(FeatureExtractor):
    name = "listing_type"

    def extract(self, ctx: FeatureContext) -> FeatureScore:
        pre = ctx.listing.pre_listed
        if pre is None:
            return FeatureScore(
                name=self.name, score=0.5, weight=self.weight,
                available=False, detail="상장 유형 미상(pre_listed 미설정)",
            )
        if pre:
            return FeatureScore(
                name=self.name, score=SCORE_PRE_LISTED, weight=self.weight,
                available=True, detail="KRW만 추가(기존 업비트 코인) — 안전·저천장(중립)",
            )
        return FeatureScore(
            name=self.name, score=SCORE_FRESH, weight=self.weight,
            available=True, detail="신규 전체상장(첫 진입 물량) — 대박 여지",
        )
