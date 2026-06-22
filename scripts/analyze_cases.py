#!/usr/bin/env python3
"""수집 케이스 통계 출력 — 상장유형/거래소가용성별 실패율·승률.

사용: python scripts/analyze_cases.py [cases.json] [최근N]
  예) python scripts/analyze_cases.py data/cases_kimchi.json 50   # 최근 50건만
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from wonsang_bot.collector.analysis import summarize  # noqa: E402
from wonsang_bot.core.events import GRADES  # noqa: E402


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "data/cases_kimchi.json"
    n_recent = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    cases = data["cases"] if isinstance(data, dict) else data

    # 상장 최신순 정렬 후 최근 N건만(선택)
    cases = sorted(cases, key=lambda c: c.get("listed_at", ""), reverse=True)
    if n_recent > 0:
        cases = cases[:n_recent]
    if cases:
        print(f"분석 대상 {len(cases)}건  "
              f"기간 {cases[-1].get('listed_at', '')[:10]} ~ {cases[0].get('listed_at', '')[:10]}")
    top = sorted(cases, key=lambda c: c.get("realized_return_pct") or 0, reverse=True)[:5]
    print("상위 수익률(이상치 점검):",
          [(c.get("symbol"), round(c.get("realized_return_pct") or 0)) for c in top])

    s = summarize(cases)

    print(f"\n=== 전체 ({s['overall'].get('n', 0)}건) ===")
    print(f"  중앙값 {s['overall'].get('median_ret')}%  (평균 {s['overall'].get('avg_ret')}%, "
          f"최대 {s['overall'].get('max_ret')}%)  "
          f"승률(≥0%) {s['overall'].get('win_rate')}  실패율(<0%) {s['overall'].get('fail_rate')}")
    g = s["grades"]
    ordered = "  ".join(f"{name} {g.get(name, 0)}" for name in reversed(GRADES))
    print(f"  등급분포(높은순): {ordered}")

    print("\n=== 상장 유형별 (중앙값 기준 — 평균은 대박에 휘둘림) ===")
    for k, v in s["by_listing_type"].items():
        if v.get("n"):
            print(f"  {k:18s} n={v['n']:3d}  중앙값 {v['median_ret']:+6.1f}%  "
                  f"실패율 {v['fail_rate']:.0%}  승률 {v['win_rate']:.0%}  "
                  f"(평균 {v['avg_ret']:+.0f}%)")

    print("\n=== 거래소 가용성별 ===")
    for k, v in s["by_venue_count"].items():
        if v.get("n"):
            print(f"  {k:8s} n={v['n']:3d}  중앙값 {v['median_ret']:+6.1f}%  "
                  f"실패율 {v['fail_rate']:.0%}  승률 {v['win_rate']:.0%}  "
                  f"(평균 {v['avg_ret']:+.0f}%)")
    print()


if __name__ == "__main__":
    main()
