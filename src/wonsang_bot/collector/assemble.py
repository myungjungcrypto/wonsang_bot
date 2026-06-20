"""공지 + 파싱결과 + 컨트랙트 + 실현수익률 → RawCase dict (백필 입력 형식).

순수 함수 — 네트워크에서 모은 값들을 backfill 이 먹는 형식으로 조립만 한다.
"""
from __future__ import annotations

from typing import Optional

from ..core.events import Announcement, Contract
from ..detector.parser import ListingParse


def to_raw_case(
    ann: Announcement,
    parsed: ListingParse,
    contracts: list[Contract],
    realized_return_pct: float,
    listed_at: Optional[str] = None,
    market_cap_usd: Optional[float] = None,
    mentions_per_hour: Optional[float] = None,
) -> dict:
    symbol = parsed.symbols[0] if parsed.symbols else ""
    return {
        "id": ann.key,
        "symbol": symbol,
        "source": ann.source,
        "title": ann.title,
        "listed_at": listed_at or ann.published_at or "",
        "is_krw": parsed.is_krw,
        "contracts": [{"chain": c.chain, "address": c.address} for c in contracts],
        "realized_return_pct": realized_return_pct,
        "market_cap_usd": market_cap_usd,
        "mentions_per_hour": mentions_per_hour,
        "meta": {
            "announcement_id": ann.id,
            "url": ann.url,
            "all_symbols": parsed.symbols,
            "markets": parsed.markets,
        },
    }
