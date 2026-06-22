"""앱 조립 및 엔트리포인트."""
from __future__ import annotations

import asyncio
import logging

from .config import Config
from .core.bus import EventBus
from .core.events import GradePredicted, ListingDetected
from .collector.buyrouting import make_venue_provider
from .collector.coingecko import CoinGeckoTokens, make_market_provider
from .collector.dex import GeckoTerminalDEX
from .collector.exchanges import binance_pre_listed, build_overseas_aggregator
from .collector.lunarcrush import LunarCrushClient, make_social_provider
from .detector.service import DetectorService
from .detector.sources.bithumb import BithumbSource, bithumb_pre_listed
from .detector.sources.upbit import UpbitSource
from .httpclient import HttpClient
from .llm.client import get_llm
from .logging_conf import setup_logging
from .notify.telegram import TelegramNotifier
from .predictor.features import build_extractors
from .predictor.historical import HistoricalStore
from .predictor.service import PredictorService
from .resolver.contract import ContractResolver
from .storage.db import Storage

log = logging.getLogger(__name__)


def build_service(config: Config) -> DetectorService:
    storage = Storage(config.db_path)
    bus = EventBus()
    http = HttpClient(
        timeout=config.http_timeout_sec,
        proxy=config.http_proxy,
        user_agent=config.request_user_agent,
    )

    llm = get_llm(config, http)
    log.info("LLM: %s", "ON(%s)" % config.llm_model if llm.enabled else "OFF")

    resolver = ContractResolver(config, http)
    notifier = TelegramNotifier(
        config.telegram_token, config.telegram_chat_id, http, dry_run=config.telegram_dry_run
    )
    bus.subscribe(ListingDetected, notifier.on_listing)

    if config.predictor_enabled:
        historical = HistoricalStore.from_dicts(storage.load_cases())
        # CoinGecko(시총·신원·DEX 인증). 키 있으면 한 클라이언트로 묶어 페이싱(쿼터 공유).
        market_provider = None
        cg_tokens = None
        cg_http = None
        if config.coingecko_enabled:
            cg_http = HttpClient(
                timeout=config.http_timeout_sec, proxy=None,
                user_agent=config.request_user_agent, min_interval=2.0, max_retries=2,
            )
            cg_tokens = CoinGeckoTokens(config, cg_http)
            market_provider = make_market_provider(cg_tokens)
        # 구매처 조회 provider(venue_count 활성 + 매수처 추천) — CEX 집계 + DEX
        overseas = build_overseas_aggregator(config)
        if config.coingecko_enabled and config.coingecko_api_key and cg_http is not None:
            onchain_base = config.coingecko_base_url.rstrip("/") + "/onchain"
            dex_headers = ({"x-cg-pro-api-key": config.coingecko_api_key}
                           if "pro-api.coingecko.com" in onchain_base
                           else {"x-cg-demo-api-key": config.coingecko_api_key})
            dex = GeckoTerminalDEX(cg_http, base=onchain_base, headers=dex_headers)
        else:
            dex = GeckoTerminalDEX(HttpClient(
                timeout=config.http_timeout_sec, proxy=None,
                user_agent=config.request_user_agent, min_interval=4.0, max_retries=2))
        venue_provider = make_venue_provider(overseas, dex, cg_tokens)
        # 소셜 provider: LunarCrush(키 있을 때만). 미연결이면 social 비활성.
        social_provider = None
        if config.lunarcrush_enabled and config.lunarcrush_api_key:
            lc_http = HttpClient(
                timeout=config.http_timeout_sec, proxy=None,
                user_agent=config.request_user_agent, min_interval=1.0, max_retries=2,
            )
            social_provider = make_social_provider(LunarCrushClient(config, lc_http))
        PredictorService(
            config, storage, bus, build_extractors(config), historical=historical,
            market_provider=market_provider, social_provider=social_provider,
            venue_provider=venue_provider,
        )
        bus.subscribe(GradePredicted, notifier.on_grade)
        log.info("등급 예측: ON (과거 케이스 %d건, 시총=%s, 소셜=%s)",
                 len(historical.cases), "ON" if market_provider else "OFF",
                 "ON" if social_provider else "OFF")

    sources = []
    if config.upbit_enabled:
        sources.append(UpbitSource(config.upbit_announcements_url, http))
    if config.bithumb_enabled:
        sources.append(BithumbSource(config.bithumb_announcements_url, http))

    # 빗썸·바이낸스 선상장 여부(평가 기준) — 심볼로 각 거래소 확인
    bithumb_checker = (lambda sym: bithumb_pre_listed(http, sym))
    binance_checker = (lambda sym: binance_pre_listed(http, sym))
    return DetectorService(config, storage, bus, sources, resolver,
                           bithumb_checker=bithumb_checker,
                           binance_checker=binance_checker)


async def main_async() -> None:
    config = Config.load()
    setup_logging(config.log_level)
    service = build_service(config)
    await service.start()


def main() -> None:
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n중지됨")


if __name__ == "__main__":
    main()
