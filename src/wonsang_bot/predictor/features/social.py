"""소셜 언급량 점수 — 텔레그램/X 언급 빈도가 높을수록 수요(상장 펌핑) 기대↑.

데이터는 주입형 provider에서 받는다. 없으면 available=False.
"""
from __future__ import annotations

from ...core.events import FeatureScore
from .base import FeatureContext, FeatureExtractor, score_higher_better

# 시간당 언급 수 구간 — 라이브 캘리브레이션 대상
MENTIONS_LOW = 0
MENTIONS_HIGH = 200


def score_social(mentions_per_hour: float) -> float:
    return score_higher_better(mentions_per_hour, MENTIONS_LOW, MENTIONS_HIGH)


class SocialFeature(FeatureExtractor):
    name = "social"

    def extract(self, ctx: FeatureContext) -> FeatureScore:
        data = ctx.social_provider(ctx.listing) if ctx.social_provider else None
        mph = (data or {}).get("mentions_per_hour") if data else None
        if mph is None:
            return FeatureScore(
                name=self.name, score=0.5, weight=self.weight,
                available=False, detail="소셜 데이터 없음(provider 미연결)",
            )
        s = score_social(float(mph))
        return FeatureScore(
            name=self.name, score=round(s, 3), weight=self.weight, available=True,
            detail=f"언급 {float(mph):.0f}/h", raw={"mentions_per_hour": mph},
        )
