#!/usr/bin/env python3
"""감지 서비스 실행 진입점.

사용:
    python scripts/run_detector.py
(설정은 .env 또는 환경변수에서 로드. .env.example 참고)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from wonsang_bot.app import main  # noqa: E402

if __name__ == "__main__":
    main()
