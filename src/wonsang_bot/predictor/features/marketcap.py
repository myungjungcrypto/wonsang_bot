"""유통 시총 점수 — 작을수록 펌핑 여지가 커 갭 유리.

데이터는 주입형 provider(예: CoinGecko/CMC + 온체인 유통량)에서 받는다.
provider가 없거나 값을 못 주면 available=False(오프라인 환경에서 우아하게 비활성).
"""
from __future__ import annotations

from ...core.events import FeatureScore
from .base import FeatureContext, FeatureExtractor, score_lower_better

# 시총 점수 구간(USD): 이 이하면 1점, 이상이면 0점 — 라이브 캘리브레이션 대상
MC_GOOD_BELOW = 2_000_000      # 200만달러 이하 → 초소형, 펌핑 여지 큼
MC_BAD_ABOVE = 500_000_000     # 5억달러 이상 → 펌핑 여지 작음


def score_marketcap(mc_usd: float) -> float:
    return score_lower_better(mc_usd, MC_GOOD_BELOW, MC_BAD_ABOVE)


class MarketCapFeature(FeatureExtractor):
    name = "marketcap"

    def extract(self, ctx: FeatureContext) -> FeatureScore:
        data = ctx.market_provider(ctx.listing) if ctx.market_provider else None
        mc = (data or {}).get("market_cap_usd") if data else None
        if mc is None:
            return FeatureScore(
                name=self.name, score=0.5, weight=self.weight,
                available=False, detail="시총 데이터 없음(provider 미연결)",
            )
        s = score_marketcap(float(mc))
        return FeatureScore(
            name=self.name, score=round(s, 3), weight=self.weight, available=True,
            detail=f"유통시총 ${float(mc):,.0f}", raw={"market_cap_usd": mc},
        )
