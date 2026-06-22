"""과거 케이스 기반 2차 검증 — 최근접 이웃.

상장 시점 피처 벡터로 과거 케이스 중 가장 비슷한 것들을 찾아,
그들의 실현 등급으로 2차 등급을 제안한다(가중합 1차 등급과 교차검증).

⚠️ 케이스 DB 백필(공지+가격액션+피처+실현라벨)은 별도 선행 과제(계획서 5-(2)).
여기서는 그 위에서 도는 순수 알고리즘만 제공 — 합성 케이스로 테스트 가능.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from ..core.events import GRADES

_EPS = 1e-9


@dataclass(slots=True)
class Case:
    id: str
    symbol: str
    features: dict[str, float]        # 피처명 → 점수(0..1)
    grade: str                        # 실현 등급(GRADES 중 하나)
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "Case":
        return cls(
            id=str(d.get("id", "")),
            symbol=str(d.get("symbol", "")),
            features=dict(d.get("features", {})),
            grade=str(d.get("grade", "약성공")),
            meta=dict(d.get("meta", {})),
        )


def distance(a: dict[str, float], b: dict[str, float]) -> float:
    """공유 피처에 대한 정규화 유클리드 거리. 공유 피처 없으면 inf."""
    shared = set(a) & set(b)
    if not shared:
        return math.inf
    sq = sum((a[k] - b[k]) ** 2 for k in shared)
    return math.sqrt(sq / len(shared))


class HistoricalStore:
    def __init__(self, cases: list[Case] | None = None) -> None:
        self.cases = cases or []

    @classmethod
    def from_dicts(cls, rows: list[dict]) -> "HistoricalStore":
        return cls([Case.from_dict(r) for r in rows])

    def nearest(
        self, features: dict[str, float], k: int = 3
    ) -> list[tuple[Case, float]]:
        scored = [(c, distance(features, c.features)) for c in self.cases]
        scored = [(c, d) for c, d in scored if math.isfinite(d)]
        scored.sort(key=lambda cd: cd[1])
        return scored[:k]

    def suggest_grade(self, neighbors: list[tuple[Case, float]]) -> str | None:
        """이웃들의 실현 등급을 거리 역수로 가중평균 → 등급."""
        if not neighbors:
            return None
        idx = {g: i for i, g in enumerate(GRADES)}
        num = den = 0.0
        for case, dist in neighbors:
            if case.grade not in idx:
                continue
            w = 1.0 / (dist + _EPS)
            num += idx[case.grade] * w
            den += w
        if den == 0:
            return None
        avg = round(num / den)
        avg = max(0, min(len(GRADES) - 1, avg))
        return GRADES[avg]
