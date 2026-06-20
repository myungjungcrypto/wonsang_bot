#!/usr/bin/env python3
"""과거 케이스 수집 (망 허용 환경 / 서울 IP 권장).

업비트 공지 아카이브를 훑어 과거 원화상장을 찾고, 코인게코로 상장후 실현수익률과
시총 스냅샷을 모아 백필 입력(cases JSON)을 만든다.

사용:
    COINGECKO_ENABLED=true python scripts/collect_cases.py [출력.json]
    # 옵션: COLLECT_PAGES=20 COLLECT_WINDOW_H=48 COLLECT_SLEEP=1.5

그다음:
    python scripts/backfill_cases.py data/cases_collected.json

⚠️ 업비트/빗썸 공지는 해외 IP 차단이 잦음 → 서울 EC2 또는 HTTP_PROXY_URL 사용.
⚠️ 엔드포인트/스키마는 라이브에서 재검증(어댑터 파싱부는 격리됨).
"""
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from wonsang_bot.collector.archive import fetch_upbit_archive  # noqa: E402
from wonsang_bot.collector.assemble import to_raw_case  # noqa: E402
from wonsang_bot.collector.price import CoinGeckoPriceProvider  # noqa: E402
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
    window_h = float(os.environ.get("COLLECT_WINDOW_H", "48"))
    sleep_s = float(os.environ.get("COLLECT_SLEEP", "1.5"))

    config = Config.load()
    setup_logging(config.log_level)
    if not config.coingecko_enabled:
        log.warning("COINGECKO_ENABLED=false → 실현수익률/시총 없이 진행(라벨 불완전).")

    http = HttpClient(
        timeout=config.http_timeout_sec,
        proxy=config.http_proxy,
        user_agent=config.request_user_agent,
    )
    resolver = ContractResolver(config, http)
    price = CoinGeckoPriceProvider(config, http) if config.coingecko_enabled else None
    src = UpbitSource(config.upbit_announcements_url, http)

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

        # 컨트랙트(본문 + 코인게코)
        body = None
        try:
            body = src.fetch_detail(ann)
        except Exception:  # noqa: BLE001
            pass
        contracts = resolver.resolve(parsed.symbols, ann, body)

        ret = mcap = None
        if price is not None:
            try:
                coin_id = price.resolve_coin_id(parsed.symbols[0])
                if coin_id:
                    ret = price.realized_return(coin_id, listing_ts, window_h=window_h)
                    mcap = price.market_cap_at(coin_id)
                time.sleep(sleep_s)  # 레이트리밋 예의
            except Exception:  # noqa: BLE001
                log.exception("가격/시총 수집 실패: %s", parsed.symbols[0])

        if ret is None:
            log.info("수익률 미확보, 건너뜀: %s", parsed.symbols[0])
            continue

        cases.append(
            to_raw_case(
                ann, parsed, contracts, ret,
                listed_at=dt.isoformat(), market_cap_usd=mcap,
            )
        )
        log.info("케이스: %s ret=%.1f%% mcap=%s", parsed.symbols[0], ret, mcap)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "note": f"collect_cases.py 자동 수집 (pages={pages}, window_h={window_h}). "
                        "realized_return_pct=상장후 윈도 고점 수익률(글로벌 USD 프록시).",
                "cases": cases,
            },
            fh, ensure_ascii=False, indent=2,
        )
    print(f"수집 완료: {len(cases)}건 → {out_path}")


if __name__ == "__main__":
    main()
