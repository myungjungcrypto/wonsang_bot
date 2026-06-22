"""공지 본문 텍스트에서 컨트랙트 주소 + 체인을 추출 (순수 함수, 네트워크 없음).

기능 1의 핵심: "contract address를 확인해서 상장 코인을 특정".
공지 본문에는 보통 네트워크명 + 컨트랙트 주소가 들어있다. 이를 뽑아낸다.

지원:
- EVM (0x...): 주변 네트워크 힌트로 체인 결정(없으면 'evm')
- Tron  (T...): 패턴이 강해 단독 식별
- Solana (base58): 솔라나 힌트가 있을 때만(오탐 방지)
"""
from __future__ import annotations

import re

from ..core.events import Contract

# 체인 정규화: canonical -> 본문에 등장할 수 있는 표기들(소문자 비교)
CHAIN_HINTS: dict[str, tuple[str, ...]] = {
    "ethereum": ("이더리움", "ethereum", "erc-20", "erc20", "eth 네트워크", "eth mainnet"),
    "bsc": ("바이낸스 스마트", "bnb smart", "bnb chain", "bnb 체인", "bsc", "bep-20", "bep20"),
    "base": ("base 네트워크", "base mainnet", "베이스 네트워크", " base ", "(base)"),
    "arbitrum": ("아비트럼", "arbitrum", "arb 네트워크"),
    "polygon": ("폴리곤", "polygon", "matic"),
    "optimism": ("옵티미즘", "optimism", " op 네트워크"),
    "avalanche": ("아발란체", "avalanche", "avax"),
    "linea": ("linea", "리네아"),
    "solana": ("솔라나", "solana", "spl 토큰", "spl token"),
    "tron": ("트론", "tron", "trc-20", "trc20"),
}

# EVM 계열(주소가 0x...인 체인)
EVM_FAMILY = {
    "ethereum", "bsc", "base", "arbitrum", "polygon", "optimism",
    "avalanche", "linea",
}

EVM_RE = re.compile(r"0x[a-fA-F0-9]{40}")
TRON_RE = re.compile(r"\bT[1-9A-HJ-NP-Za-km-z]{33}\b")
SOL_RE = re.compile(r"[1-9A-HJ-NP-Za-km-z]{32,44}")


def normalize_chain(name: str | None) -> str | None:
    """다양한 표기를 canonical 체인 id로."""
    if not name:
        return None
    low = name.strip().lower()
    for canon, hints in CHAIN_HINTS.items():
        if low == canon or any(h.strip() and h.strip() in low for h in hints):
            return canon
    return None


def _find_hints(text_low: str) -> list[tuple[int, str]]:
    """본문에서 (위치, 체인) 힌트 목록."""
    hints: list[tuple[int, str]] = []
    for canon, needles in CHAIN_HINTS.items():
        for n in needles:
            n = n.strip()
            if not n:
                continue
            start = 0
            while True:
                idx = text_low.find(n, start)
                if idx == -1:
                    break
                hints.append((idx, canon))
                start = idx + len(n)
    return hints


def _nearest_chain(
    pos: int, hints: list[tuple[int, str]], allowed: set[str], default: str
) -> str:
    best: str | None = None
    best_dist = 10**9
    for idx, canon in hints:
        if canon not in allowed:
            continue
        dist = abs(idx - pos)
        if dist < best_dist:
            best_dist, best = dist, canon
    return best or default


def parse_deposit_network(text: str | None) -> str | None:
    """공지 본문의 '네트워크' 칸 → 업비트 입금 지원 체인(브릿지 목적지).

    업비트 신규상장 공지엔 표로 '디지털자산|마켓|네트워크|...'가 있고 네트워크 칸에
    Ethereum/Solana/BNB Smart Chain 등이 적힘. '네트워크' 라벨 뒤 가장 가까운 체인
    힌트를 채택(없으면 본문 첫 힌트). 라이브에서 표기 재검증 필요.
    """
    if not text:
        return None
    low = text.lower()
    hints = sorted(_find_hints(low), key=lambda t: t[0])
    if not hints:
        return None
    label = low.find("네트워크")
    if label != -1:
        after = [c for idx, c in hints if idx >= label]
        if after:
            return after[0]
    return hints[0][1]


def extract_contracts_from_text(text: str | None) -> list[Contract]:
    if not text:
        return []
    low = text.lower()
    hints = _find_hints(low)
    has_solana = any(c == "solana" for _, c in hints)

    out: list[Contract] = []
    seen: set[tuple[str, str]] = set()

    def add(chain: str, addr: str) -> None:
        key = (chain, addr.lower())
        if key not in seen:
            seen.add(key)
            out.append(Contract(chain=chain, address=addr, via="announcement_body"))

    # EVM
    for m in EVM_RE.finditer(text):
        chain = _nearest_chain(m.start(), hints, EVM_FAMILY, default="evm")
        add(chain, m.group(0))

    # Tron
    for m in TRON_RE.finditer(text):
        add("tron", m.group(0))

    # Solana (힌트 있을 때만)
    if has_solana:
        for m in SOL_RE.finditer(text):
            # 0x 직후(=EVM 16진 일부)나 Tron 주소는 제외
            if text[max(0, m.start() - 2):m.start()] == "0x":
                continue
            if TRON_RE.fullmatch(m.group(0)):
                continue
            add("solana", m.group(0))

    return out
