"""전략 백테스트 수익을 벤치마크(SPY)에 CAPM 회귀 → beta·연율 alpha 분해.

목적: "SPY 대비 초과수익"이 진짜 selection alpha인지, 아니면 단순 beta 틸트
(고베타로 시장을 배수로 탄 것)인지 판별. 비용후 전략수익 y = alpha + beta·(벤치수익) 회귀.
- beta ≈ 1.5, alpha ≈ 0  → 초과는 beta 틸트(레버리지). 알파 아님.
- alpha 유의미 > 0        → beta 벗겨도 남는 진짜 우위.

실행: python scripts/model_backtest/analyze_capm.py [--glob PATTERN] [--limit N]
입력: mlruns의 PortAnaRecord 산출물(report_normal_1week.pkl). qlib 불요(pickle+numpy).
"""
from __future__ import annotations

import argparse
import glob
import os
import pickle
import time

import numpy as np

_DEFAULT_GLOB = "mlruns/*/*/artifacts/portfolio_analysis/report_normal_1week.pkl"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", default=_DEFAULT_GLOB)
    ap.add_argument("--limit", type=int, default=8, help="최근 N개 report")
    args = ap.parse_args()

    paths = sorted(glob.glob(args.glob), key=os.path.getmtime, reverse=True)[: args.limit]
    if not paths:
        raise SystemExit(f"[오류] report 없음: {args.glob} — 먼저 백테스트 실행")

    print(f"{'excess/yr':>9} {'beta':>6} {'alpha/yr':>9} {'R2':>5}  mtime")
    for p in paths:
        r = pickle.load(open(p, "rb"))
        if not {"return", "bench"}.issubset(r.columns):
            continue
        net = r["return"] - r.get("cost", 0.0)     # 비용후 전략수익
        x, y = r["bench"].values, net.values
        beta, alpha = np.polyfit(x, y, 1)          # 주간 회귀: y = alpha + beta·x
        yhat = alpha + beta * x
        r2 = 1 - ((y - yhat) ** 2).sum() / (((y - y.mean()) ** 2).sum() + 1e-12)
        exc = (y - x).mean() * 52                   # 비용후 초과(연) — 대조용
        mt = time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(p)))
        print(f"{exc:>+8.1%} {beta:>6.2f} {alpha * 52:>+8.1%} {r2:>5.2f}  {mt}")


if __name__ == "__main__":
    main()
