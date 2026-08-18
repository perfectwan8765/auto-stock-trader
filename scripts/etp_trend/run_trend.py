"""매크로 ETF 시계열 모멘텀 — 1층 판정.

측정 정의는 전부 사전등록 `docs/project/etp-trend-prereg.md` §1·§3에 박혀 있다.
여기서 바꾸면 이탈이다 — 252거래일 총수익 부호 · 자산별 1/N 슬리브 · 월말 종가 신호 →
다음 거래일 시가 집행 · 비용 편도 0.23% · 253거래일 이력 후 편입 · 현금 SHY.

⚠️ 벤치마크는 SPY가 아니라 **같은 위험자산 10종의 등가중 매수보유**다. 분산의 몫을
타이밍의 몫으로 착각하지 않기 위한 것이며 이것이 판정의 좌변을 정한다(§0).

실행:  OMP_NUM_THREADS=1 .venv/bin/python scripts/etp_trend/run_trend.py
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

RISK = ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "IEF", "GLD", "DBC", "VNQ"]
CASH = "SHY"
LOOKBACK = 252          # §1 고정. 다른 값을 시도하면 시행 +1
MIN_HISTORY = 253       # 편입 조건: 룩백 계산이 가능해지는 최소 이력
COST_PER_SIDE = 0.0023  # §1 — Phase 0 실측(수수료 0.10 + 환전 0.03 + 슬리피지 0.10)


def load_panel() -> tuple[pd.DataFrame, pd.DataFrame]:
    """(종가, 시가) 와이드 프레임. 배당·분할 조정된 값이다(02_normalize의 factor 적용)."""
    import qlib
    from qlib.config import REG_US
    from qlib.data import D

    qlib.init(provider_uri=str(ROOT / "data" / "qlib_us_etp"), region=REG_US, kernels=1)
    df = D.features(RISK + [CASH], ["$close", "$open"], "2003-01-01", "2026-12-31")
    close = df["$close"].unstack("instrument")
    open_ = df["$open"].unstack("instrument")
    return close.sort_index(), open_.reindex(close.index)


def month_end_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    """각 달의 마지막 거래일. 신호를 이 날 종가로 만든다."""
    s = pd.Series(index, index=index)
    return list(s.groupby([index.year, index.month]).last())


def run(close: pd.DataFrame, open_: pd.DataFrame, *, timing: bool, rebalance: bool = True) -> dict:
    """전략 또는 벤치마크를 굴린다. 세 경로가 **같은 함수를 지나는 것이 요점이다** —
    편입 규칙·집행 시점·비용 처리가 갈리면 초과수익이 그 차이를 재게 된다.

    Args:
        close: 일별 종가(조정). 신호와 평가에 쓴다.
        open_: 일별 시가(조정). 집행가다.
        timing: True면 252일 총수익 부호로 자산별 온/오프, False면 항상 위험자산 전량.
        rebalance: False면 첫 달에만 매수하고 이후 비중을 방치한다(순수 매수보유).

    Returns:
        `equity`(일별 순자산) · `weights`(집행 시점 목표비중) · `turnover`(리밸별 Σ|Δw|).
    """
    dates = close.index
    cols = list(close.columns)
    equity = pd.Series(index=dates, dtype=float)
    shares = pd.Series(0.0, index=cols)
    turnover, wlog = [], {}
    pos = None                                # 마지막 집행일. None이면 아직 미진입

    for t in month_end_dates(dates):
        i = dates.get_loc(t)
        if i + 1 >= len(dates):
            break                             # 집행일이 없다 — 마지막 달은 버린다
        exec_i = i + 1                         # §1: 월말 종가 신호 → 다음 거래일 시가 집행

        # 편입 자격: 253거래일 이력이 쌓인 자산만 (§1)
        eligible = [s for s in RISK if close[s].iloc[: i + 1].notna().sum() >= MIN_HISTORY]
        if not eligible:
            continue
        if pos is not None and not rebalance:
            continue                           # 매수보유: 첫 집행 후 손대지 않는다

        # 신호: 자산별 252거래일 총수익 부호. 종가 i까지만 본다 = 룩아헤드 없음
        target = pd.Series(0.0, index=cols)
        w = 1.0 / len(eligible)
        for s in eligible:
            hist = close[s].iloc[: i + 1].dropna()
            if not timing or hist.iloc[-1] / hist.iloc[-LOOKBACK - 1] - 1 > 0:
                target[s] = w
            else:
                target[CASH] += w              # 추세 음수 → 그 슬리브만 현금

        # 집행 전날까지의 순자산 진행(주식수 고정 = 비중 드리프트)
        if pos is not None:
            seg = close.iloc[pos:exec_i]
            equity.iloc[pos:exec_i] = (seg * shares).sum(axis=1)

        # 집행: 시가로 목표비중 달성. 비용은 Σ|Δw| × 편도 (|Δw| 한 단위 = 거래 한 쪽)
        ep = open_.iloc[exec_i]
        val = float((ep * shares).sum()) if pos is not None else 1.0
        cur_w = (ep * shares) / val if pos is not None and val > 0 else pd.Series(0.0, index=cols)
        dw = float((target - cur_w).abs().sum())
        turnover.append(dw)
        val *= 1 - dw * COST_PER_SIDE
        shares = (target * val / ep).fillna(0.0)
        wlog[dates[exec_i]] = target.copy()
        # ★ pos를 exec_i로 둔다(exec_i+1이 아니다). 다음 구간이 집행일 **종가**부터 평가하므로
        #   집행일 시가→종가 수익이 빠지지 않는다. exec_i+1로 두면 매달 하루치가 사라진다.
        pos = exec_i

    if pos is not None:
        equity.iloc[pos:] = (close.iloc[pos:] * shares).sum(axis=1)
    return {"equity": equity.dropna(), "weights": pd.DataFrame(wlog).T,
            "turnover": pd.Series(turnover)}


def stats(ret: pd.Series, periods: int = 252) -> dict:
    """연율 수익·변동성·Sharpe·최대낙폭. 판정이 아니라 보고용이다(§3.1)."""
    cum = (1 + ret).prod()
    yrs = len(ret) / periods
    curve = (1 + ret).cumprod()
    return {"cagr": cum ** (1 / yrs) - 1, "vol": ret.std() * np.sqrt(periods),
            "sharpe": ret.mean() / ret.std() * np.sqrt(periods) if ret.std() else np.nan,
            "mdd": float((curve / curve.cummax() - 1).min()), "years": yrs}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=None, help="일별 수익 계열을 저장할 경로")
    args = ap.parse_args()

    close, open_ = load_panel()
    print(f"패널: {close.shape[0]}거래일 × {close.shape[1]}자산 "
          f"({close.index[0].date()} ~ {close.index[-1].date()})")

    strat = run(close, open_, timing=True)
    bench_rb = run(close, open_, timing=False, rebalance=True)    # 월간 등가중 재조정
    bench_bh = run(close, open_, timing=False, rebalance=False)   # 순수 매수보유

    idx = strat["equity"].index
    for b in (bench_rb, bench_bh):
        idx = idx.intersection(b["equity"].index)
    sr = strat["equity"].loc[idx].pct_change().dropna()
    rb = bench_rb["equity"].loc[idx].pct_change().dropna()
    bh = bench_bh["equity"].loc[idx].pct_change().dropna()

    print(f"\n{'구분':22s} {'CAGR':>8s} {'변동성':>8s} {'Sharpe':>8s} {'MDD':>8s}")
    for name, r in (("전략(타이밍)", sr), ("벤치A 월간등가중", rb), ("벤치B 순수매수보유", bh)):
        s = stats(r)
        print(f"{name:22s} {s['cagr']:>8.2%} {s['vol']:>8.2%} {s['sharpe']:>8.2f} {s['mdd']:>8.2%}")

    print(f"\n{'='*66}\n판정 좌변 — 비용후 net excess\n{'='*66}")
    yrs = len(sr) / 252
    for label, ex in (("A 월간등가중 대비 (주 판정, 정정 A-2)", (sr - rb).dropna()),
                      ("B 순수매수보유 대비 (참고 — 더 높은 바)", (sr - bh).dropna())):
        cagr = (1 + ex).prod() ** (1 / yrs) - 1
        ir = ex.mean() / ex.std() * np.sqrt(252) if ex.std() else float("nan")
        print(f"  {label:38s} 연율 {cagr:+7.2%}  IR {ir:+6.3f}")

    tv = strat["turnover"]
    ann = tv.sum() / yrs
    print(f"\n회전율: 리밸 {len(tv)}회 · 연 Σ|Δw| {ann:.2f} "
          f"(정정 A-1 임계 12) → {'❌ 무효' if ann > 12 else '✅'}")

    # §2.1 — 비겹침 3구간. **보고용이며 어느 구간도 선택 근거로 쓰지 않는다.**
    print(f"\n구간별 (보고 전용) {'':10s}{'전략':>10s}{'벤치A':>10s}{'초과':>10s}")
    for lo, hi in (("2004", "2011"), ("2012", "2018"), ("2019", "2026")):
        m = (sr.index >= f"{lo}-01-01") & (sr.index <= f"{hi}-12-31")
        if m.sum() < 250:
            continue
        y = m.sum() / 252
        cs = (1 + sr[m]).prod() ** (1 / y) - 1
        cb = (1 + rb[m]).prod() ** (1 / y) - 1
        print(f"  {lo}~{hi} ({m.sum():4d}일){'':6s}{cs:>10.2%}{cb:>10.2%}{cs - cb:>10.2%}")

    if args.csv:
        pd.DataFrame({"strategy": sr, "bench_rebal": rb, "bench_bh": bh}).to_csv(args.csv)
        print(f"\n수익 계열 저장: {args.csv}")


if __name__ == "__main__":
    main()
