"""소셜 점수 — 소셜 관심/언급이 높을수록 수요(상장 펌핑) 기대↑.

데이터는 주입형 provider(LunarCrush 등)에서 받는다. 없으면 available=False.
- galaxy_score(0~100, LunarCrush 종합 소셜지표)가 있으면 우선 사용(/100).
- 없으면 mentions_per_hour(언급 velocity)로 score_higher_better.
둘 다 없으면 비활성. (라이브 캘리브레이션 대상)
"""
from __future__ import annotations

from ...core.events import FeatureScore
from .base import FeatureContext, FeatureExtractor, clamp01, score_higher_better

# 시간당 언급 수 구간 — 라이브 캘리브레이션 대상
MENTIONS_LOW = 0
MENTIONS_HIGH = 200


def score_social(mentions_per_hour: float) -> float:
    return score_higher_better(mentions_per_hour, MENTIONS_LOW, MENTIONS_HIGH)


class SocialFeature(FeatureExtractor):
    name = "social"

    def extract(self, ctx: FeatureContext) -> FeatureScore:
        data = ctx.social_provider(ctx.listing) if ctx.social_provider else None
        data = data or {}
        galaxy = data.get("galaxy_score")
        mph = data.get("mentions_per_hour")

        if galaxy is not None:
            s = clamp01(float(galaxy) / 100.0)
            return FeatureScore(
                name=self.name, score=round(s, 3), weight=self.weight, available=True,
                detail=f"galaxy_score {float(galaxy):.0f}/100", raw=dict(data),
            )
        if mph is not None:
            s = score_social(float(mph))
            return FeatureScore(
                name=self.name, score=round(s, 3), weight=self.weight, available=True,
                detail=f"언급 {float(mph):.0f}/h", raw=dict(data),
            )
        return FeatureScore(
            name=self.name, score=0.5, weight=self.weight,
            available=False, detail="소셜 데이터 없음(provider 미연결)",
        )
