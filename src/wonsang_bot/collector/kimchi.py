"""김프(따리) 수익률 계산 — 순수 함수.

모델: 공지 +5분 해외(USDT) 매수 → 업비트 상장 오픈 KRW 매도.
환율은 업비트 KRW-USDT(김프 포함 실효환율)를 사용 → 따리 트레이더 실제 체감과 일치.

    upbit_usdt_price = krw_sell / usdt_krw      # 업비트 상장가를 USDT로 환산
    return%          = (upbit_usdt_price / usd_buy - 1) * 100
"""
from __future__ import annotations

from typing import Optional


def kimchi_return_pct(
    usd_buy: Optional[float],
    krw_sell: Optional[float],
    usdt_krw: Optional[float],
) -> Optional[float]:
    """해외 매수(USDT) 대비 업비트 상장가(KRW→USDT 환산) 수익률(%)."""
    if not usd_buy or not krw_sell or not usdt_krw:
        return None
    if usd_buy <= 0 or usdt_krw <= 0:
        return None
    upbit_usdt = krw_sell / usdt_krw
    return round((upbit_usdt / usd_buy - 1.0) * 100.0, 2)
