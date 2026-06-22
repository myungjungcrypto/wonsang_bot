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
    # True=KRW만 추가된 기존 업비트 코인(BTC/USDT 선상장), False=신규 전체상장, None=미상
    pre_listed: bool | None = None
    # True=상장 시점 이미 빗썸(KRW)에 있던 코인, False=빗썸 미상장, None=미상
    pre_listed_bithumb: bool | None = None
    # True=상장 시점 이미 바이낸스(USDT)에 있던 코인, False=미상장, None=미상
    pre_listed_binance: bool | None = None
    # 업비트 입금 지원 네트워크(공지 '네트워크' 칸 파싱) — 브릿지 목적지
    deposit_network: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# 등급(낮음→높음). 인덱스가 클수록 좋은 따리.
GRADES: tuple[str, ...] = ("큰실패", "실패", "약성공", "성공", "대성공")


@dataclass(slots=True)
class FeatureScore:
    """피처 1개의 점수(0..1, 높을수록 갭/성공에 유리)."""
    name: str
    score: float
    weight: float
    available: bool = True            # 데이터가 없으면 False → 가중합에서 제외(신뢰도↓)
    detail: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GradePredicted:
    """등급 예측 이벤트(추천 모드)."""
    source: str
    announcement_id: str
    symbols: list[str] = field(default_factory=list)
    grade: str = "약성공"
    score: float = 0.0                # 가용 피처 가중합(0..1)
    confidence: float = 0.0           # 가용 피처 비중(0..1)
    features: list[FeatureScore] = field(default_factory=list)
    neighbors: list[dict[str, Any]] = field(default_factory=list)  # 유사 과거 케이스
    secondary_grade: str | None = None   # 과거 케이스 기반 2차 등급
    # 구매처 추천(라이브 구매처 조회 시): 어디서 얼마에 살지
    buy_venue: str | None = None         # 매수처(cex명 또는 dex:chain)
    buy_price: float | None = None       # 최저가(USD)
    venue_count: int | None = None       # 구매 가능 거래소 수
    bridge: dict[str, Any] | None = None  # 브릿지 경로(매수체인≠입금체인 시) {tool,duration_sec,...}
    predicted_at: str = field(default_factory=now_iso)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

