"""앱 조립 및 엔트리포인트."""
from __future__ import annotations

import asyncio
import logging

from .config import Config
from .core.bus import EventBus
from .core.events import GradePredicted, ListingDetected
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
        PredictorService(
            config, storage, bus, build_extractors(config), historical=historical
        )
        bus.subscribe(GradePredicted, notifier.on_grade)
        log.info("등급 예측: ON (과거 케이스 %d건)", len(historical.cases))

    sources = []
    if config.upbit_enabled:
        sources.append(UpbitSource(config.upbit_announcements_url, http))
    if config.bithumb_enabled:
        sources.append(BithumbSource(config.bithumb_announcements_url, http))

    # 빗썸 기상장 여부(평가 기준) — 어느 소스의 공지든 심볼로 빗썸 KRW 마켓 확인
    bithumb_checker = (lambda sym: bithumb_pre_listed(http, sym))
    return DetectorService(config, storage, bus, sources, resolver,
                           bithumb_checker=bithumb_checker)


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
