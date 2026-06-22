#!/usr/bin/env python3
"""구매처 탐색 + 매수처 산정 빠른 점검 (공지 재수집 없이).

수집기와 동일한 로직(심볼로 올바른 컨트랙트 선택 → CEX 신원검증(코인게코 티커) →
체인별 DEX → 유동성 컷 → 최저가)을 재현해, 특정 심볼·컨트랙트가 어떻게
매수처/가격으로 귀결되는지 즉시 확인.

사용:
    # 기본: USDS 두 컨트랙트(SKY 0x5607.. / USDS 0xdC03..) 재현
    python scripts/debug_pick.py
    # 임의: 심볼과 chain:address 목록(+선택 unix타임스탬프)
    python scripts/debug_pick.py USDS ethereum:0xdC03.. ethereum:0x5607.. 1774927229
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from wonsang_bot.collector.coingecko import CoinGeckoTokens  # noqa: E402
from wonsang_bot.collector.dex import GeckoTerminalDEX  # noqa: E402
from wonsang_bot.collector.exchanges import (  # noqa: E402
    build_overseas_aggregator,
    choose_buy_venue,
)
from wonsang_bot.config import Config  # noqa: E402
from wonsang_bot.httpclient import HttpClient  # noqa: E402
from wonsang_bot.logging_conf import setup_logging  # noqa: E402

# 기본값: USDS 케이스(공지에 SKY 주소까지 섞였던 그 케이스)
DEFAULT_SYMBOL = "USDS"
DEFAULT_CONTRACTS = [
    ("ethereum", "0xdC035D45d973E3EC169d2276DDab16f1e407384F"),  # USDS(진짜)
    ("ethereum", "0x56072C95FAA701256059aa122697B133aDEd9279"),  # SKY(섞여든 것)
]


def main() -> None:
    args = sys.argv[1:]
    ts = time.time()
    if args and args[-1].isdigit():
        ts = float(args.pop())
    if args:
        symbol = args[0]
        contracts = []
        for a in args[1:]:
            ch, _, ad = a.partition(":")
            contracts.append((ch, ad))
    else:
        symbol, contracts = DEFAULT_SYMBOL, DEFAULT_CONTRACTS

    config = Config.load()
    setup_logging(config.log_level)
    dex_min_liq = float(os.environ.get("COLLECT_DEX_MIN_LIQ", "30000"))

    overseas = build_overseas_aggregator(config)
    dex = GeckoTerminalDEX(HttpClient(
        timeout=config.http_timeout_sec, proxy=None,
        user_agent=config.request_user_agent, min_interval=4.0, max_retries=4, backoff=5.0))
    cg = None
    if config.coingecko_enabled:
        cg = CoinGeckoTokens(config, HttpClient(
            timeout=config.http_timeout_sec, proxy=None,
            user_agent=config.request_user_agent, min_interval=2.0, max_retries=3, backoff=5.0))

    print(f"심볼={symbol}  ts={int(ts)}  컨트랙트 {len(contracts)}개")

    # (1) 신원 확정: 상장심볼과 같은 컨트랙트 선별
    resolved = None
    identified = False
    if cg is not None:
        for ch, ad in contracts:
            r = cg.resolve(ch, ad)
            mark = "  ← 채택" if (r.symbol == symbol.lower()) else ""
            print(f"  {ch}:{ad}  symbol={r.symbol} id={r.coin_id} "
                  f"chains={list(r.platforms)}{mark}")
            if r.symbol:
                identified = True
                if r.symbol == symbol.lower() and resolved is None:
                    resolved = r

    # (2) CEX: 코인게코 티커로 검증된 거래소만
    if resolved is not None:
        cex_only = cg.exchanges_for(resolved.coin_id)
        print(f"  코인게코 검증 거래소(CEX): {cex_only or '없음'}")
        venues = overseas.fetch_venues(symbol, ts, only=cex_only)
        chain_addrs = dict(resolved.platforms)
    elif cg is None:
        venues = overseas.fetch_venues(symbol, ts)
        chain_addrs = {contracts[0][0]: contracts[0][1]} if contracts else {}
    elif identified:
        print("  ⚠️ 상장심볼과 일치하는 컨트랙트 없음(다른 토큰) → 매수처 없음")
        venues, chain_addrs = {}, {}
    else:
        venues = overseas.fetch_venues(symbol, ts)
        chain_addrs = {contracts[0][0]: contracts[0][1]} if contracts else {}
        print("  (코인게코 미식별 → 첫 주소 DEX + 심볼 CEX best-effort)")
    print(f"  CEX venues: {venues}")

    # (3) DEX: 전체 체인 풀
    for ch, ad in chain_addrs.items():
        dq = dex.quote_at(ch, ad, ts)
        ok = dq and dq[1] >= dex_min_liq
        print(f"  DEX {ch}:{ad} → {dq}  {'유동성OK' if ok else '제외'}")
        if dq:
            venues[f"dex:{ch}"] = {"price": round(dq[0], 8), "liq": round(dq[1], 2),
                                   "kind": "dex"}

    # (4) 유동성 컷 → 최저가
    p, v, sp = choose_buy_venue(venues, dex_min_liq=dex_min_liq)
    print(f"\n=> buy_venue={v}  usd_buy={p}  spread={sp}")


if __name__ == "__main__":
    main()
