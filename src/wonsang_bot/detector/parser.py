"""공지 제목 파싱 — 상장 여부/심볼/마켓 추출 (휴리스틱).

⚠️ 거래소 공지 제목 포맷은 수시로 바뀐다. 여기 규칙은 합리적 기본값이며
라이브 데이터로 반드시 재검증/보강해야 한다(모호하면 LLM 보조 파싱으로 폴백).

예시 제목:
- 업비트: "디지털 자산 추가 (메타플래닛(MTP)) (KRW, BTC 마켓)"
- 업비트: "[거래] 무빙(MOVE) KRW, USDT 마켓 디지털 자산 추가"
- 빗썸:   "원화(KRW) 마켓 추가 (이름(SYM))"
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# 시세 기준통화(신규 상장 심볼이 될 수 없음) → 심볼 후보에서 제외
QUOTE_CCY = {"KRW", "BTC", "USDT", "USDC"}

# 상장으로 볼 수 있는 키워드
LISTING_KW = (
    "디지털 자산", "거래지원", "거래 지원", "신규", "마켓 추가",
    "원화 마켓", "상장", "마켓 디지털", "마켓 추가 안내",
)

# 상장이 아님(제외) 키워드
NEG_KW = (
    "종료", "폐지", "유의", "점검", "중단", "연기", "지연",
    "이벤트", "에어드랍", "에어드롭", "스냅샷", "리브랜딩", "변경 안내",
)

_PAREN = re.compile(r"\(([^()]*)\)")            # 가장 안쪽 괄호 내용
_TOKEN = re.compile(r"[A-Z0-9]{2,15}")          # 티커 후보
_WORD = re.compile(r"\b(KRW|BTC|USDT|USDC)\b")  # 마켓 기준통화


@dataclass(slots=True)
class ListingParse:
    is_listing: bool
    symbols: list[str] = field(default_factory=list)
    markets: list[str] = field(default_factory=list)
    is_krw: bool = False
    confidence: float = 0.0
    reason: str = ""


def _looks_like_ticker(tok: str) -> bool:
    return any(c.isalpha() for c in tok) and tok not in QUOTE_CCY


def extract_symbols(title: str) -> list[str]:
    """괄호 안에서 티커처럼 보이는 토큰을 추출(순서 유지, 중복 제거)."""
    out: list[str] = []
    for group in _PAREN.findall(title):
        for tok in _TOKEN.findall(group):
            if _looks_like_ticker(tok) and tok not in out:
                out.append(tok)
    return out


def extract_markets(title: str) -> tuple[list[str], bool]:
    """마켓 기준통화 목록과 원화마켓 여부."""
    markets: list[str] = []
    for q in _WORD.findall(title):
        if q not in markets:
            markets.append(q)
    is_krw = ("KRW" in markets) or ("원화" in title)
    if is_krw and "KRW" not in markets:
        markets.insert(0, "KRW")
    return markets, is_krw


def classify(title: str) -> tuple[bool, str]:
    """상장 공지 여부 + 사유."""
    neg = [k for k in NEG_KW if k in title]
    if neg:
        return False, f"제외 키워드: {','.join(neg)}"
    pos = [k for k in LISTING_KW if k in title]
    if pos:
        return True, f"상장 키워드: {','.join(pos)}"
    return False, "상장 키워드 없음"


def parse_title(title: str) -> ListingParse:
    title = (title or "").strip()
    is_listing, reason = classify(title)
    symbols = extract_symbols(title)
    markets, is_krw = extract_markets(title)

    confidence = 0.0
    if is_listing:
        confidence += 0.5
    if symbols:
        confidence += 0.3
    if is_krw:
        confidence += 0.2
    confidence = min(confidence, 1.0)

    return ListingParse(
        is_listing=is_listing,
        symbols=symbols,
        markets=markets,
        is_krw=is_krw,
        confidence=round(confidence, 3),
        reason=reason,
    )
