"""상장 시간대 점수.

가정: 경쟁자가 덜 붙는 시간대(저녁/심야, 주말, 특히 금요일 저녁)에 상장될수록
대응이 늦은 물량이 많아 갭이 커질 수 있다. (라이브 데이터로 캘리브레이션 필요)
"""
from __future__ import annotations

from datetime import timedelta, timezone

from ...core.events import FeatureScore
from .base import FeatureContext, FeatureExtractor, clamp01, resolve_time

KST = timezone(timedelta(hours=9))


class TimingFeature(FeatureExtractor):
    name = "timing"

    def extract(self, ctx: FeatureContext) -> FeatureScore:
        dt = resolve_time(ctx).astimezone(KST)
        wd, h = dt.weekday(), dt.hour  # 월=0 ... 일=6

        score = 0.4
        notes: list[str] = []
        if 18 <= h <= 23 or 0 <= h <= 1:
            score += 0.25
            notes.append("저녁/심야")
        if wd == 4 and h >= 18:
            score += 0.2
            notes.append("금요일 저녁")
        if wd >= 5:
            score += 0.2
            notes.append("주말")

        score = clamp01(score)
        detail = (
            f"KST {dt:%a %H:%M} ({'·'.join(notes)})" if notes else f"KST {dt:%a %H:%M} (평시)"
        )
        return FeatureScore(
            name=self.name,
            score=round(score, 3),
            weight=self.weight,
            available=True,
            detail=detail,
            raw={"weekday": wd, "hour": h},
        )
