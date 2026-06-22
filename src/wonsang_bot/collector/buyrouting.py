"""구매처 탐색 — 백필·라이브 공용 (사용자 원칙: 둘이 같은 행동).

신원(컨트랙트/티커)으로 같은 토큰을 CEX·DEX 전체에서 찾고 → 유동성 적은 곳 제거 →
남은 구매처 중 최저가. backfill(collect_kimchi)과 live(예측 시 venue_count·구매처추천)이
이 함수를 함께 쓴다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from .exchanges import TRADE_USD_DEFAULT, OverseasAggregator, choose_buy_venue

log = logging.getLogger(__name__)


@dataclass(slots=True)
class BuyRoute:
    buy_price: Optional[float]               # 유동성 통과 구매처 중 최저가
    buy_venue: Optional[str]                 # 매수처 이름(cex명 또는 dex:chain)
    price_spread: float = 0.0
    venues: dict[str, dict] = field(default_factory=dict)  # name→{price,liq,kind}
    used_dex: bool = False
    coin_id: Optional[str] = None            # 코인게코 신원(시총 등 재사용)
    mismatch: bool = False                   # 컨트랙트가 상장심볼과 불일치(다른 토큰)
    platforms: dict[str, str] = field(default_factory=dict)  # {chain: token주소}(브릿지용)

    @property
    def venue_count(self) -> int:
        return len(self.venues)

    @property
    def buy_chain(self) -> Optional[str]:
        """매수처가 DEX면 그 체인(dex:<chain>), CEX면 None(출금 시 네트워크 선택)."""
        if self.buy_venue and self.buy_venue.startswith("dex:"):
            return self.buy_venue.split(":", 1)[1]
        return None


def gather_buy_route(
    symbol: str,
    ts: float,
    contracts: list[Any],
    *,
    overseas: OverseasAggregator,
    dex: Any,
    cg_tokens: Any = None,
    dex_min_liq: float = 30000.0,
    trade_usd: float = TRADE_USD_DEFAULT,
) -> BuyRoute:
    """symbol 의 구매처(CEX+DEX)를 ts 시점으로 조회 → 유동성 컷 → 유효 체결가 최저.

    contracts: .chain/.address 를 가진 객체 리스트(공지 본문 추출). cg_tokens 있으면
    심볼 일치 컨트랙트로 신원 확정(전체 체인 + 티커검증 거래소). 없으면 best-effort.
    buy_price 는 trade_usd 매수 시 슬리피지·수수료 반영 유효가.
    """
    # (1) 신원 확정
    resolved = None
    identified = False
    if cg_tokens is not None:
        for c in contracts:
            r = cg_tokens.resolve(c.chain, c.address)
            if r.symbol:
                identified = True
                if r.symbol == symbol.lower():
                    resolved = r
                    break

    # (2) CEX 구매처(코인게코 티커로 검증된 거래소만 — 충돌 토큰 배제)
    if resolved is not None:
        venues = overseas.fetch_venues(symbol, ts, only=resolved.exchanges)
        chain_addrs = dict(resolved.platforms)
    elif cg_tokens is None:
        venues = overseas.fetch_venues(symbol, ts)            # 심볼 신뢰(충돌위험)
        chain_addrs = ({contracts[0].chain: contracts[0].address} if contracts else {})
    elif identified:
        # 신원 확인됐는데 상장심볼과 불일치 → 다른 토큰 → 신뢰 불가
        return BuyRoute(None, None, mismatch=True)
    else:
        venues = overseas.fetch_venues(symbol, ts)            # CG 미식별 → best-effort
        chain_addrs = ({contracts[0].chain: contracts[0].address} if contracts else {})

    # (3) DEX: 같은 토큰의 전체 체인 풀(브릿지 가능=같은 토큰)
    for ch, ad in chain_addrs.items():
        dq = dex.quote_at(ch, ad, ts)
        if dq:
            venues[f"dex:{ch}"] = {"price": round(dq[0], 8), "liq": round(dq[1], 2),
                                   "kind": "dex"}

    # (4) 유동성 컷 통과분 중 유효 체결가(슬리피지 반영) 최저
    price, venue, spread = choose_buy_venue(venues, dex_min_liq=dex_min_liq,
                                            trade_usd=trade_usd)
    return BuyRoute(
        buy_price=price, buy_venue=venue, price_spread=spread, venues=venues,
        used_dex=bool(venue and venue.startswith("dex")),
        coin_id=(resolved.coin_id if resolved else None),
        platforms=dict(resolved.platforms) if resolved else {},
    )


# 체인별 토큰 소수자릿수 추정(브릿지 fromAmount 환산용 — 정확값 없을 때 근사)
_DECIMALS_GUESS = {"solana": 9, "tron": 6}


def find_bridge_route(
    route: "BuyRoute", deposit_network: Optional[str], lifi: Any,
    trade_usd: float = TRADE_USD_DEFAULT, from_address: Optional[str] = None,
) -> dict | None:
    """매수 체인 ≠ 업비트 입금 체인이면 LI.FI 로 브릿지 경로 1건. 아니면 None.

    CEX 매수(buy_chain None)는 출금 시 네트워크 선택으로 해결 → 브릿지 불필요.
    """
    if lifi is None or not deposit_network:
        return None
    buy_chain = route.buy_chain
    if not buy_chain or buy_chain == deposit_network:
        return None
    from_token = route.platforms.get(buy_chain)
    to_token = route.platforms.get(deposit_network)
    if not from_token or not to_token or not route.buy_price:
        return None
    decimals = _DECIMALS_GUESS.get(buy_chain, 18)
    amount = max(int((trade_usd / route.buy_price) * (10 ** decimals)), 1)
    return lifi.route(buy_chain, from_token, deposit_network, to_token,
                      str(amount), from_address)


def make_venue_provider(overseas, dex, cg_tokens, dex_min_liq: float = 30000.0,
                        trade_usd: float = TRADE_USD_DEFAULT,
                        lifi: Any = None, from_address: Optional[str] = None):
    """라이브 등급예측용 — 예측 시점(현재가)에 구매처 조회 → ctx.extra 에 넣을 dict.

    반환 dict: venue_count / buy_venue / buy_price(유효가) / used_dex / venues / bridge.
    lifi 가 있고 매수 체인 ≠ 업비트 입금 체인(listing.deposit_network)이면 bridge 경로 포함.
    """
    import time as _t

    def provider(listing) -> dict | None:
        syms = getattr(listing, "symbols", None) or []
        if not syms:
            return None
        route = gather_buy_route(
            syms[0], _t.time(), getattr(listing, "contracts", []) or [],
            overseas=overseas, dex=dex, cg_tokens=cg_tokens, dex_min_liq=dex_min_liq,
            trade_usd=trade_usd,
        )
        if route.mismatch or route.venue_count == 0:
            return None
        out = {
            "venue_count": route.venue_count,
            "buy_venue": route.buy_venue,
            "buy_price": route.buy_price,
            "used_dex": route.used_dex,
            "venues": route.venues,
        }
        bridge = find_bridge_route(route, getattr(listing, "deposit_network", None),
                                   lifi, trade_usd=trade_usd, from_address=from_address)
        if bridge:
            out["bridge"] = bridge
        return out
    return provider
