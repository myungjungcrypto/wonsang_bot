"""등급 예측 서비스 — ListingDetected 구독 → 피처 추출 → 스코어링 → GradePredicted 발행.

predict()는 순수(주입된 추출기에만 의존)하므로 오프라인 테스트 가능.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from ..config import Config
from ..core.bus import EventBus
from ..core.events import GradePredicted, ListingDetected
from ..storage.db import Storage
from . import scoring
from .features.base import FeatureContext, FeatureExtractor, Provider
from .historical import HistoricalStore

log = logging.getLogger(__name__)


class PredictorService:
    def __init__(
        self,
        config: Config,
        storage: Storage,
        bus: EventBus,
        extractors: list[FeatureExtractor],
        historical: Optional[HistoricalStore] = None,
        market_provider: Optional[Provider] = None,
        social_provider: Optional[Provider] = None,
    ) -> None:
        self.config = config
        self.storage = storage
        self.bus = bus
        self.extractors = extractors
        self.historical = historical
        self.market_provider = market_provider
        self.social_provider = social_provider
        bus.subscribe(ListingDetected, self.on_listing)

    async def on_listing(self, ev: ListingDetected) -> None:
        pred = self.predict(ev)
        try:
            self.storage.save_prediction(pred)
        except Exception:  # noqa: BLE001
            log.exception("예측 저장 실패")
        await self.bus.publish(pred)

    def predict(self, ev: ListingDetected, now: datetime | None = None) -> GradePredicted:
        ctx = FeatureContext(
            listing=ev,
            config=self.config,
            now=now,
            market_provider=self.market_provider,
            social_provider=self.social_provider,
        )
        features = [ex.extract(ctx) for ex in self.extractors]
        score, confidence = scoring.combine(features)
        grade = scoring.to_grade(score, self.config.grade_thresholds)

        neighbors_out: list[dict] = []
        secondary: str | None = None
        if self.historical is not None:
            fvec = {f.name: f.score for f in features if f.available}
            nb = self.historical.nearest(fvec, k=self.config.historical_k)
            secondary = self.historical.suggest_grade(nb)
            neighbors_out = [
                {"id": c.id, "symbol": c.symbol, "grade": c.grade, "distance": round(d, 4)}
                for c, d in nb
            ]

        pred = GradePredicted(
            source=ev.source,
            announcement_id=ev.announcement_id,
            symbols=ev.symbols,
            grade=grade,
            score=score,
            confidence=confidence,
            features=features,
            neighbors=neighbors_out,
            secondary_grade=secondary,
        )
        log.info(
            "등급 예측: %s %s → %s (score=%.3f conf=%.2f, 2차=%s)",
            ev.source.upper(), ev.symbols, grade, score, confidence, secondary,
        )
        return pred
