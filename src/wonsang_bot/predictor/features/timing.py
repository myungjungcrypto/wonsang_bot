"""상장 요일·시간대 점수 (KST) — 백필 데이터로 캘리브레이션.

백필 50건(요일별 중앙값/실패율):
  월 +2.0%/33%  화 +8.8%/9%  수 +5.9%/25%  목 +8.6%/22%  금 +21.6%/11%  (토·일 0건)
  시간대: 오전(6-12) +9.9%/0%(n5)  오후(12-17) +4.3%/21%(n33)  저녁(17-24) +10.5%/25%(n12)

→ 금요일 최강·화/목 양호·월 약함, 오후(다수)가 가장 평범. 주말 상장은 업비트가 거의
  안 해서 표본 0 → 중립. 표본이 작아(요일당 ~9~12) 큰 경향만 반영하고 과적합 피함.
가중은 낮게(w_timing) 두고 데이터 쌓이면 재보정.
"""
from __future__ import annotations

from datetime import timedelta, timezone

from ...core.events import FeatureScore
from .base import FeatureContext, FeatureExtractor, clamp01, resolve_time

KST = timezone(timedelta(hours=9))

# 요일(월=0..일=6) 가감 — 데이터 중앙값/실패율 기반. 주말은 표본 0 → 중립.
_WEEKDAY_ADJ = {0: -0.12, 1: +0.12, 2: 0.0, 3: +0.08, 4: +0.20, 5: 0.0, 6: 0.0}
_WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]


def _daypart_adj(h: int) -> tuple[float, str]:
    if 6 <= h < 12:
        return +0.08, "오전"      # 표본 작지만 양호(실패 0%)
    if 12 <= h < 17:
        return -0.05, "오후"      # 다수·가장 평범(기준선)
    if 17 <= h < 24:
        return +0.05, "저녁"      # 중앙값 높으나 분산 큼(실패율도↑)
    return 0.0, "심야"            # 표본 거의 없음 → 중립


class TimingFeature(FeatureExtractor):
    name = "timing"

    def extract(self, ctx: FeatureContext) -> FeatureScore:
        dt = resolve_time(ctx).astimezone(KST)
        wd, h = dt.weekday(), dt.hour

        wd_adj = _WEEKDAY_ADJ.get(wd, 0.0)
        tod_adj, part = _daypart_adj(h)
        score = clamp01(0.5 + wd_adj + tod_adj)

        detail = f"KST {_WEEKDAY_KO[wd]} {dt:%H:%M}·{part} (요일{wd_adj:+.2f}/시간{tod_adj:+.2f})"
        return FeatureScore(
            name=self.name,
            score=round(score, 3),
            weight=self.weight,
            available=True,
            detail=detail,
            raw={"weekday": wd, "hour": h},
        )
