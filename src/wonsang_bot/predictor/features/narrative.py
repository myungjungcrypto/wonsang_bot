"""내러티브 태깅 점수.

제목/심볼을 내러티브(AI, RWA, 밈 등)로 태깅하고, 현재 핫한 정도(heat)로 점수화.
heat 가중치는 config.hot_narratives 로 조정(기능 8에서 갱신). 없으면 기본값 사용.
"""
from __future__ import annotations

import re

from ...core.events import FeatureScore
from .base import FeatureContext, FeatureExtractor

# canonical 내러티브 → 매칭 키워드(소문자, 한/영)
NARRATIVE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ai": ("ai", "인공지능", "artificial intelligence", "agent", "에이전트"),
    "rwa": ("rwa", "real world asset", "실물자산", "tokenized"),
    "meme": ("meme", "밈", "doge", "pepe", "shib", "wif", "bonk"),
    "depin": ("depin", "디핀", "physical infrastructure"),
    "defi": ("defi", "디파이", "dex", "perp", "lending", "staking", "스테이킹"),
    "gaming": ("game", "gaming", "게임", "gamefi", "play"),
    "layer2": ("layer2", "l2", "rollup", "롤업", "zk", "arbitrum", "optimism"),
    "layer1": ("layer1", "l1", "mainnet", "메인넷"),
    "nft": ("nft", "대체불가"),
}

# 기본 heat(0..1). config.hot_narratives 가 있으면 그쪽 우선.
DEFAULT_HOT_NARRATIVES: dict[str, float] = {
    "ai": 1.0,
    "rwa": 0.9,
    "meme": 0.85,
    "depin": 0.8,
    "defi": 0.6,
    "gaming": 0.6,
    "layer2": 0.6,
    "layer1": 0.55,
    "nft": 0.4,
}

_NEUTRAL = 0.3  # 어떤 내러티브에도 안 걸릴 때


def _matches(haystack: str, kw: str) -> bool:
    # 짧은 영문 키워드는 단어경계로(오탐 방지), 그 외엔 부분일치
    if kw.isascii() and len(kw) <= 3:
        return re.search(rf"\b{re.escape(kw)}\b", haystack) is not None
    return kw in haystack


def tag_narratives(text: str) -> list[str]:
    low = text.lower()
    return [
        canon
        for canon, kws in NARRATIVE_KEYWORDS.items()
        if any(_matches(low, kw) for kw in kws)
    ]


class NarrativeFeature(FeatureExtractor):
    name = "narrative"

    def extract(self, ctx: FeatureContext) -> FeatureScore:
        listing = ctx.listing
        heat = DEFAULT_HOT_NARRATIVES
        if ctx.config is not None and getattr(ctx.config, "hot_narratives", None):
            heat = ctx.config.hot_narratives

        haystack = " ".join([listing.title, *listing.symbols])
        tags = tag_narratives(haystack)

        if tags:
            best = max(tags, key=lambda t: heat.get(t, 0.5))
            score = heat.get(best, 0.5)
            detail = f"내러티브: {', '.join(tags)} (best={best}, heat={score})"
        else:
            score = _NEUTRAL
            detail = "매칭된 내러티브 없음"

        return FeatureScore(
            name=self.name,
            score=round(float(score), 3),
            weight=self.weight,
            available=True,
            detail=detail,
            raw={"tags": tags},
        )
