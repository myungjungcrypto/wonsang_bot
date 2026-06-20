"""이벤트/도메인 데이터 구조 (표준 라이브러리만)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class Announcement:
    """거래소 공지 1건(정규화된 형태)."""
    source: str                      # "upbit" | "bithumb"
    id: str                          # 거래소가 주는 안정적 식별자
    title: str
    url: str | None = None
    category: str | None = None
    published_at: str | None = None  # 거래소가 준 게시 시각(원본 문자열)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.id}"


@dataclass(slots=True)
class Contract:
    """온체인 컨트랙트 주소."""
    chain: str
    address: str
    via: str = "unknown"             # 해결 출처: announcement_body | coingecko | llm


@dataclass(slots=True)
class ListingDetected:
    """원화상장(으로 추정되는) 감지 이벤트."""
    source: str
    announcement_id: str
    title: str
    symbols: list[str] = field(default_factory=list)
    markets: list[str] = field(default_factory=list)
    is_krw: bool = False
    contracts: list[Contract] = field(default_factory=list)
    url: str | None = None
    published_at: str | None = None
    detected_at: str = field(default_factory=now_iso)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
