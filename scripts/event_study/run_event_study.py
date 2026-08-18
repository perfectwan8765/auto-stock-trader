"""단계 3 — 이벤트스터디 [1층 게이트]. 판정 지점이다.

측정 정의는 전부 사전등록 §5·§9 A-2에 박혀 있다 — 여기서 바꾸면 위반이다.
진입 t+1 시가 · 청산 H거래일 뒤 종가 · BHAR = 실현 − 팩터모형 기대 · 추정창 t−250~t−31 ·
비용 왕복(수수료 0.10%×2 + spread_final×2) · winsor 1% 횡단면 · 교차상관 보정 t · 판정 h=0.

실행:  .venv/bin/python scripts/event_study/run_event_study.py
옵션:  --horizons 30 60 90   --no-cost(비용 전 값 확인용, 판정 아님)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_panel import judged_population, load_factors, load_prices, load_sic

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "event_study_bhar.csv"

FACTOR_COLS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "MOM", "IWC"]
EST_START, EST_END = 250, 31          # 추정창 t−250 ~ t−31 (거래일)
EST_MIN_OBS = 100
COMMISSION = 0.0010                    # 편도. 실측 0.10~0.13% 중 하한
CATASTROPHE = -0.55                    # 파산 손실 가정 (Shumway)
EXIT_RATE = 0.031                      # 보유기간 내 퇴출 비율 (전수 측정)
WINSOR = 0.01


def _estimate(px: pd.DataFrame, fac: pd.DataFrame, entry_idx: int) -> tuple[np.ndarray, float] | None:
    """(팩터 베타, 잔차 일별 표준편차)."""
    lo, hi = entry_idx - EST_START, entry_idx - EST_END
    if lo < 0:
        return None
    win = px.iloc[lo:hi]
    r = (win.close / win.close.shift(1) - 1).dropna()
    d = fac.reindex(r.index).dropna()
    if len(d) < EST_MIN_OBS:
        return None
    y = (r.reindex(d.index) - d.RF).values
    X = np.column_stack([np.ones(len(d)), d[FACTOR_COLS].values])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    return beta, float(resid.std(ddof=len(beta)))


def _bhar(px: pd.DataFrame, fac: pd.DataFrame, entry_idx: int, H: int,
          beta: np.ndarray, entry_price: float) -> tuple[float, float] | None:
    """(실현 보유수익, 기대 보유수익)."""
    exit_idx = entry_idx + H
    if exit_idx >= len(px):
        return None
    actual = px.close.iloc[exit_idx] / entry_price - 1

    # 진입일 종가 팩터수익은 전일 종가부터의 구간이라 포지션이 생기기 전을 포함한다(정정 A-3).
    win = px.iloc[entry_idx + 1:exit_idx + 1]
    d = fac.reindex(win.index).dropna()
    if len(d) < H * 0.6:               # 팩터 결측이 과하면 기대수익을 못 만든다
        return None
    daily = d.RF.values + d[FACTOR_COLS].values @ beta[1:]
    return float(actual), float(np.prod(1 + daily) - 1)


def compute(events: pd.DataFrame, prices: dict, fac: pd.DataFrame, H: int,
            entry_mode: str, apply_cost: bool) -> pd.DataFrame:
    rows, skipped = [], {"no_price": 0, "no_est": 0, "short_window": 0}
    for e in events.itertuples():
        px = prices.get(e.symbol)
        if px is None:
            skipped["no_price"] += 1
            continue
        after = px.index[px.index > e.filing_date]
        if len(after) == 0:
            skipped["no_price"] += 1
            continue
        t1 = px.index.get_loc(after[0])                     # t+1
        entry_idx = t1 - 1 if entry_mode == "t0_close" else t1
        est = _estimate(px, fac, entry_idx)
        if est is None:
            skipped["no_est"] += 1
            continue
        beta, sigma = est

        if entry_mode == "t1_open":
            entry_price = px.open.iloc[t1]
        elif entry_mode == "t1_close":
            entry_price = px.close.iloc[t1]
        else:                                               # t0_close — 이론 참고
            entry_price = px.close.iloc[t1 - 1]
        if not np.isfinite(entry_price) or entry_price <= 0:
            skipped["no_price"] += 1
            continue

        res = _bhar(px, fac, entry_idx, H, beta, entry_price)
        if res is None:
            skipped["short_window"] += 1
            continue
        actual, expected = res

        cost = 2 * (COMMISSION + (e.spread_final if np.isfinite(e.spread_final) else 0.0)) \
            if apply_cost else 0.0
        rows.append({
            "symbol": e.symbol, "cik": int(e.cik), "filing_date": e.filing_date,
            "entry_date": px.index[entry_idx], "mcap_usd": e.mcap_usd, "addv": e.addv,
            "spread": e.spread_final, "bhar": actual - expected - cost,
            "bhar_gross": actual - expected, "actual": actual, "sigma_d": sigma,
        })
    df = pd.DataFrame(rows)
    df.attrs["skipped"] = skipped
    return df


def _winsor(x: pd.Series, q: float = WINSOR) -> pd.Series:
    return x.clip(x.quantile(q), x.quantile(1 - q))


def cross_correlation_inflation(df: pd.DataFrame, H: int) -> tuple[float, float, float]:
    """Kolari-Pynnönen 팽창 계수 √(1+(n̄−1)ρ̄).

    n̄은 같은 날짜가 아니라 **보유기간이 겹치는 이벤트 수**다 — H=30의 동시 포지션이
    수백이라 겹치는 창을 무시하면 팽창을 과소평가한다.
    """
    ends = df.entry_date + pd.Timedelta(days=int(H * 1.45))     # 거래일 H ≈ 달력일 1.45H
    overlap = [(((df.entry_date <= e) & (ends >= s)).sum()) for s, e in zip(df.entry_date, ends)]
    n_bar = float(np.median(overlap))

    rho = df.attrs.get("rho_bar", np.nan)
    infl = float(np.sqrt(max(1.0 + (n_bar - 1) * rho, 1.0))) if np.isfinite(rho) else np.nan
    return n_bar, rho, infl


def estimate_rho(df: pd.DataFrame, prices: dict, fac: pd.DataFrame, max_sym: int = 120) -> float:
    """이벤트 종목 잔차의 평균 쌍상관 — 시장·팩터 제거 후 남는 횡단면 상관."""
    syms = df.symbol.value_counts().head(max_sym).index
    resid = {}
    for s in syms:
        px = prices[s]
        r = (px.close / px.close.shift(1) - 1).dropna()
        d = fac.reindex(r.index).dropna()
        if len(d) < 250:
            continue
        y = (r.reindex(d.index) - d.RF).values
        X = np.column_stack([np.ones(len(d)), d[FACTOR_COLS].values])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid[s] = pd.Series(y - X @ beta, index=d.index)
    R = pd.DataFrame(resid).dropna(how="all")
    C = R.corr().values
    iu = np.triu_indices_from(C, k=1)
    return float(np.nanmean(C[iu]))


def judge(df: pd.DataFrame, n_missing: int, H: int, label: str) -> dict:
    """판정 통계. n_missing에는 계산 실패분도 포함한다 — 짧은 이력·조기 소멸 쪽에 몰린
    비무작위 표본이라 빼면 경계가 낙관으로 기운다(정정 A-3).
    """
    x_raw = df.bhar
    x = _winsor(x_raw)
    n = len(x)
    mean = float(x.mean())

    # 섹터 통제는 평균이 아니라 SE를 바꾼다. 분모는 SIC가 붙은 행 수여야 한다 — 전체 n을
    # 쓰면 NaN 제외 std를 큰 수로 나누게 되어 SE가 과소평가된다.
    if "sic2" in df and df.sic2.notna().any():
        dem = (x - df.groupby("sic2").bhar.transform(lambda g: _winsor(g).mean())).dropna()
        se_sector = float(dem.std(ddof=1) / np.sqrt(len(dem))) if len(dem) > 1 else np.nan
    else:
        se_sector = float(x.std(ddof=1) / np.sqrt(n))
    se_plain = float(x.std(ddof=1) / np.sqrt(n))

    sar = x / (df.sigma_d * np.sqrt(H))
    t_bmp = float(sar.mean() / (sar.std(ddof=1) / np.sqrt(n)))

    n_bar, rho, infl = cross_correlation_inflation(df, H)
    t_plain = mean / se_plain
    t_sector = mean / se_sector
    t_adj = t_bmp / infl if np.isfinite(infl) else np.nan

    cov = n / (n + n_missing) if (n + n_missing) else 1.0
    bounds = {h: cov * mean + (1 - cov) * (EXIT_RATE * CATASTROPHE + (1 - EXIT_RATE) * mean * h)
              for h in (0.0, 0.5, 1.0)}

    return {"label": label, "H": H, "n": n, "n_missing": n_missing, "coverage": cov,
            "mean_raw": float(x_raw.mean()), "mean": mean,
            "t_plain": t_plain, "t_sector": t_sector, "t_bmp": t_bmp,
            "n_bar": n_bar, "rho": rho, "inflation": infl, "t_adj": t_adj,
            "bound_h0": bounds[0.0], "bound_h05": bounds[0.5], "bound_h1": bounds[1.0],
            "spread_p50": float(df.spread.median())}


def threshold(H: int, spread: float, target_net: float = 0.10) -> float:
    """§5.2 역산 — 목표 net에서 필요한 총 BHAR."""
    return target_net * H / 252 + 2 * (COMMISSION + spread)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizons", type=int, nargs="+", default=[30])
    ap.add_argument("--no-cost", action="store_true", help="비용 전 값 (판정 아님)")
    args = ap.parse_args()

    obs, miss = judged_population()
    print(f"판정 모집단 — 관측 후보 {len(obs):,} · 결측(폐지 전 이벤트) {len(miss):,}")
    prices, fac, sic = load_prices(), load_factors(), load_sic()
    print(f"가격 {len(prices)}종목 · 팩터 {len(fac)}일 ({fac.index.min().date()}~{fac.index.max().date()})")

    results, first = [], None
    for H in args.horizons:
        for mode in ("t1_open", "t1_close", "t0_close"):
            df = compute(obs, prices, fac, H, mode, apply_cost=not args.no_cost)
            if df.empty:
                continue
            df["sic2"] = df.cik.map(sic)
            if first is None:
                df.attrs["rho_bar"] = estimate_rho(df, prices, fac)
                first = df.attrs["rho_bar"]
                print(f"평균 잔차 쌍상관 ρ̄ = {first:.4f}")
            df.attrs["rho_bar"] = first
            if mode == "t1_open":
                df.to_csv(OUT.with_name(f"event_study_bhar_H{H}.csv"), index=False)
                print(f"  H={H} 산출 {len(df):,} · 제외 {df.attrs['skipped']}")
            n_skipped = sum(df.attrs["skipped"].values())
            results.append(judge(df, len(miss) + n_skipped, H, mode))

    r = pd.DataFrame(results)
    pd.set_option("display.width", 200)
    print("\n=== 판정표 (winsor 1% · 비용 후) ===")
    print(r[["label", "H", "n", "coverage", "mean", "t_plain", "t_sector", "t_bmp",
             "inflation", "t_adj", "bound_h0"]].to_string(index=False,
          float_format=lambda v: f"{v:.4f}"))

    for row in results:
        if row["label"] != "t1_open":
            continue
        th = threshold(row["H"], row["spread_p50"])
        print(f"\n★ H={row['H']} 판정 — 진입 t+1 시가 · h=0 비관 경계")
        print(f"   비관 경계 BHAR {row['bound_h0']:+.2%}  vs  임계 {th:.2%}"
              f"  → {'통과' if row['bound_h0'] >= th else '미달'}")
        print(f"   보정 t {row['t_adj']:.2f} (하한 3.0) → {'통과' if row['t_adj'] >= 3.0 else '미달'}")
        print(f"   교차상관 — ρ̄ {row['rho']:.4f} · n̄ {row['n_bar']:.0f} · 팽창 {row['inflation']:.2f}배"
              f" (가정 1.7배 대비 {row['inflation']/1.7:.2f})")


if __name__ == "__main__":
    main()
