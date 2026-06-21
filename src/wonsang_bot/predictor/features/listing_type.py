"""상장 유형 점수.

가설(사용자): **KRW 마켓만 추가**된 경우(=이미 업비트 BTC/USDT에 상장돼 있던 코인)는
신규 따리 모멘텀이 약해 **실패 경향**. 반대로 **신규 전체상장**(KRW/BTC/USDT 동시)은
처음 들어오는 물량이라 갭이 크게 벌어질 여지가 큼.

listing.pre_listed:
  True  → KRW만 추가(기존 코인) → 낮은 점수(실패 경향)
  False → 신규 전체상장        → 높은 점수
  None  → 미상 → available=False (가중합 제외)

점수는 캘리ब레이션 대상(scripts/analyze_cases.py 의 실패율로 조정).
"""
from __future__ import annotations

from ...core.events import FeatureScore
from .base import FeatureContext, FeatureExtractor

# 기본 점수(데이터로 캘리브레이션). 사용자 관찰: KRW만 추가는 잘 망함.
SCORE_PRE_LISTED = 0.2
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
                available=True, detail="KRW만 추가(기존 업비트 코인) — 실패 경향",
            )
        return FeatureScore(
            name=self.name, score=SCORE_FRESH, weight=self.weight,
            available=True, detail="신규 전체상장(첫 진입 물량)",
        )
