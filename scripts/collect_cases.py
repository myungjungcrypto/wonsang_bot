#!/usr/bin/env python3
"""과거 케이스 수집 (망 허용 환경 / 서울 IP 권장).

라벨 방법론: 상장 공지 +5분 가격에 매수 → 상장 직후 업비트/빗썸 국내가 고점에 매도.
공지 아카이브 + 국내 KRW 캔들 + (선택)코인게코 시총 → 백필 입력(cases JSON).

사용:
    python scripts/collect_cases.py [출력.json]
    # 옵션: COLLECT_PAGES=20 COLLECT_WINDOW_H=6 COLLECT_ENTRY_MIN=5 COLLECT_SLEEP=0.3
    # 시총 스냅샷도 원하면: COINGECKO_ENABLED=true

그다음:
    python scripts/backfill_cases.py data/cases_collected.json

⚠️ 업비트/빗썸 공지·캔들은 해외 IP 차단이 잦음 → 서울 EC2 또는 HTTP_PROXY_URL.
⚠️ 엔드포인트/스키마는 라이브에서 재검증(파서는 격리됨). 빗썸 공개 캔들은 최근
   구간만 제공 → 오래된 빗썸 상장은 수익률을 못 구할 수 있음(업비트는 `to`로 과거 가능).
"""
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from wonsang_bot.collector.archive import fetch_upbit_archive  # noqa: E402
from wonsang_bot.collector.assemble import to_raw_case  # noqa: E402
from wonsang_bot.collector.price import (  # noqa: E402
    CoinGeckoPriceProvider,
    domestic_provider_for,
)
from wonsang_bot.config import Config  # noqa: E402
from wonsang_bot.detector.parser import parse_title  # noqa: E402
from wonsang_bot.detector.sources.upbit import UpbitSource  # noqa: E402
from wonsang_bot.httpclient import HttpClient  # noqa: E402
from wonsang_bot.logging_conf import setup_logging  # noqa: E402
from wonsang_bot.predictor.features.base import parse_iso  # noqa: E402
from wonsang_bot.resolver.contract import ContractResolver  # noqa: E402

log = logging.getLogger(__name__)


def main() -> None:
    out_path = sys.argv[1] if len(sys.argv) > 1 else "data/cases_collected.json"
    pages = int(os.environ.get("COLLECT_PAGES", "10"))
    window_sec = float(os.environ.get("COLLECT_WINDOW_H", "6")) * 3600
    entry_offset = float(os.environ.get("COLLECT_ENTRY_MIN", "5")) * 60
    sleep_s = float(os.environ.get("COLLECT_SLEEP", "0.3"))

    config = Config.load()
    setup_logging(config.log_level)

    http = HttpClient(
        timeout=config.http_timeout_sec,
        proxy=config.http_proxy,
        user_agent=config.request_user_agent,
    )
    resolver = ContractResolver(config, http)
    src = UpbitSource(config.upbit_announcements_url, http)
    cg = CoinGeckoPriceProvider(config, http) if config.coingecko_enabled else None

    anns = fetch_upbit_archive(http, config.upbit_announcements_url, pages=pages)
    log.info("아카이브 수집: 공지 %d건 (pages=%d)", len(anns), pages)

    cases: list[dict] = []
    for ann in anns:
        parsed = parse_title(ann.title)
        if not (parsed.is_listing and parsed.is_krw and parsed.symbols):
            continue
        dt = parse_iso(ann.published_at)
        if dt is None:
            log.debug("상장시각 파싱 실패, 건너뜀: %s", ann.title)
            continue
        listing_ts = dt.timestamp()
        symbol = parsed.symbols[0]

        # 국내 수익률(진입 +5분 → 윈도 고점)
        provider = domestic_provider_for(ann.source, http)
        ret = None
        if provider is not None:
            try:
                ret = provider.realized_return(
                    symbol, listing_ts,
                    entry_offset_sec=entry_offset, window_sec=window_sec,
                )
                time.sleep(sleep_s)
            except Exception:  # noqa: BLE001
                log.exception("국내 수익률 수집 실패: %s", symbol)
        if ret is None:
            log.info("수익률 미확보, 건너뜀: %s (%s)", symbol, ann.source)
            continue

        # 컨트랙트(본문 + 코인게코)
        body = None
        try:
            body = src.fetch_detail(ann)
        except Exception:  # noqa: BLE001
            pass
        contracts = resolver.resolve(parsed.symbols, ann, body)

        # 시총 스냅샷(선택, 피처용)
        mcap = None
        if cg is not None:
            try:
                coin_id = cg.resolve_coin_id(symbol)
                if coin_id:
                    mcap = cg.market_cap_usd(coin_id)
                time.sleep(sleep_s)
            except Exception:  # noqa: BLE001
                log.exception("시총 수집 실패: %s", symbol)

        cases.append(
            to_raw_case(
                ann, parsed, contracts, ret,
                listed_at=dt.isoformat(), market_cap_usd=mcap,
            )
        )
        log.info("케이스: %s ret=%.1f%% mcap=%s", symbol, ret, mcap)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "note": (
                    f"collect_cases.py 자동수집 (pages={pages}, "
                    f"entry=+{entry_offset/60:.0f}분, window={window_sec/3600:.0f}h). "
                    "realized_return_pct = 진입(+5분) 대비 국내 KRW 고점 수익률."
                ),
                "cases": cases,
            },
            fh, ensure_ascii=False, indent=2,
        )
    print(f"수집 완료: {len(cases)}건 → {out_path}")


if __name__ == "__main__":
    main()
