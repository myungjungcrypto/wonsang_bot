#!/usr/bin/env python3
"""따리(김프) 과거 케이스 수집 — 올바른 모델.

매수: 공지 +5분 해외(바이낸스 USDT)  /  매도: 업비트 상장 오픈(첫 캔들 KRW)
수익률 = (업비트 첫캔들 KRW / 업비트 USDT-KRW환율) / 해외 USDT매수가 - 1

데이터 경로:
- 공지 아카이브(api-manager): Cloudflare → **프록시** 사용
- 업비트 캔들(api.upbit.com)·바이낸스: 차단 없음 → **직접**

사용:
    python scripts/collect_kimchi_cases.py [출력.json]
    # 옵션: COLLECT_PAGES=40 COLLECT_ENTRY_MIN=5 COLLECT_SLEEP=0.25 COLLECT_LIMIT=0
    # COLLECT_LIMIT>0 이면 KRW 상장 앞 N개만(빠른 테스트)

그다음:
    python scripts/backfill_cases.py data/cases_kimchi.json
"""
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from datetime import datetime, timezone  # noqa: E402

from wonsang_bot.collector.archive import fetch_upbit_archive  # noqa: E402
from wonsang_bot.collector.coingecko import CoinGeckoTokens  # noqa: E402
from wonsang_bot.collector.dex import GeckoTerminalDEX  # noqa: E402
from wonsang_bot.collector.exchanges import (  # noqa: E402
    Quote,
    build_overseas_aggregator,
    choose_buy_venue,
)
from wonsang_bot.collector.kimchi import kimchi_return_pct  # noqa: E402
from wonsang_bot.collector.upbit_market import UpbitMarketBackfiller  # noqa: E402
from wonsang_bot.config import Config  # noqa: E402
from wonsang_bot.detector.contract_extract import extract_contracts_from_text  # noqa: E402
from wonsang_bot.detector.parser import parse_title  # noqa: E402
from wonsang_bot.detector.sources.upbit import UpbitSource  # noqa: E402
from wonsang_bot.httpclient import HttpClient  # noqa: E402
from wonsang_bot.logging_conf import setup_logging  # noqa: E402
from wonsang_bot.predictor.features.base import parse_iso  # noqa: E402

log = logging.getLogger(__name__)


