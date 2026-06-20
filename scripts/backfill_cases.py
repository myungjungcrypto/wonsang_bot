#!/usr/bin/env python3
"""과거 케이스 백필 실행.

사용:
    python scripts/backfill_cases.py [입력.json]
    (기본 입력: data/cases_seed.example.json)

입력 JSON의 각 케이스를 라이브와 동일한 피처 추출기로 재구성하고, 실현 수익률을
등급으로 라벨링하여 DB(cases)에 저장한다. 저장된 케이스는 다음 실행부터 등급
예측의 2차 검증(최근접 이웃)에 사용된다.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from wonsang_bot.config import Config  # noqa: E402
from wonsang_bot.logging_conf import setup_logging  # noqa: E402
from wonsang_bot.predictor.backfill import backfill, load_raw_cases  # noqa: E402
from wonsang_bot.predictor.features import build_extractors  # noqa: E402
from wonsang_bot.storage.db import Storage  # noqa: E402


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "data/cases_seed.example.json"
    config = Config.load()
    setup_logging(config.log_level)

    raws = load_raw_cases(path)
    storage = Storage(config.db_path)
    try:
        n = backfill(raws, build_extractors(config), storage, config=config)
    finally:
        total = len(storage.load_cases())
        storage.close()
    print(f"백필 완료: {n}건 처리, cases 총 {total}건 (db={config.db_path})")


if __name__ == "__main__":
    main()
