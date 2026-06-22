"""바이낸스 선상장 여부 점수 (사용자 추가 기준).

가설(원래): 바이낸스에 이미 있으면 프리미엄 약화 → 낮은 점수.
→ **백필 50건으로 검증한 결과 반대(강한 신호)**:
  바이낸스 선상장  중앙값 +9.7% / 실패율 16% / 승률 84%
  바이낸스 미상장  중앙값 +3.8% / 실패율 24% / 승률 76%
즉 바이낸스 선상장 = '검증된 좋은 코인'이라 수익↑ + 안전(venue_count 와 같은 품질 신호).
→ 방향을 **양(선상장=높음)** 으로 바꾸고 가중을 올린다.
(n=25/25 로 비교적 깔끔. venue_count 와 상관 있으니 가중은 그보다는 낮게.)

listing.pre_listed_binance:
  True  → 바이낸스 선상장 → 높음(품질·수요 검증)
  False → 바이낸스 미상장 → 낮음(상대적으로 무명·위험)
  None  → 미상 → available=False (가중합 제외)
"""
from __future__ import annotations

from ...core.events import FeatureScore
from .base import FeatureContext, FeatureExtractor

# 데이터 캘리브레이션: 선상장(중앙 +9.7%/실패16%)=성공경향, 미상장(+3.8%/실패24%)=경계.
SCORE_ON_BINANCE = 0.7
SCORE_NOT_ON_BINANCE = 0.4


class BinanceListedFeature(FeatureExtractor):
    name = "binance_listed"

    def extract(self, ctx: FeatureContext) -> FeatureScore:
        pre = ctx.listing.pre_listed_binance
        if pre is None:
            return FeatureScore(
                name=self.name, score=0.5, weight=self.weight,
                available=False, detail="바이낸스 선상장 여부 미상",
            )
        if pre:
            return FeatureScore(
                name=self.name, score=SCORE_ON_BINANCE, weight=self.weight,
                available=True, detail="바이낸스 선상장(검증된 코인) — 수익↑·안전(데이터)",
            )
        return FeatureScore(
            name=self.name, score=SCORE_NOT_ON_BINANCE, weight=self.weight,
            available=True, detail="바이낸스 미상장 — 상대적 무명·위험(데이터)",
        )

