#!/usr/bin/env python3
"""따리(김프) 과거 케이스 수집 — 올바른 모델.

매수: 공지 +5분 해외(바이낸스 USDT)  /  매도: 업비트 상장 오픈(첫 캔들 KRW)
수익률 = (업비트 첫캔들 KRW / 업비트 USDT-KRW환율) / 해외 USDT매수가 - 1

데이터 경로:
- 공지 아카이브(api-manager): Cloudflare → **프록시** 사용
- 업비트 캔들(api.upbit.com)·바이낸스: 차단 없음 → **직접**

사용:
    # 최근 50개만(빠름, 분석도 보통 최근 50건 기준):
    COLLECT_LIMIT=50 python scripts/collect_kimchi_cases.py data/cases_kimchi.json
    # 증분(기존 파일에 새 상장만 추가 — 반복 실행이 빠름):
    COLLECT_APPEND=1 python scripts/collect_kimchi_cases.py data/cases_kimchi.json
    # 전체 재수집(필드 추가 후 전부 갱신할 때):
    python scripts/collect_kimchi_cases.py data/cases_kimchi.json

    # 그 외 옵션: COLLECT_PAGES=40 COLLECT_ENTRY_MIN=5 COLLECT_DEX_INTERVAL=4.0
    #            COLLECT_TRADE_USD=10000 (매수규모=슬리피지 기준)
    # COLLECT_LIMIT=N 은 최신 N건만(공지는 newest-first). 증분(APPEND)과 함께면 신규 N건.

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
from wonsang_bot.collector.buyrouting import gather_buy_route  # noqa: E402
from wonsang_bot.collector.exchanges import (  # noqa: E402
    Quote,
    binance_pre_listed,
    build_overseas_aggregator,
)
from wonsang_bot.collector.kimchi import kimchi_return_pct  # noqa: E402
from wonsang_bot.collector.upbit_market import (  # noqa: E402
    BITHUMB_API,
    UpbitMarketBackfiller,
)
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
    trade_usd = float(os.environ.get("COLLECT_TRADE_USD", "10000"))  # 매수규모(슬리피지 기준)
    limit = int(os.environ.get("COLLECT_LIMIT", "0"))  # >0: 최신 N건만(빠른 테스트/갱신)
    # 증분: 기존 출력의 이미 수집한 종목은 건너뛰고 새 상장만 추가(반복 실행 빠름)
    append = os.environ.get("COLLECT_APPEND", "0").lower() not in ("0", "false", "no")

    config = Config.load()
    setup_logging(config.log_level)

    # 불변 과거데이터(캔들·컨트랙트·DEX OHLCV) 디스크 캐시 → 재실행 시 즉시(429 회피).
    cache_dir = os.environ.get("COLLECT_CACHE_DIR", "data/.httpcache")
    if cache_dir.lower() in ("", "0", "off", "none"):
        cache_dir = None

    # 공지: 프록시(Cloudflare 우회). 업비트/바이낸스: 직접 + 레이트리밋 throttle.
    http_proxy = HttpClient(timeout=config.http_timeout_sec, proxy=config.http_proxy,
                            user_agent=config.request_user_agent,
                            min_interval=0.5, max_retries=3)
    # 업비트 quotation 한도 ~10req/s → 0.2s 간격(5req/s) + 429 백오프 (+캐시)
    http_upbit = HttpClient(timeout=config.http_timeout_sec, proxy=None,
                            user_agent=config.request_user_agent,
                            min_interval=0.2, max_retries=5, cache_dir=cache_dir)
    upbit = UpbitMarketBackfiller(http_upbit)
    # 빗썸(v1 업비트호환) — 기상장 여부 판정용 별도 client(레이트리밋 격리)
    http_bithumb = HttpClient(timeout=config.http_timeout_sec, proxy=None,
                              user_agent=config.request_user_agent,
                              min_interval=0.2, max_retries=3, cache_dir=cache_dir)
    bithumb = UpbitMarketBackfiller(http_bithumb, base_url=BITHUMB_API)
    # 바이낸스 선상장 판정용 client(klines 한도 넉넉 + 캐시)
    http_binance = HttpClient(timeout=config.http_timeout_sec, proxy=None,
                              user_agent=config.request_user_agent,
                              min_interval=0.1, max_retries=2, cache_dir=cache_dir)
    overseas = build_overseas_aggregator(config)  # 7개 CEX 집계(거래소별 독립 client)
    src = UpbitSource(config.upbit_announcements_url, http_proxy)  # 공지 본문(컨트랙트)

    # CoinGecko(컨트랙트·체인·티커) + DEX(Geckoterminal) 설정.
    # 키가 있으면 DEX 도 CoinGecko 온체인 API로 인증 경유 → 익명 DC-IP throttle 회피.
    # 이때 컨트랙트·DEX 가 같은 키 쿼터(30/min)를 공유하므로 **한 클라이언트로 묶어** 페이싱.
    cg_tokens = None
    dex = None
    if config.coingecko_enabled and config.coingecko_api_key:
        cg_interval = float(os.environ.get("COLLECT_CG_INTERVAL", "2.5"))  # ~24/min<30
        http_cg = HttpClient(timeout=config.http_timeout_sec, proxy=None,
                             user_agent=config.request_user_agent,
                             min_interval=cg_interval, max_retries=3, backoff=5.0,
                             cache_dir=cache_dir)
        cg_tokens = CoinGeckoTokens(config, http_cg)
        onchain_base = config.coingecko_base_url.rstrip("/") + "/onchain"
        dex_headers = ({"x-cg-pro-api-key": config.coingecko_api_key}
                       if "pro-api.coingecko.com" in onchain_base
                       else {"x-cg-demo-api-key": config.coingecko_api_key})
        dex = GeckoTerminalDEX(http_cg, base=onchain_base, headers=dex_headers)
        log.info("CoinGecko 키 사용 → 컨트랙트+DEX 인증 경유(공유 페이싱 %.1fs)", cg_interval)
    else:
        # 무키: 공개 Geckoterminal(자체 ~30/min, DC-IP throttle 잦음) + 활성 시 공개 CoinGecko
        dex_interval = float(os.environ.get("COLLECT_DEX_INTERVAL", "4.0"))
        http_dex = HttpClient(timeout=config.http_timeout_sec, proxy=None,
                              user_agent=config.request_user_agent,
                              min_interval=dex_interval, max_retries=4, backoff=5.0,
                              cache_dir=cache_dir)
        dex = GeckoTerminalDEX(http_dex)
        if config.coingecko_enabled:
            cg_interval = float(os.environ.get("COLLECT_CG_INTERVAL", "2.0"))
            http_cg = HttpClient(timeout=config.http_timeout_sec, proxy=None,
                                 user_agent=config.request_user_agent,
                                 min_interval=cg_interval, max_retries=3, backoff=5.0,
                                 cache_dir=cache_dir)
            cg_tokens = CoinGeckoTokens(config, http_cg)
            log.warning("CoinGecko 키 없음 → DEX는 공개 Geckoterminal(DC-IP 429 잦음). "
                        "무료 Demo 키 권장(COINGECKO_API_KEY).")
        else:
            log.warning("COINGECKO_ENABLED=false → 체인간 컨트랙트 해소 불가(공지 체인만 DEX 조회)")

    anns = fetch_upbit_archive(http_proxy, config.upbit_announcements_url, pages=pages)
    log.info("공지 아카이브 %d건 수신 (pages=%d)", len(anns), pages)

    # 증분 모드: 기존 케이스 로드 → 이미 수집한 종목은 seen 으로 건너뜀
    existing: list[dict] = []
    seen: set[str] = set()
    if append and os.path.exists(out_path):
        try:
            with open(out_path, encoding="utf-8") as fh:
                prev = json.load(fh)
            existing = prev.get("cases", prev) if isinstance(prev, dict) else prev
            seen = {c.get("symbol") for c in existing if c.get("symbol")}
            log.info("증분 모드: 기존 %d건 로드 → %d종목 건너뜀(새 상장만 추가)",
                     len(existing), len(seen))
        except Exception:  # noqa: BLE001
            log.exception("기존 케이스 로드 실패 → 전체 수집")

    cases: list[dict] = []
    for ann in anns:
        if limit and len(cases) >= limit:
            break
        parsed = parse_title(ann.title)
        if not (parsed.is_listing and parsed.is_krw and parsed.symbols):
            continue
        # 이미 수집한 상장은 본문 fetch 도 생략(증분 빠르게)
        if all(s in seen for s in parsed.symbols):
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
                # 구매처 탐색(CEX+DEX) → 유동성 컷 → 최저가. 백필·라이브 공용 로직.
                route = gather_buy_route(
                    symbol, buy_ts, contracts,
                    overseas=overseas, dex=dex, cg_tokens=cg_tokens,
                    dex_min_liq=dex_min_liq, trade_usd=trade_usd,
                )
                if route.mismatch:
                    log.info("스킵 %s: 공지 컨트랙트가 상장심볼과 불일치(다른 토큰)", symbol)
                resolved_coin_id = route.coin_id
                quote = Quote(buy_price=route.buy_price, buy_venue=route.buy_venue,
                              price_spread=route.price_spread, venues=route.venues)
                used_dex = route.used_dex
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

            # 빗썸 기상장 여부: 공지 1시간 전 빗썸 KRW 마켓 캔들이 있었나
            pre_listed_bithumb: bool | None
            try:
                pre_listed_bithumb = (
                    bithumb.price_at(f"KRW-{symbol}", announce_ts - 3600) is not None
                )
            except Exception:  # noqa: BLE001 - 조회 실패는 미상(None)
                pre_listed_bithumb = None

            # 바이낸스 선상장 여부: 공지 1시간 전 바이낸스 USDT 일봉이 있었나
            pre_listed_binance = binance_pre_listed(http_binance, symbol,
                                                    announce_ts - 3600)

            # 과거 시총: 신원확정(coin_id) 시 상장일 CoinGecko 시총(백필 marketcap 피처용)
            market_cap_usd = None
            if cg_tokens is not None and resolved_coin_id:
                market_cap_usd = cg_tokens.market_cap_at(resolved_coin_id, announce_ts)

            cases.append({
                "id": f"upbit:{symbol}",
                "symbol": symbol,
                "source": "upbit",
                "title": ann.title,
                "listed_at": dt.isoformat(),
                "is_krw": True,
                "contracts": [{"chain": c.chain, "address": c.address} for c in contracts],
                "realized_return_pct": ret,
                "market_cap_usd": market_cap_usd,
                "mentions_per_hour": None,
                "pre_listed": pre_listed,
                "pre_listed_bithumb": pre_listed_bithumb,
                "pre_listed_binance": pre_listed_binance,
                "meta": {
                    "announce_ts": announce_ts,
                    "listing_ts": listing_ts,
                    "usd_buy": usd_buy,                 # 유효 체결가(슬리피지·수수료 반영)
                    "trade_usd": trade_usd,            # 매수 규모(슬리피지 기준)
                    "krw_sell": krw_sell,
                    "usdt_krw": usdt_krw,
                    "gap_hours": round((listing_ts - announce_ts) / 3600, 2),
                    "buy_venue": quote.buy_venue,      # 매수처(유효가 최저)
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

    all_cases = existing + cases   # 증분이면 기존 + 신규, 아니면 신규만(=전체)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({
            "note": (f"collect_kimchi_cases.py (공지+{entry_offset/60:.0f}분 해외 USDT 매수 "
                     "→ 업비트 상장오픈 KRW 매도, USDT-KRW 환율 적용)."),
            "cases": all_cases,
        }, fh, ensure_ascii=False, indent=2)
    if append:
        print(f"수집 완료: 신규 {len(cases)}건 (총 {len(all_cases)}건) → {out_path}")
    else:
        print(f"수집 완료: {len(all_cases)}건 → {out_path}")


if __name__ == "__main__":
    main()
