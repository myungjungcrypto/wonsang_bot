"""과거 케이스 백필 — 원시 상장기록 → (피처 + 실현등급) 케이스 → cases 저장.

핵심: **라이브와 동일한 FeatureExtractor 로 피처를 재구성**한다. 그래야 최근접이웃
비교가 의미 있다(같은 척도). 상장 시점의 시총/소셜 등 provider 의존 값은 원시기록에
스냅샷되어 있으면 사용하고, 없으면 해당 피처는 비활성(라이브 오프라인과 동일 처리).

입력(JSON): 리스트 또는 {"note":..., "cases":[...]} 형태.
망 차단 환경에서도 손수 수집한 데이터셋만 있으면 백필 가능.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from ..config import Config
from ..core.events import Contract, ListingDetected
from ..storage.db import Storage
from .features.base import FeatureContext, FeatureExtractor, parse_iso
from .historical import Case
from .labeling import DEFAULT_RETURN_THRESHOLDS, grade_from_return


@dataclass(slots=True)
class RawCase:
    """백필 입력 1건(과거 상장 + 실현 결과)."""
    id: str
    symbol: str
    listed_at: str                       # ISO 시각(상장 시점)
    realized_return_pct: float           # 따리로 실현 가능했던 수익률(%)
    source: str = "upbit"
    title: str = ""
    is_krw: bool = True
    contracts: list[dict] = field(default_factory=list)   # [{chain, address}]
    market_cap_usd: Optional[float] = None                # 상장시점 스냅샷(있으면)
    mentions_per_hour: Optional[float] = None             # 상장시점 스냅샷(있으면)
    pre_listed: Optional[bool] = None                     # KRW만 추가(기존 코인) 여부
    pre_listed_bithumb: Optional[bool] = None             # 빗썸 기상장 여부
    pre_listed_binance: Optional[bool] = None             # 바이낸스 기상장 여부
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "RawCase":
        return cls(
            id=str(d["id"]),
            symbol=str(d.get("symbol", "")),
            listed_at=str(d.get("listed_at", "")),
            realized_return_pct=float(d.get("realized_return_pct", 0.0)),
            source=str(d.get("source", "upbit")),
            title=str(d.get("title", "")),
            is_krw=bool(d.get("is_krw", True)),
            contracts=list(d.get("contracts", [])),
            market_cap_usd=d.get("market_cap_usd"),
            mentions_per_hour=d.get("mentions_per_hour"),
            pre_listed=d.get("pre_listed"),
            pre_listed_bithumb=d.get("pre_listed_bithumb"),
            pre_listed_binance=d.get("pre_listed_binance"),
            meta=dict(d.get("meta", {})),
        )


def raw_to_listing(raw: RawCase) -> ListingDetected:
    contracts = [
        Contract(chain=c.get("chain", ""), address=c.get("address", ""),
                 via=c.get("via", "backfill"))
        for c in raw.contracts
    ]
    listing = ListingDetected(
        source=raw.source,
        announcement_id=raw.id,
        title=raw.title or raw.symbol,
        symbols=[raw.symbol] if raw.symbol else [],
        markets=["KRW"] if raw.is_krw else [],
        is_krw=raw.is_krw,
        contracts=contracts,
        published_at=raw.listed_at or None,
        pre_listed=raw.pre_listed,
        pre_listed_bithumb=raw.pre_listed_bithumb,
        pre_listed_binance=raw.pre_listed_binance,
    )
    if raw.listed_at:
        listing.detected_at = raw.listed_at
    return listing


def build_case(
    raw: RawCase,
    extractors: list[FeatureExtractor],
    config: Config | None = None,
    thresholds: tuple[tuple[float, str], ...] = DEFAULT_RETURN_THRESHOLDS,
) -> Case:
    listing = raw_to_listing(raw)
    market_provider = (
        (lambda ev: {"market_cap_usd": raw.market_cap_usd})
        if raw.market_cap_usd is not None else None
    )
    social_provider = (
        (lambda ev: {"mentions_per_hour": raw.mentions_per_hour})
        if raw.mentions_per_hour is not None else None
    )
    ctx = FeatureContext(
        listing=listing,
        config=config,
        now=parse_iso(raw.listed_at),
        market_provider=market_provider,
        social_provider=social_provider,
        extra=dict(raw.meta),   # venue_count 등 구매처 탐색 산출값 → 피처 입력
    )
    feats = [ex.extract(ctx) for ex in extractors]
    features = {f.name: f.score for f in feats if f.available}
    grade = grade_from_return(raw.realized_return_pct, thresholds)
    meta = {
        "realized_return_pct": raw.realized_return_pct,
        "listed_at": raw.listed_at,
        "source": raw.source,
        **raw.meta,
    }
    return Case(id=raw.id, symbol=raw.symbol, features=features, grade=grade, meta=meta)


def backfill(
    raws: list[RawCase],
    extractors: list[FeatureExtractor],
    storage: Storage,
    config: Config | None = None,
    thresholds: tuple[tuple[float, str], ...] = DEFAULT_RETURN_THRESHOLDS,
) -> int:
    count = 0
    for raw in raws:
        case = build_case(raw, extractors, config=config, thresholds=thresholds)
        storage.add_case(
            {
                "id": case.id,
                "symbol": case.symbol,
                "grade": case.grade,
                "features": case.features,
                "meta": case.meta,
            }
        )
        count += 1
    return count


def load_raw_cases(path: str) -> list[RawCase]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    rows = data["cases"] if isinstance(data, dict) else data
    return [RawCase.from_dict(r) for r in rows]
