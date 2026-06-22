"""텔레그램 알림 (제어판 겸 알림 채널의 시작점).

dry_run=True거나 토큰이 없으면 실제 전송 대신 로그만 남긴다.
포맷은 **HTML 모드**(공지 제목·심볼 등에 _ * [ 같은 문자가 있어도 안전).
동적 값은 모두 _esc()로 < > & 이스케이프 → 파싱 400(알림 유실) 방지.
"""
from __future__ import annotations

import asyncio
import html
import logging

from ..core.events import GradePredicted, ListingDetected
from ..httpclient import HttpClient

log = logging.getLogger(__name__)


def _esc(value: object) -> str:
    """텔레그램 HTML 텍스트 이스케이프(< > & 만)."""
    return html.escape(str(value), quote=False)


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
            "🚨 <b>원화상장 감지</b>" if ev.is_krw else "📢 <b>상장 공지 감지</b>",
            f"거래소: {_esc(ev.source.upper())}",
            f"심볼: {_esc(syms)}",
            f"마켓: {_esc(markets)}",
            f"신뢰도: {_esc(ev.confidence)}",
            f"제목: {_esc(ev.title)}",
        ]
        if ev.contracts:
            for c in ev.contracts[:6]:
                lines.append(f"  • {_esc(c.chain)}: <code>{_esc(c.address)}</code>")
        if ev.url:
            lines.append(_esc(ev.url))
        return "\n".join(lines)

    _GRADE_EMOJI = {
        "대성공": "🟢🟢", "성공": "🟢", "약성공": "🟡", "실패": "🔴", "큰실패": "🔴🔴",
    }

    @classmethod
    def format_grade(cls, ev: GradePredicted) -> str:
        syms = ", ".join(ev.symbols) if ev.symbols else "(심볼 미확인)"
        emoji = cls._GRADE_EMOJI.get(ev.grade, "")
        lines = [
            f"{emoji} <b>등급 예측: {_esc(ev.grade)}</b>",
            f"심볼: {_esc(syms)} ({_esc(ev.source.upper())})",
            f"점수: {ev.score:.2f} / 신뢰도: {ev.confidence:.0%}",
        ]
        if ev.secondary_grade:
            lines.append(f"과거 케이스 2차등급: {_esc(ev.secondary_grade)}")
        if ev.buy_venue and ev.buy_price is not None:
            vc = f", {ev.venue_count}곳" if ev.venue_count else ""
            lines.append(f"💰 매수처: {_esc(ev.buy_venue)} ${ev.buy_price:,.6g}{vc}")
        lines.append("─ 근거 ─")
        for f in ev.features:
            mark = "" if f.available else " (데이터없음)"
            lines.append(f"  • {_esc(f.name)}: {f.score:.2f}{mark} — {_esc(f.detail)}")
        if ev.neighbors:
            sims = ", ".join(f"{_esc(n['symbol'])}({_esc(n['grade'])})"
                             for n in ev.neighbors[:3])
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
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            self.http.post_json(url, payload)
        except Exception:  # noqa: BLE001
            log.exception("텔레그램 전송 실패")

