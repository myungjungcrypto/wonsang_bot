#!/usr/bin/env python3
"""수집 케이스 통계 출력 — 상장유형/거래소가용성별 실패율·승률.

사용: python scripts/analyze_cases.py [cases.json]   (기본 data/cases_kimchi.json)
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from wonsang_bot.collector.analysis import summarize  # noqa: E402


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "data/cases_kimchi.json"
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    cases = data["cases"] if isinstance(data, dict) else data
    s = summarize(cases)

    print(f"\n=== 전체 ({s['overall'].get('n', 0)}건) ===")
    print(f"  평균수익률 {s['overall'].get('avg_ret')}%  "
          f"승률(≥10%) {s['overall'].get('win_rate')}  "
          f"실패율(<0%) {s['overall'].get('fail_rate')}")
    print(f"  등급분포: {s['grades']}")

    print("\n=== 상장 유형별 ===")
    for k, v in s["by_listing_type"].items():
        if v.get("n"):
            print(f"  {k:18s} n={v['n']:3d}  실패율 {v['fail_rate']:.0%}  "
                  f"승률 {v['win_rate']:.0%}  평균 {v['avg_ret']:+.1f}%")

    print("\n=== 거래소 가용성별 ===")
    for k, v in s["by_venue_count"].items():
        if v.get("n"):
            print(f"  {k:8s} n={v['n']:3d}  실패율 {v['fail_rate']:.0%}  "
                  f"승률 {v['win_rate']:.0%}  평균 {v['avg_ret']:+.1f}%")
    print()


if __name__ == "__main__":
    main()
