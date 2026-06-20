"""피처 추출 공통 골격.

각 피처 추출기는 FeatureContext를 받아 FeatureScore(0..1)를 돌려준다.
- 점수는 "갭이 크게 벌어질(=따리 성공) 가능성"에 양의 방향으로 정규화.
- 데이터가 없으면 available=False → 스코어링에서 제외되고 신뢰도만 낮아진다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from ...config import Config
from ...core.events import FeatureScore, ListingDetected

# 시세/소셜 등 네트워크 의존 데이터 제공자(없으면 None → 해당 피처 비활성)
Provider = Callable[[ListingDetected], Optional[dict]]


@dataclass(slots=True)
class FeatureContext:
    listing: ListingDetected
    config: Optional[Config] = None
    now: Optional[datetime] = None            # 테스트/재현용 시각 주입
    market_provider: Optional[Provider] = None
    social_provider: Optional[Provider] = None
    extra: dict[str, Any] = field(default_factory=dict)


class FeatureExtractor:
    name: str = "base"

    def __init__(self, weight: float = 1.0) -> None:
        self.weight = weight

    def extract(self, ctx: FeatureContext) -> FeatureScore:  # pragma: no cover
        raise NotImplementedError


# --- 점수 헬퍼 (순수 함수) ---

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def score_higher_better(v: float, lo: float, hi: float) -> float:
    """v<=lo → 0, v>=hi → 1 (선형)."""
    if hi == lo:
        return 0.5
    return clamp01((v - lo) / (hi - lo))


def score_lower_better(v: float, lo: float, hi: float) -> float:
    """v<=lo → 1, v>=hi → 0 (선형). 작을수록 좋은 지표용."""
    if hi == lo:
        return 0.5
    return clamp01(1.0 - (v - lo) / (hi - lo))


def parse_iso(s: str | None) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def resolve_time(ctx: FeatureContext) -> datetime:
    """피처 계산 기준 시각(tz-aware UTC 보장)."""
    dt = ctx.now or parse_iso(ctx.listing.published_at) or parse_iso(
        ctx.listing.detected_at
    )
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
