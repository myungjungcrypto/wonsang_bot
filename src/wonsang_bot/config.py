"""설정 로더 (표준 라이브러리만 사용).

`.env` 파일과 환경변수에서 설정을 읽는다. 시크릿(키)은 절대 커밋하지 않는다.
무거운 의존성(pydantic 등) 없이 오프라인에서도 동작하도록 의도적으로 가볍게 작성.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def load_dotenv(path: str = ".env") -> None:
    """`.env`를 읽어 os.environ 에 채운다(기존 값은 덮어쓰지 않음)."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key.strip(), val)


def _get(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


def _get_float(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def _get_bool(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "y"}


@dataclass(slots=True)
class Config:
    # --- 감지 ---
    poll_interval_sec: float = 2.0          # 공지 폴링 주기(초). 라이브에선 더 짧게.
    upbit_enabled: bool = True
    bithumb_enabled: bool = True
    upbit_announcements_url: str = (
        "https://api-manager.upbit.com/api/v1/announcements"
        "?os=web&page=1&per_page=20&category=trade"
    )
    # 빗썸 공지 엔드포인트는 라이브에서 재검증 필요(아래 어댑터 주석 참고).
    bithumb_announcements_url: str = (
        "https://api.bithumb.com/v1/notices?count=20"
    )
    http_proxy: str | None = None           # 차단 대비 프록시(예: http://host:port)
    http_timeout_sec: float = 8.0
    request_user_agent: str = "Mozilla/5.0 (wonsang_bot)"
    fetch_announcement_body: bool = True    # 상장 감지 시 본문 받아 컨트랙트 추출

    # --- 알림(텔레그램) ---
    telegram_token: str | None = None
    telegram_chat_id: str | None = None
    telegram_dry_run: bool = True           # True면 실제 전송 대신 로그만

    # --- LLM (교체/비활성 가능) ---
    llm_enabled: bool = False
    llm_provider: str = "claude"
    llm_model: str = "claude-haiku-4-5-20251001"  # 비용 고려 기본값
    llm_api_key: str | None = None

    # --- 컨트랙트 매핑(선택형) ---
    coingecko_enabled: bool = False
    coingecko_api_key: str | None = None
    coingecko_base_url: str = "https://api.coingecko.com/api/v3"

    # --- 저장/로깅 ---
    db_path: str = "data/wonsang.sqlite"
    log_level: str = "INFO"

    # --- 동작 모드 ---
    seed_only_first_run: bool = True        # 첫 실행 시 기존 공지는 알림 없이 seen 처리

    @classmethod
    def load(cls, dotenv_path: str = ".env") -> "Config":
        load_dotenv(dotenv_path)
        return cls(
            poll_interval_sec=_get_float("POLL_INTERVAL_SEC", 2.0),
            upbit_enabled=_get_bool("UPBIT_ENABLED", True),
            bithumb_enabled=_get_bool("BITHUMB_ENABLED", True),
            upbit_announcements_url=_get("UPBIT_ANNOUNCEMENTS_URL", cls.upbit_announcements_url),  # type: ignore[arg-type]
            bithumb_announcements_url=_get("BITHUMB_ANNOUNCEMENTS_URL", cls.bithumb_announcements_url),  # type: ignore[arg-type]
            http_proxy=_get("HTTP_PROXY_URL"),
            http_timeout_sec=_get_float("HTTP_TIMEOUT_SEC", 8.0),
            fetch_announcement_body=_get_bool("FETCH_ANNOUNCEMENT_BODY", True),
            telegram_token=_get("TELEGRAM_TOKEN"),
            telegram_chat_id=_get("TELEGRAM_CHAT_ID"),
            telegram_dry_run=_get_bool("TELEGRAM_DRY_RUN", True),
            llm_enabled=_get_bool("LLM_ENABLED", False),
            llm_provider=_get("LLM_PROVIDER", "claude"),  # type: ignore[arg-type]
            llm_model=_get("LLM_MODEL", "claude-haiku-4-5-20251001"),  # type: ignore[arg-type]
            llm_api_key=_get("ANTHROPIC_API_KEY") or _get("LLM_API_KEY"),
            coingecko_enabled=_get_bool("COINGECKO_ENABLED", False),
            coingecko_api_key=_get("COINGECKO_API_KEY"),
            coingecko_base_url=_get("COINGECKO_BASE_URL", cls.coingecko_base_url),  # type: ignore[arg-type]
            db_path=_get("DB_PATH", "data/wonsang.sqlite"),  # type: ignore[arg-type]
            log_level=_get("LOG_LEVEL", "INFO"),  # type: ignore[arg-type]
            seed_only_first_run=_get_bool("SEED_ONLY_FIRST_RUN", True),
        )
