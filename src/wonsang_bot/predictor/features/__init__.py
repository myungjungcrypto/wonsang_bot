"""피처 추출기."""
from __future__ import annotations

from ...config import Config
from .base import FeatureContext, FeatureExtractor, Provider
from .listing_type import ListingTypeFeature
from .marketcap import MarketCapFeature
from .narrative import NarrativeFeature
from .social import SocialFeature
from .supply import SupplyChokeFeature
from .timing import TimingFeature


def build_extractors(config: Config) -> list[FeatureExtractor]:
    """config 가중치로 기본 피처 추출기 세트를 구성."""
    return [
        TimingFeature(config.w_timing),
        NarrativeFeature(config.w_narrative),
        SupplyChokeFeature(config.w_supply),
        ListingTypeFeature(config.w_listing_type),
        MarketCapFeature(config.w_marketcap),
        SocialFeature(config.w_social),
    ]


__all__ = [
    "FeatureContext",
    "FeatureExtractor",
    "Provider",
    "TimingFeature",
    "NarrativeFeature",
    "SupplyChokeFeature",
    "ListingTypeFeature",
    "MarketCapFeature",
    "SocialFeature",
    "build_extractors",
]
