"""텔레그램 알림 (제어판 겸 알림 채널의 시작점).

dry_run=True거나 토큰이 없으면 실제 전송 대신 로그만 남긴다.
"""
from __future__ import annotations

import asyncio
import logging

from ..core.events import GradePredicted, ListingDetected
from ..httpclient import HttpClient

log = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(
        self,
        token: str | None,
        chat_id: str | None,
        http: HttpClient,
        dry_run: bool = True,
    ) -> None:
        self.token = token
        self.chat_id = chat_id
        self.http = http
        self.dry_run = dry_run or not token or not chat_id

    @staticmethod
    def format_listing(ev: ListingDetected) -> str:
        syms = ", ".join(ev.symbols) if ev.symbols else "(심볼 미확인)"
        markets = ", ".join(ev.markets) if ev.markets else "-"
        lines = [
            "🚨 *원화상장 감지*" if ev.is_krw else "📢 *상장 공지 감지*",
            f"거래소: {ev.source.upper()}",
            f"심볼: {syms}",
            f"마켓: {markets}",
            f"신뢰도: {ev.confidence}",
            f"제목: {ev.title}",
        ]
        if ev.contracts:
            for c in ev.contracts[:6]:
                lines.append(f"  • {c.chain}: `{c.address}`")
        if ev.url:
            lines.append(ev.url)
        return "\n".join(lines)

    _GRADE_EMOJI = {
        "대성공": "🟢🟢", "성공": "🟢", "약성공": "🟡", "실패": "🔴", "큰실패": "🔴🔴",
    }

    @classmethod
    def format_grade(cls, ev: GradePredicted) -> str:
        syms = ", ".join(ev.symbols) if ev.symbols else "(심볼 미확인)"
        emoji = cls._GRADE_EMOJI.get(ev.grade, "")
        lines = [
            f"{emoji} *등급 예측: {ev.grade}*",
            f"심볼: {syms} ({ev.source.upper()})",
            f"점수: {ev.score:.2f} / 신뢰도: {ev.confidence:.0%}",
        ]
        if ev.secondary_grade:
            lines.append(f"과거 케이스 2차등급: {ev.secondary_grade}")
        lines.append("─ 근거 ─")
        for f in ev.features:
            mark = "" if f.available else " (데이터없음)"
            lines.append(f"  • {f.name}: {f.score:.2f}{mark} — {f.detail}")
        if ev.neighbors:
            sims = ", ".join(f"{n['symbol']}({n['grade']})" for n in ev.neighbors[:3])
            lines.append(f"유사 케이스: {sims}")
        return "\n".join(lines)

    async def on_listing(self, ev: ListingDetected) -> None:
        text = self.format_listing(ev)
        if self.dry_run:
            log.info("[TELEGRAM dry-run]\n%s", text)
            return
        await asyncio.to_thread(self._send, text)

    async def on_grade(self, ev: GradePredicted) -> None:
        text = self.format_grade(ev)
        if self.dry_run:
            log.info("[TELEGRAM dry-run]\n%s", text)
            return
        await asyncio.to_thread(self._send, text)

    def _send(self, text: str) -> None:
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        try:
            self.http.post_json(url, payload)
        except Exception:  # noqa: BLE001
            log.exception("텔레그램 전송 실패")
