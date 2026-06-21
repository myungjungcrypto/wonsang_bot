#!/usr/bin/env python3
"""업비트 마켓목록 기반 과거 케이스 수집 (Cloudflare 우회).

공지 API가 Cloudflare로 막힐 때 사용. api.upbit.com(차단 안 됨)만 사용:
현재 KRW 상장 코인 전체 → 각 첫 캔들(상장)에서 +5분 매수/+15분 매도 수익률.

사용:
    python scripts/collect_upbit_market.py [출력.json]
    # 옵션: COLLECT_ENTRY_MIN=5 COLLECT_EXIT_MIN=15 COLLECT_SLEEP=0.2 COLLECT_LIMIT=0
    # COLLECT_LIMIT>0 이면 앞에서 N개만(빠른 테스트용)

그다음:
    python scripts/backfill_cases.py data/cases_upbit.json
"""
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from datetime import datetime, timezone  # noqa: E402

from wonsang_bot.collector.upbit_market import UpbitMarketBackfiller  # noqa: E402
from wonsang_bot.config import Config  # noqa: E402
from wonsang_bot.httpclient import HttpClient  # noqa: E402
from wonsang_bot.logging_conf import setup_logging  # noqa: E402

log = logging.getLogger(__name__)


def main() -> None:
    out_path = sys.argv[1] if len(sys.argv) > 1 else "data/cases_upbit.json"
    entry_offset = float(os.environ.get("COLLECT_ENTRY_MIN", "5")) * 60
    exit_offset = float(os.environ.get("COLLECT_EXIT_MIN", "15")) * 60
    sleep_s = float(os.environ.get("COLLECT_SLEEP", "0.2"))
    limit = int(os.environ.get("COLLECT_LIMIT", "0"))

    config = Config.load()
    setup_logging(config.log_level)
    http = HttpClient(
        timeout=config.http_timeout_sec,
        proxy=config.http_proxy,
        user_agent=config.request_user_agent,
    )
    bf = UpbitMarketBackfiller(http)

    markets = bf.fetch_krw_markets()
    if limit > 0:
        markets = markets[:limit]
    log.info("KRW 마켓 %d개 수집 시작 (entry+%.0f분/exit+%.0f분)",
             len(markets), entry_offset / 60, exit_offset / 60)

    cases: list[dict] = []
    for i, m in enumerate(markets, 1):
        try:
            listing_ts, ret = bf.listing_and_return(m["market"], entry_offset, exit_offset)
        except Exception:  # noqa: BLE001
            log.exception("수집 실패: %s", m["market"])
            listing_ts, ret = None, None
        time.sleep(sleep_s)
        if listing_ts is None or ret is None:
            log.info("[%d/%d] %s 건너뜀(데이터 없음)", i, len(markets), m["symbol"])
            continue
        listed_at = datetime.fromtimestamp(listing_ts, tz=timezone.utc).isoformat()
        cases.append(
            {
                "id": f"upbit:{m['market']}",
                "symbol": m["symbol"],
                "source": "upbit",
                "title": m["name"],          # 내러티브 태깅용(코인명)
                "listed_at": listed_at,
                "is_krw": True,
                "contracts": [],
                "realized_return_pct": ret,
                "market_cap_usd": None,
                "mentions_per_hour": None,
                "meta": {"market": m["market"], "name": m["name"]},
            }
        )
        log.info("[%d/%d] %s 상장=%s ret=%.1f%%", i, len(markets),
                 m["symbol"], listed_at[:10], ret)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "note": (
                    f"collect_upbit_market.py (market/all + 첫캔들, "
                    f"매수+{entry_offset/60:.0f}분/매도+{exit_offset/60:.0f}분). "
                    "Cloudflare 우회: api.upbit.com 만 사용."
                ),
                "cases": cases,
            },
            fh, ensure_ascii=False, indent=2,
        )
    print(f"수집 완료: {len(cases)}건 → {out_path}")


if __name__ == "__main__":
    main()