def main() -> None:
    out_path = sys.argv[1] if len(sys.argv) > 1 else "data/cases_kimchi.json"
    pages = int(os.environ.get("COLLECT_PAGES", "40"))
    entry_offset = float(os.environ.get("COLLECT_ENTRY_MIN", "5")) * 60
    sleep_s = float(os.environ.get("COLLECT_SLEEP", "0"))  # throttle 가 페이싱 담당
    dex_min_liq = float(os.environ.get("COLLECT_DEX_MIN_LIQ", "30000"))  # 실매수 가능 풀만
    limit = int(os.environ.get("COLLECT_LIMIT", "0"))

    config = Config.load()
    setup_logging(config.log_level)

    # 공지: 프록시(Cloudflare 우회). 업비트/바이낸스: 직접 + 레이트리밋 throttle.
    http_proxy = HttpClient(timeout=config.http_timeout_sec, proxy=config.http_proxy,
                            user_agent=config.request_user_agent,
                            min_interval=0.5, max_retries=3)
    # 업비트 quotation 한도 ~10req/s → 0.2s 간격(5req/s) + 429 백오프
    http_upbit = HttpClient(timeout=config.http_timeout_sec, proxy=None,
                            user_agent=config.request_user_agent,
                            min_interval=0.2, max_retries=5)
    upbit = UpbitMarketBackfiller(http_upbit)
    overseas = build_overseas_aggregator(config)  # 7개 CEX 집계(거래소별 독립 client)
    src = UpbitSource(config.upbit_announcements_url, http_proxy)  # 공지 본문(컨트랙트)
    # DEX: Geckoterminal 무료 ~30/min → 간격 넉넉히(env로 조정) + 429 긴 백오프
    dex_interval = float(os.environ.get("COLLECT_DEX_INTERVAL", "4.0"))
    http_dex = HttpClient(timeout=config.http_timeout_sec, proxy=None,
                          user_agent=config.request_user_agent,
                          min_interval=dex_interval, max_retries=4, backoff=5.0)
    dex = GeckoTerminalDEX(http_dex)
    # 같은 코인의 전체 체인 컨트랙트 해소(체인마다 주소 다름) — coingecko
    cg_tokens = None
    if config.coingecko_enabled:
        http_cg = HttpClient(timeout=config.http_timeout_sec, proxy=None,
                             user_agent=config.request_user_agent,
                             min_interval=2.0, max_retries=3, backoff=5.0)
        cg_tokens = CoinGeckoTokens(config, http_cg)
    else:
        log.warning("COINGECKO_ENABLED=false → 체인간 컨트랙트 해소 불가(공지 체인만 DEX 조회)")

    anns = fetch_upbit_archive(http_proxy, config.upbit_announcements_url, pages=pages)
    log.info("공지 아카이브 %d건 수신 (pages=%d)", len(anns), pages)

    cases: list[dict] = []
    seen: set[str] = set()
    for ann in anns:
        parsed = parse_title(ann.title)
        if not (parsed.is_listing and parsed.is_krw and parsed.symbols):
            continue
        dt = parse_iso(ann.published_at)
        if dt is None:
            continue
        announce_ts = dt.timestamp()

        # 공지 본문에서 컨트랙트 추출(DEX 가격·충돌제거 기준점)
        try:
            body = src.fetch_detail(ann)
        except Exception:  # noqa: BLE001
            body = None
        contracts = extract_contracts_from_text(body) if body else []

        for symbol in parsed.symbols:
            if symbol in seen:
                continue
            seen.add(symbol)
            if limit and len(cases) >= limit:
                break

            market = f"KRW-{symbol}"
            try:
                listing_ts, krw_sell = upbit.first_candle(market)
                if listing_ts is None:
                    log.info("스킵 %s: 업비트 KRW 마켓 없음(상장폐지/개명)", symbol)
                    continue
                buy_ts = announce_ts + entry_offset
                # --- 구매처 전부 탐색(CEX+DEX) → 유동성 컷 → 최저가 ---
                # (1) 신원 확정: 공지 컨트랙트 중 상장심볼과 같은 토큰 → coin_id + 전체체인 주소.
                #     본문엔 여러 토큰 주소가 섞일 수 있음(USDS 공지에 SKY 주소까지).
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
                # (2) CEX: 코인게코 티커로 '이 코인을 실제 상장한 거래소'만(충돌 토큰 배제).
                if resolved is not None:
                    cex_only = cg_tokens.exchanges_for(resolved.coin_id)
                    venues = overseas.fetch_venues(symbol, buy_ts, only=cex_only)
                    chain_addrs = dict(resolved.platforms)
                elif cg_tokens is None:
                    venues = overseas.fetch_venues(symbol, buy_ts)  # 심볼 신뢰(충돌위험)
                    chain_addrs = ({contracts[0].chain: contracts[0].address}
                                   if contracts else {})
                elif identified:
                    # 신원 확인됐는데 상장심볼과 불일치 → 다른 토큰 → 신뢰 불가(스킵 유도)
                    log.info("스킵 %s: 공지 컨트랙트가 상장심볼과 불일치(다른 토큰)", symbol)
                    venues, chain_addrs = {}, {}
                else:
                    # 코인게코가 못 알아본 신규 토큰 → 첫 주소 DEX + 심볼 CEX best-effort
                    venues = overseas.fetch_venues(symbol, buy_ts)
                    chain_addrs = ({contracts[0].chain: contracts[0].address}
                                   if contracts else {})
                # (3) DEX: 같은 토큰의 전체 체인 풀(브릿지 가능=같은 토큰) → 체인별 구매처.
                for ch, ad in chain_addrs.items():
                    dq = dex.quote_at(ch, ad, buy_ts)
                    if dq:
                        venues[f"dex:{ch}"] = {"price": round(dq[0], 8),
                                               "liq": round(dq[1], 2), "kind": "dex"}
                # (4) 유동성 컷(DEX reserve>=min_liq) 통과분 중 최저가.
                p, v, sp = choose_buy_venue(venues, dex_min_liq=dex_min_liq)
                quote = Quote(buy_price=p, buy_venue=v, price_spread=sp, venues=venues)
                used_dex = bool(v and v.startswith("dex"))
                usd_buy = quote.buy_price  # 유동성 통과 구매처 중 최저가
                if usd_buy is None:
                    log.info("스킵 %s: 매수 가능 구매처 없음(유동성 부족/TGE 동시상장 의심)",
                             symbol)
                    continue
                usdt_krw = upbit.price_at("KRW-USDT", listing_ts)
                if usdt_krw is None:
                    log.info("스킵 %s: 업비트 USDT-KRW 환율 없음", symbol)
                    continue
            except Exception:  # noqa: BLE001
                log.exception("수집 실패 %s", symbol)
                continue
            finally:
                time.sleep(sleep_s)

            ret = kimchi_return_pct(usd_buy, krw_sell, usdt_krw)
            if ret is None:
                continue

            # KRW만 추가(기존 코인) 여부: 공지 1시간 전 BTC/USDT 마켓 캔들이 있었나
            pre_listed = False
            for q in ("BTC", "USDT"):
                try:
                    if upbit.price_at(f"{q}-{symbol}", announce_ts - 3600) is not None:
                        pre_listed = True
                        break
                except Exception:  # noqa: BLE001 - 없는 마켓은 그냥 신규
                    pass

            cases.append({
                "id": f"upbit:{symbol}",
                "symbol": symbol,
                "source": "upbit",
                "title": ann.title,
                "listed_at": dt.isoformat(),
                "is_krw": True,
                "contracts": [{"chain": c.chain, "address": c.address} for c in contracts],
                "realized_return_pct": ret,
                "market_cap_usd": None,
                "mentions_per_hour": None,
                "pre_listed": pre_listed,
                "meta": {
                    "announce_ts": announce_ts,
                    "listing_ts": listing_ts,
                    "usd_buy": usd_buy,
                    "krw_sell": krw_sell,
                    "usdt_krw": usdt_krw,
                    "gap_hours": round((listing_ts - announce_ts) / 3600, 2),
                    "buy_venue": quote.buy_venue,      # 매수처(유동성 최대)
                    "price_spread": quote.price_spread,  # 거래소간 가격차(충돌 진단)
                    "venues": quote.venues,            # name→{price,liq}
                    "venue_count": len(quote.venues),  # 가용성 피처
                },
            })
            log.info("케이스 %s: 매수$%.4f@%s(%d곳%s,스프레드%.0f%%) ret=%.1f%% %s (gap %.1fh)",
                     symbol, usd_buy, quote.buy_venue, len(quote.venues),
                     "+DEX" if used_dex else "",
                     quote.price_spread * 100, ret,
                     "[KRW만추가]" if pre_listed else "[신규]",
                     (listing_ts - announce_ts) / 3600)
        if limit and len(cases) >= limit:
            break

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({
            "note": (f"collect_kimchi_cases.py (공지+{entry_offset/60:.0f}분 해외 USDT 매수 "
                     "→ 업비트 상장오픈 KRW 매도, USDT-KRW 환율 적용)."),
            "cases": cases,
        }, fh, ensure_ascii=False, indent=2)
    print(f"수집 완료: {len(cases)}건 → {out_path}")


if __name__ == "__main__":
    main()
