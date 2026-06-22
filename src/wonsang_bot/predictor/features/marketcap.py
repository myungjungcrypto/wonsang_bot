"""유통 시총(MC) 점수 — 클수록 따리 펌핑 여지 작음.

백필 50건(상장일 CoinGecko MC, 구간별 중앙값):
  $10-100M +8.6% / $100M-1B +8.5% / >$1B +0.8%(거의 본전)  (미상=초기/무데이터 +4.3%)
→ "작을수록 좋다"는 약하고($10M~1B 차이 거의 없음), **실질 분기점은 ~$1B**(대형주는
  이미 글로벌 가격 형성 → 안 터짐). ramp 중심을 $1B 근처로(≤$500M 최고, $1.5B↑ 0).
FDV(완전희석)가 신규상장엔 더 맞을 수 있으나 일단 MC 기준(추후 확장).
"""
from __future__ import annotations

from ...core.events import FeatureScore
from .base import FeatureContext, FeatureExtractor, score_lower_better

# 데이터 캘리브레이션: ≤$500M 펌핑여지 충분, $1.5B↑ 사실상 없음(분기 ~$1B).
MC_GOOD_BELOW = 500_000_000
MC_BAD_ABOVE = 1_500_000_000


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
