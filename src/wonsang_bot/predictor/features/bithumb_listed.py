"""빗썸 기상장 여부 점수 (사용자 추가 기준).

가설: 상장 시점 이미 **빗썸(KRW)** 에 있던 코인은 한국 리테일이 이미 접근 가능했으므로
업비트 신규상장의 따리 프리미엄이 덜 폭발할 수 있음(약한 음의 신호). 반대로 빗썸에도
없던 코인은 첫 한국 진입이라 갭이 크게 벌어질 여지.

⚠️ 아직 백필 데이터로 검증 전 → **약한 lean + 낮은 가중**으로 시작하고,
analysis 의 by_bithumb 실패율로 캘리브레이션한다. (listing_type 처럼 직관이 데이터와
반대일 수 있음 — 빗썸 동시상장 = 검증된 코인이라 오히려 안전할 가능성도.)

listing.pre_listed_bithumb:
  True  → 빗썸 선상장 → 약간 낮음
  False → 빗썸 미상장 → 약간 높음
  None  → 미상 → available=False (가중합 제외)
"""
from __future__ import annotations

from ...core.events import FeatureScore
from .base import FeatureContext, FeatureExtractor

# 검증 전이라 중립 근처(약한 lean). 데이터 쌓이면 재캘리브레이션.
SCORE_ON_BITHUMB = 0.45     # 빗썸 선상장 — 프리미엄 덜할 수 있음(가설)
SCORE_NOT_ON_BITHUMB = 0.55  # 빗썸 미상장 — 첫 한국 진입


class BithumbListedFeature(FeatureExtractor):
    name = "bithumb_listed"

    def extract(self, ctx: FeatureContext) -> FeatureScore:
        pre = ctx.listing.pre_listed_bithumb
        if pre is None:
            return FeatureScore(
                name=self.name, score=0.5, weight=self.weight,
                available=False, detail="빗썸 기상장 여부 미상",
            )
        if pre:
            return FeatureScore(
                name=self.name, score=SCORE_ON_BITHUMB, weight=self.weight,
                available=True, detail="빗썸 선상장(한국 접근 기존) — 프리미엄 약화 가설",
            )
        return FeatureScore(
            name=self.name, score=SCORE_NOT_ON_BITHUMB, weight=self.weight,
            available=True, detail="빗썸 미상장 — 첫 한국 진입(갭 여지)",
        )
