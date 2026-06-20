"""공급 병목(supply choke) 점수 — 이벤트 정보만으로 계산하는 휴리스틱.

가정: 입금 가능한 매도 물량이 적을수록(=공급 병목) 갭이 커진다.
- 빗썸은 출금 한도가 있어 외부 물량 유입이 더 막힘 → 병목↑
- 토큰의 체인이 입금 친화적(주요 EVM/솔라나 등)이면 물량 유입 쉬움 → 병목↓
- 입금 친화 체인이 하나도 없으면(또는 컨트랙트 미확인) → 병목↑

⚠️ 정밀 버전(거래소별 입금 네트워크·출금한도·팀물량)은 Phase 3에서 venue/온체인
데이터로 대체. 지금은 라이브 캘리브레이션 전의 합리적 기본값.
"""
from __future__ import annotations

from ...core.events import FeatureScore
from .base import FeatureContext, FeatureExtractor, clamp01

# 국내 거래소가 흔히 입금 지원하는(=물량 유입 쉬운) 체인
DEPOSIT_FRIENDLY = {"ethereum", "bsc", "tron", "solana", "polygon", "base", "arbitrum"}


class SupplyChokeFeature(FeatureExtractor):
    name = "supply_distribution"

    def extract(self, ctx: FeatureContext) -> FeatureScore:
        ev = ctx.listing
        score = 0.4
        notes: list[str] = []

        if ev.source == "bithumb":
            score += 0.15
            notes.append("빗썸(출금한도)")
        if ev.is_krw:
            score += 0.05

        chains = {c.chain for c in ev.contracts}
        if not chains:
            notes.append("컨트랙트 미확인(공급 불명)")
            # 컨트랙트가 없으면 공급 판단 근거가 약함 → 중립 쪽으로
            score += 0.05
        elif chains & DEPOSIT_FRIENDLY:
            score -= 0.1
            notes.append("입금친화 체인(물량유입 용이)")
        else:
            score += 0.2
            notes.append("입금 어려운 체인(공급 병목)")

        score = clamp01(score)
        return FeatureScore(
            name=self.name,
            score=round(score, 3),
            weight=self.weight,
            available=True,
            detail="; ".join(notes) if notes else "기본",
            raw={"chains": sorted(chains)},
        )
