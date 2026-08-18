"""단계 3 진단 — 사전등록 §5가 요구하는 층화·교차확인. 전부 진단이라 판정에도 N에도 쓰지 않는다.

  (1) 공시 전 20거래일 모멘텀 버킷 — 파이프라인 신뢰성 검사. 원논문 Table 4의 price deviation은
      ≤0% → 2.3% … >10% → 6.3%로 단조 증가한다. 정규화 가격은 거래단가와 수준 비교가 안 돼
      모멘텀을 대리로 쓴다. 같은 방향이 안 나오면 파이프라인을 의심해야 한다.
  (2) NANO 층화  (3) 은행 제외 부표본  (4) raw vs winsor  (5) calendar-time (D16 교차확인)

실행:  .venv/bin/python scripts/event_study/diagnostics.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_panel import load_factors, load_prices, load_sic

ROOT = Path(__file__).resolve().parents[2]
BHAR = ROOT / "data" / "event_study_bhar_H30.csv"
FACTOR_COLS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "MOM", "IWC"]
BANK_SIC = {"60", "61", "62"}          # 예금기관·비예금 신용·증권 — SIC 2자리


def _t(x: pd.Series) -> float:
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 1 else np.nan


def _line(name: str, x: pd.Series, col: str = "bhar_gross") -> None:
    print(f"  {name:<26} n={len(x):>5}  평균 {x[col].mean():+7.2%}  t={_t(x[col]):>6.2f}"
          f"   비용후 {x.bhar.mean():+7.2%}")


def main() -> None:
    df = pd.read_csv(BHAR, parse_dates=["filing_date", "entry_date"])
    prices, fac, sic = load_prices(), load_factors(), load_sic()
    df["sic2"] = df.cik.map(sic)
    print(f"판정 표본 n={len(df)} · 총 BHAR {df.bhar_gross.mean():+.2%} (t={_t(df.bhar_gross):.2f})"
          f" · 비용후 {df.bhar.mean():+.2%}")

    print("\n=== (1) 공시 전 20거래일 모멘텀 버킷 — 파이프라인 신뢰성 검사 ===")
    mom = []
    for r in df.itertuples():
        px = prices[r.symbol]
        prior = px.index[px.index <= r.filing_date]
        if len(prior) < 21:
            mom.append(np.nan); continue
        mom.append(px.close.loc[prior[-1]] / px.close.loc[prior[-21]] - 1)
    df["mom20"] = mom
    sub = df.dropna(subset=["mom20"])
    edges = [-1, -0.05, 0.0, 0.05, 0.10, 10]
    labels = ["≤−5%", "−5~0%", "0~5%", "5~10%", ">10%"]
    sub = sub.assign(bucket=pd.cut(sub.mom20, edges, labels=labels))
    for b in labels:
        g = sub[sub.bucket == b]
        if len(g) > 20:
            _line(b, g)

    print("\n=== (2) NANO(<$50M) 층화 ===")
    _line("NANO", df[df.mcap_usd < 50e6])
    _line("NANO 제외", df[df.mcap_usd >= 50e6])

    print("\n=== (3) 은행 제외 부표본 ===")
    is_bank = df.sic2.isin(BANK_SIC)
    _line(f"은행 (SIC 60~62)", df[is_bank])
    _line("은행 제외", df[~is_bank])

    print("\n=== (4) raw vs winsor 1% ===")
    for name, x in (("raw", df.bhar), ("winsor 1%", df.bhar.clip(df.bhar.quantile(.01),
                                                                 df.bhar.quantile(.99)))):
        print(f"  {name:<12} 평균 {x.mean():+7.2%}  σ {x.std():6.2%}  t={_t(x):>6.2f}")

    print("\n=== (5) calendar-time portfolio (D16 교차확인) ===")
    hold = {}
    for r in df.itertuples():
        px = prices[r.symbol]
        idx = px.index.get_loc(r.entry_date)
        for d in px.index[idx:idx + 30]:
            hold.setdefault(d, []).append(r.symbol)
    rets = {}
    for d, syms in hold.items():
        vals = []
        for s in syms:
            px = prices[s]
            if d not in px.index:
                continue
            i = px.index.get_loc(d)
            if i == 0:
                continue
            vals.append(px.close.iloc[i] / px.close.iloc[i - 1] - 1)
        if vals:
            rets[d] = np.mean(vals)
    port = pd.Series(rets).sort_index()
    d = fac.reindex(port.index).dropna()
    y = (port.reindex(d.index) - d.RF).values
    X = np.column_stack([np.ones(len(d)), d[FACTOR_COLS].values])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    se = np.sqrt((resid @ resid) / (len(y) - X.shape[1]) * np.linalg.inv(X.T @ X)[0, 0])
    print(f"  일별 alpha {beta[0]*100:+.4f}%  연환산 {beta[0]*252*100:+.2f}%  t={beta[0]/se:.2f}"
          f"  (관측 {len(y)}일)")
    print(f"  → 이벤트 단위 총 BHAR({df.bhar_gross.mean():+.2%})과 "
          f"{'같은 부호' if np.sign(beta[0]) == np.sign(df.bhar_gross.mean()) else '⚠️ 다른 부호'}")


if __name__ == "__main__":
    main()
