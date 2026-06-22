#!/usr/bin/env python3
"""라이브 파이프라인 스모크 테스트 — 가짜 상장 신호 주입(실제 상장 대기 없이).

실제 라이브 배선(app.build_service)에 합성 ListingDetected 를 발행 → 구독 중인
예측기/알림이 그대로 동작: 진짜 CoinGecko/CEX/DEX/LunarCrush 를 조회해 구매처·등급·
근거를 산출하고, 텔레그램(dry_run 이면 로그)으로 알림까지 흘려본다.
감지부(공지 폴링/프록시/파싱)는 타지 않음 — 그건 실제 상장으로 검증.

사용:
    python scripts/smoke_signal.py IRYS ethereum:0x<주소>
    python scripts/smoke_signal.py WIF                      # 컨트랙트 없이(심볼만)도 가능
    python scripts/smoke_signal.py IRYS ethereum:0x<주소> net=ethereum  # 브릿지 테스트
      → 최저가 매수처가 net(입금체인)과 다른 체인이면 🌉 브릿지 경로가 뜸
환경:
    TELEGRAM_DRY_RUN=true 면 전송 대신 로그(안전). false + 토큰/챗ID 면 실제 전송.
    COINGECKO_ENABLED=true(+키) 로 venue_count/시총 활성, LIFI_ENABLED=true 로 브릿지.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from wonsang_bot.app import build_service  # noqa: E402
from wonsang_bot.config import Config  # noqa: E402
from wonsang_bot.core.events import Contract, ListingDetected  # noqa: E402
from wonsang_bot.logging_conf import setup_logging  # noqa: E402


async def main() -> None:
    contracts = []
    deposit_network = None
    positional = []
    for a in sys.argv[1:]:
        if a.startswith("net="):
            deposit_network = a.split("=", 1)[1] or None
        elif ":" in a:
            ch, _, ad = a.partition(":")
            contracts.append(Contract(chain=ch, address=ad))
        else:
            positional.append(a)
    symbol = positional[0] if positional else "IRYS"

    config = Config.load()
    setup_logging(config.log_level)
    svc = build_service(config)  # 실제 배선(예측기+알림 구독). 폴링은 시작 안 함.

    # 빗썸/바이낸스 선상장은 라이브와 동일 체커로 실제 조회(있으면)
    pre_b = svc.bithumb_checker(symbol) if svc.bithumb_checker else None
    pre_n = svc.binance_checker(symbol) if svc.binance_checker else None

    ev = ListingDetected(
        source="upbit", announcement_id="SMOKE-TEST",
        title=f"{symbol} 신규 거래지원 안내 (KRW) [스모크테스트]",
        symbols=[symbol], markets=["KRW"], is_krw=True, contracts=contracts,
        confidence=0.99, pre_listed=False,
        pre_listed_bithumb=pre_b, pre_listed_binance=pre_n,
        deposit_network=deposit_network,
    )
    print(f"▶ 합성 신호 발행: {symbol} (contracts={len(contracts)}, "
          f"입금네트워크={deposit_network or '-'}, "
          f"빗썸선상장={pre_b}, 바이낸스선상장={pre_n})")
    dry = config.telegram_dry_run or not config.telegram_token or not config.telegram_chat_id
    print(f"  텔레그램: {'dry-run(로그만)' if dry else '실제 전송'} — 알림은 아래로\n")
    await svc.bus.publish(ev)  # → 감지 알림 + 등급 예측(구매처 조회) + 등급 알림


if __name__ == "__main__":
    asyncio.run(main())
