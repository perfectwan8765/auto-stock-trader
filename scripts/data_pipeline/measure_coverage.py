"""분기별 이벤트 커버리지 전수 + Toss 폐지기록 교차검증 — 계획서 §5 단계 1(b)(c)(f).

kill(1)("최근 구간조차 커버리지 80% 미달 → 종료")은 전수로 판정해야 한다. 티커 기준과 이벤트
가중 기준을 모두 낸다 — 둘이 다르면 결측이 이벤트 수와 상관됐다는 뜻이고 그 자체가 정보다.

실행:  .venv/bin/python scripts/data_pipeline/measure_coverage.py
"""
from __future__ import annotations

import sys

from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CANDIDATE_CLOSES_CSV, EVENTS_CSV, TOSS_META_CSV  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
EVENTS = EVENTS_CSV
CLOSES = CANDIDATE_CLOSES_CSV
TOSS_META = TOSS_META_CSV


def main() -> None:
    ev = pd.read_csv(EVENTS, parse_dates=["filing_date"]).dropna(subset=["symbol"])
    closes = pd.read_csv(CLOSES, index_col=0, parse_dates=True)
    covered = {c for c in closes.columns if closes[c].notna().sum() > 20}

    ev["quarter"] = ev.filing_date.dt.to_period("Q")
    ev["covered"] = ev.symbol.isin(covered)

    print(f"이벤트 {len(ev):,} · 고유 티커 {ev.symbol.nunique():,} · 가격 확보 티커 {len(covered):,}")
    print("\n=== 분기별 커버리지 (전수) ===")
    print("  {:<9}{:>9}{:>8}{:>11}{:>13}".format("분기", "이벤트", "티커", "티커커버", "이벤트커버"))
    for q, g in ev.groupby("quarter"):
        syms = g.symbol.unique()
        tick_cov = sum(s in covered for s in syms) / len(syms)
        print(f"  {str(q):<9}{len(g):>9,}{len(syms):>8,}{tick_cov:>10.1%}{g.covered.mean():>12.1%}")

    print(f"\n★ kill(1) 입력 — 주 표본 전체 이벤트 커버리지: {ev.covered.mean():.1%} "
          f"(임계 80% 대비 {'통과' if ev.covered.mean() >= 0.80 else '미달'})")

    _crosscheck_toss(ev, covered)


def _crosscheck_toss(ev: pd.DataFrame, covered: set[str]) -> None:
    """단계 1(f) — 가격 결측이 Toss 폐지 기록과 겹치는지. yfinance와 독립 소스다."""
    if not TOSS_META.exists():
        print("\n(Toss 메타 없음 — 교차검증 생략)")
        return
    meta = pd.read_csv(TOSS_META).drop_duplicates("symbol").set_index("symbol")
    missing = sorted(set(ev.symbol.unique()) - covered)
    known = [s for s in missing if s in meta.index]
    if not known:
        print("\n(결측 티커가 Toss 메타에 없음 — 교차검증 불가)")
        return
    sub = meta.loc[known]
    delisted = (sub.status == "DELISTED").sum()
    with_date = sub.delistDate.notna().sum()
    print(f"\n=== Toss 폐지기록 교차검증 (가격 결측 티커 {len(missing)}, 그중 Toss 메타 보유 {len(known)}) ===")
    print(f"  status=DELISTED {delisted} ({delisted/len(known):.1%}) · delistDate 있음 {with_date}")
    active = meta.loc[[s for s in ev.symbol.unique() if s in meta.index and s in covered]]
    if len(active):
        print(f"  (대조) 가격 확보 티커 {len(active)} 중 DELISTED "
              f"{(active.status == 'DELISTED').sum()} ({(active.status == 'DELISTED').mean():.1%})")


if __name__ == "__main__":
    main()
