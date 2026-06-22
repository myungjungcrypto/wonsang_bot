"""바이낸스 선상장 여부 점수 (사용자 추가 기준).

가설: 상장 시점 이미 **바이낸스(USDT)** 에 있던 코인은 글로벌 유동성·인지도가 이미 커서
업비트 신규상장의 따리 프리미엄이 덜 폭발할 수 있음(약한 음의 신호). 반대로 바이낸스에도
없던 코인은 첫 메이저 진입이라 갭 여지. (단, 메이저 상장 = 검증된 코인이라 오히려 안전할
가능성도 — listing_type/빗썸처럼 직관이 데이터와 반대일 수 있어 약한 가중으로 시작.)

⚠️ 백필 데이터로 검증 전 → 약한 lean + 낮은 가중. analysis 의 by_binance 로 캘리브레이션.

listing.pre_listed_binance:
  True  → 바이낸스 선상장 → 약간 낮음
  False → 바이낸스 미상장 → 약간 높음
  None  → 미상 → available=False (가중합 제외)
"""
from __future__ import annotations

from ...core.events import FeatureScore
from .base import FeatureContext, FeatureExtractor

SCORE_ON_BINANCE = 0.45      # 바이낸스 선상장 — 프리미엄 덜할 수 있음(가설)
SCORE_NOT_ON_BINANCE = 0.55  # 바이낸스 미상장 — 첫 메이저 진입


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
                available=True, detail="바이낸스 선상장(글로벌 인지 기존) — 프리미엄 약화 가설",
            )
        return FeatureScore(
            name=self.name, score=SCORE_NOT_ON_BINANCE, weight=self.weight,
            available=True, detail="바이낸스 미상장 — 첫 메이저 진입(갭 여지)",
        )
