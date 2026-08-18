"""매크로 ETF 횡단면 모멘텀(상대강도) — 1층 판정.

측정 정의는 사전등록 `docs/project/etp-prereg.md` §0(공통)·§2(연구 B)에 박혀 있다.
252거래일 총수익으로 자산 간 순위 → **상위 절반 k=⌈N/2⌉ 등가중** · 항상 100% 투자 ·
SHY는 랭킹 제외 · 절대 필터 없음. 나머지(리밸·비용·편입·데이터)는 절대 모멘텀에서 상속한다.

⚠️ 집행·비용·드리프트는 `run_trend.run()`의 `target_fn` 이음매로 **공유한다.** 따로 구현하면
초과수익이 구현 차이를 재게 된다.

실행:  OMP_NUM_THREADS=1 uv run python scripts/etp_trend/run_rotation.py
"""
from __future__ import annotations

import argparse
import math

import numpy as np
import pandas as pd

from run_trend import LOOKBACK, load_panel, run, stats


def rotation_targets(hist: pd.DataFrame, eligible: list[str], cols: list[str]) -> pd.Series:
    """상위 절반 등가중. `hist`는 신호일 종가까지만 담긴다(룩아헤드 없음).

    Args:
        hist: 신호일까지의 종가. 마지막 행이 신호일이다.
        eligible: 253거래일 이력이 쌓인 위험자산.
        cols: 전체 컬럼(현금 포함). 반환 Series의 인덱스다.

    Returns:
        목표비중. 상위 `⌈len(eligible)/2⌉` 종목에 균등 배분하고 합은 1이다.
    """
    mom = {}
    for s in eligible:
        px = hist[s].dropna()
        mom[s] = px.iloc[-1] / px.iloc[-LOOKBACK - 1] - 1
    k = math.ceil(len(eligible) / 2)
    top = sorted(mom, key=lambda s: mom[s], reverse=True)[:k]
    target = pd.Series(0.0, index=cols)
    target[top] = 1.0 / k
    return target


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=None)
    args = ap.parse_args()

    close, open_ = load_panel()
    print(f"패널: {close.shape[0]}거래일 × {close.shape[1]}자산 "
          f"({close.index[0].date()} ~ {close.index[-1].date()})")

    strat = run(close, open_, timing=True, target_fn=rotation_targets)
    bench_rb = run(close, open_, timing=False, rebalance=True)
    bench_bh = run(close, open_, timing=False, rebalance=False)

    idx = strat["equity"].index
    for b in (bench_rb, bench_bh):
        idx = idx.intersection(b["equity"].index)
    sr = strat["equity"].loc[idx].pct_change().dropna()
    rb = bench_rb["equity"].loc[idx].pct_change().dropna()
    bh = bench_bh["equity"].loc[idx].pct_change().dropna()

    print(f"\n{'구분':24s} {'CAGR':>8s} {'변동성':>8s} {'Sharpe':>8s} {'MDD':>8s}")
    for name, r in (("전략(상위절반 로테이션)", sr), ("벤치A 월간등가중", rb),
                    ("벤치B 순수매수보유", bh)):
        s = stats(r)
        print(f"{name:24s} {s['cagr']:>8.2%} {s['vol']:>8.2%} {s['sharpe']:>8.2f} "
              f"{s['mdd']:>8.2%}")

    print(f"\n{'='*68}\n판정 좌변 — 비용후 net excess\n{'='*68}")
    yrs = len(sr) / 252
    for label, ex in (("A 월간등가중 대비 (주 판정)", (sr - rb).dropna()),
                      ("B 순수매수보유 대비 (참고)", (sr - bh).dropna())):
        cagr = (1 + ex).prod() ** (1 / yrs) - 1
        ir = ex.mean() / ex.std() * np.sqrt(252) if ex.std() else float("nan")
        print(f"  {label:34s} 연율 {cagr:+7.2%}  IR {ir:+6.3f}")

    tv = strat["turnover"]
    ann = tv.sum() / yrs
    print(f"\n회전율: 리밸 {len(tv)}회 · 연 Σ|Δw| {ann:.2f} (임계 12) "
          f"→ {'❌ 무효' if ann > 12 else '✅'}")
    print(f"보유 종목 수: 중앙 {(strat['weights'] > 0).sum(axis=1).median():.0f}개")

    print(f"\n구간별 (보고 전용){'':10s}{'전략':>10s}{'벤치A':>10s}{'초과':>10s}")
    for lo, hi in (("2004", "2011"), ("2012", "2018"), ("2019", "2026")):
        m = (sr.index >= f"{lo}-01-01") & (sr.index <= f"{hi}-12-31")
        if m.sum() < 250:
            continue
        y = m.sum() / 252
        cs = (1 + sr[m]).prod() ** (1 / y) - 1
        cb = (1 + rb[m]).prod() ** (1 / y) - 1
        print(f"  {lo}~{hi} ({m.sum():4d}일){'':4s}{cs:>10.2%}{cb:>10.2%}{cs - cb:>10.2%}")

    if args.csv:
        pd.DataFrame({"strategy": sr, "bench_rebal": rb, "bench_bh": bh}).to_csv(args.csv)
        print(f"\n수익 계열 저장: {args.csv}")


if __name__ == "__main__":
    main()
