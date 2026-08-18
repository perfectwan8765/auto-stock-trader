"""매크로 ETF 장기반전(자산군 가치) — 1층 판정.

정의는 사전등록 `docs/project/etp-prereg.md` §0(공통)·§3(연구 C). 1,260거래일(5년) 총수익으로
자산 간 순위 → **하위 절반 k=⌈N/2⌉ 등가중** · 항상 100% 투자 · 편입은 1,261거래일 이력.
나머지는 자매 문서 2편에서 상속한다.

⚠️ §3의 QQQ 민감도는 **보고 전용이며 판정은 10자산으로만** 한다.

실행:  OMP_NUM_THREADS=1 .venv/bin/python scripts/etp_trend/run_reversal.py
"""
from __future__ import annotations

import argparse
import math

import numpy as np
import pandas as pd
from scipy.stats import norm

from run_trend import RISK, load_panel, run, stats

LOOKBACK_REV = 1260     # §1 — AMP의 자산군 value 대용 호라이즌(5년)
MIN_HISTORY_REV = 1261


def reversal_targets(hist: pd.DataFrame, eligible: list[str], cols: list[str]) -> pd.Series:
    """**하위 절반** 등가중. 지난 5년 수익이 낮은 쪽을 산다(반전).

    Args:
        hist: 신호일까지의 종가. 마지막 행이 신호일이다.
        eligible: 1,261거래일 이력이 쌓인 위험자산.
        cols: 전체 컬럼. 반환 Series의 인덱스다.

    Returns:
        목표비중. 하위 `⌈len(eligible)/2⌉` 종목에 균등 배분하고 합은 1이다.
    """
    mom = {}
    for s in eligible:
        px = hist[s].dropna()
        mom[s] = px.iloc[-1] / px.iloc[-LOOKBACK_REV - 1] - 1
    k = math.ceil(len(eligible) / 2)
    bottom = sorted(mom, key=lambda s: mom[s])[:k]      # ★ 오름차순 = 부진했던 쪽
    target = pd.Series(0.0, index=cols)
    target[bottom] = 1.0 / k
    return target


def judge(close, open_, universe: list[str], label: str) -> dict:
    """전략·벤치A·벤치B를 한 유니버스에서 굴리고 판정 통계를 낸다."""
    kw = {"risk": universe, "min_history": MIN_HISTORY_REV}
    strat = run(close, open_, timing=True, target_fn=reversal_targets, **kw)
    rbal = run(close, open_, timing=False, rebalance=True, **kw)
    bh = run(close, open_, timing=False, rebalance=False, **kw)

    idx = strat["equity"].index
    for b in (rbal, bh):
        idx = idx.intersection(b["equity"].index)
    s = strat["equity"].loc[idx].pct_change().dropna()
    a = rbal["equity"].loc[idx].pct_change().dropna()
    b_ = bh["equity"].loc[idx].pct_change().dropna()
    return {"label": label, "strat": s, "bench_a": a, "bench_b": b_,
            "turnover": strat["turnover"], "weights": strat["weights"]}


def psr(x: pd.Series) -> tuple[float, float]:
    """(연율 IR, PSR). PSR은 다중검정 무시 상한이며 정의상 `DSR ≤ PSR`이다."""
    x = x.dropna()
    sr = x.mean() / x.std(ddof=1)
    g3, g4 = x.skew(), x.kurt() + 3.0
    den = np.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr**2)
    return sr * np.sqrt(252), float(norm.cdf(sr * np.sqrt(len(x) - 1) / den))


def report(r: dict) -> None:
    yrs = len(r["strat"]) / 252
    print(f"\n{'='*70}\n{r['label']}\n{'='*70}")
    print(f"{'구분':22s} {'CAGR':>8s} {'변동성':>8s} {'Sharpe':>8s} {'MDD':>8s}")
    for name, x in (("전략(하위절반 반전)", r["strat"]), ("벤치A 월간등가중", r["bench_a"]),
                    ("벤치B 순수매수보유", r["bench_b"])):
        st = stats(x)
        print(f"{name:22s} {st['cagr']:>8.2%} {st['vol']:>8.2%} {st['sharpe']:>8.2f} "
              f"{st['mdd']:>8.2%}")
    for tag, ex in (("A 대비 (주 판정)", r["strat"] - r["bench_a"]),
                    ("B 대비 (참고)", r["strat"] - r["bench_b"])):
        ex = ex.dropna()
        ir, p = psr(ex)
        cagr = (1 + ex).prod() ** (1 / yrs) - 1
        print(f"  {tag:20s} 연율 {cagr:+7.2%}  IR {ir:+6.3f}  PSR {p:6.4f}"
              f"  {'→ 임계 0.95 미달' if p <= 0.95 else '→ 통과'}")
    ann = r["turnover"].sum() / yrs
    print(f"  회전율 연 Σ|Δw| {ann:.2f} (임계 12) → {'❌ 무효' if ann > 12 else '✅'}"
          f" · 보유 중앙 {(r['weights'] > 0).sum(axis=1).median():.0f}개"
          f" · OOS {yrs:.1f}년")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=None)
    args = ap.parse_args()
    close, open_ = load_panel()
    print(f"패널: {close.shape[0]}거래일 × {close.shape[1]}자산")

    main_r = judge(close, open_, RISK, "판정 — 10자산 (§1)")
    report(main_r)

    sens = judge(close, open_, [s for s in RISK if s != "QQQ"],
                 "민감도 — QQQ 제외 9자산 (§2.3 보고 전용, 판정 아님)")
    report(sens)

    if args.csv:
        pd.DataFrame({"strategy": main_r["strat"], "bench_rebal": main_r["bench_a"],
                      "bench_bh": main_r["bench_b"]}).to_csv(args.csv)
        print(f"\n수익 계열 저장: {args.csv}")


if __name__ == "__main__":
    main()
