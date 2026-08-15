"""30거래일 수익률 σ와 1층 검정력(t) 재계산 — 계획서 §3.13(2)(3).

왜 스크립트로 두나: t는 이상치 처리 규칙 하나로 1.77↔8.45까지 움직이고(첨도 4,131),
n에 √로 달려 있어 `measure_*` 산출물이 바뀔 때마다 다시 내야 한다. v3.3에서 이 계산이
임시 스크립트로 이뤄져 유실됐다(E5 위반).

    n_eff = n_events × coverage
    SE    = σ / √n_eff
    t     = CAR_true / (SE × inflation)      # inflation = 이벤트 군집 교차상관 SE 팽창

구조 통계·분산만 만든다 — 이벤트 조건부 수익률은 계산하지 않는다(계획서 §9 서두).

실행:  .venv/bin/python scripts/data_pipeline/measure_power.py
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CLOSES = ROOT / "data" / "candidate_closes.csv"
ADDV = ROOT / "data" / "events_addv.csv"

HORIZON = 30          # 거래일
WINSOR = (0.0, 0.01, 0.025, 0.05)


def sigma_by_rule(closes: pd.DataFrame, symbols: set[str]) -> tuple[dict[float, float], int, dict]:
    """유니버스 종목의 무조건부 30거래일 수익률에서 winsor 수준별 σ를 낸다."""
    px = closes[[c for c in closes.columns if c in symbols]]
    ret = (px.shift(-HORIZON) / px - 1.0).values.ravel()
    ret = ret[np.isfinite(ret)]
    sig = {}
    for w in WINSOR:
        r = ret if w == 0 else np.clip(ret, np.quantile(ret, w), np.quantile(ret, 1 - w))
        sig[w] = float(r.std(ddof=1))
    desc = {"mean": float(ret.mean()), "p50": float(np.median(ret)),
            "skew": float(pd.Series(ret).skew()), "kurt": float(pd.Series(ret).kurt())}
    return sig, len(ret), desc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--car", type=float, default=0.03, help="가정 참 CAR (1층 임계, 기본 3.0%)")
    ap.add_argument("--inflation", type=float, default=1.7, help="교차상관 SE 팽창 (문헌 예시치)")
    ap.add_argument("--addv-min", type=float, default=200e3)
    args = ap.parse_args()

    closes = pd.read_csv(CLOSES, index_col=0, parse_dates=True)
    ev = pd.read_csv(ADDV)
    ev = ev[ev.addv.notna()]

    main_spec = ev[(ev.mcap_usd < 300e6) & (ev.addv >= args.addv_min)]
    universe = set(main_spec.symbol.unique())
    sig, n_obs, desc = sigma_by_rule(closes, universe)

    span = pd.to_datetime(ev.filing_date)
    print(f"표본 구간 {span.min().date()} ~ {span.max().date()} "
          f"({(span.max() - span.min()).days / 365.25:.2f}년)")
    print(f"주 스펙 유니버스 {len(universe)}종목 · {HORIZON}거래일 수익률 관측 {n_obs:,}")
    print(f"  평균 {desc['mean']:+.1%}  중앙 {desc['p50']:+.1%}  "
          f"왜도 {desc['skew']:.1f}  첨도 {desc['kurt']:,.0f}")
    print("  σ — " + "  ".join(
        f"{'raw' if w == 0 else f'winsor {w:.1%}'} {sig[w]:.1%}" for w in WINSOR))

    cuts = [(100e6, "$100M"), (200e6, "$200M"), (300e6, "$300M"), (500e6, "$500M")]
    print(f"\n=== t (CAR_true={args.car:.1%}, 팽창 ×{args.inflation}) — ADDV≥${args.addv_min:,.0f} 적용 ===")
    header = "  {:<14}".format("이상치 규칙") + "".join(f"{name:>16}" for _, name in cuts)
    print(header)
    for w in WINSOR:
        row = f"  {'raw' if w == 0 else f'winsor {w:.1%}':<14}"
        for cut, _ in cuts:
            n = int((main_spec.mcap_usd < cut).sum()) if cut <= 300e6 else \
                int(((ev.mcap_usd < cut) & (ev.addv >= args.addv_min)).sum())
            t = args.car / (sig[w] / np.sqrt(n) * args.inflation)
            row += f"{f'n={n} t={t:.2f}':>16}"
        print(row)

    n_main = len(main_spec)
    t_main = args.car / (sig[0.01] / np.sqrt(n_main) * args.inflation)
    print(f"\n★ 주 스펙(<$300M ∩ Toss ∩ ADDV≥$200k, winsor 1%): n={n_main} → t={t_main:.2f}")


if __name__ == "__main__":
    main()
