"""이벤트별 스프레드 추정 — 계획서 §5 단계 1(j). Toss가 호가를 안 주므로 일봉 OHLC로 대체한다.

산출: data/events_spread.csv — 추정량 3종 × 창 4개(`{edge,cs,ar}_w{30,60,120,252}`)와
      단계 3이 실제로 부과하는 `spread_final`. 이벤트별 부과이며 횡단면 분위 고정은 금지(§9 #15).

원래 합격선은 "음수 추정 ≤10%"였으나 세 추정량·네 창이 전부 미달해 음수 처리 규칙으로
교체했다(이탈 D-2). 실측 음수 비율은 EDGE 14.7% < AR 16.2% << CS 51.9%(w252).

실행:  .venv/bin/python scripts/data_pipeline/measure_edge_spread.py
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from bidask import edge_rolling
from spread_estimators import abdi_ranaldo, corwin_schultz

ROOT = Path(__file__).resolve().parents[2]
ADDV = ROOT / "data" / "events_addv.csv"
OUT = ROOT / "data" / "events_spread.csv"

# 짧은 창일수록 음수 추정이 늘어난다. 합격선을 만족하는 가장 짧은 창을 고르려고 한 번에 잰다.
WINDOWS = (30, 60, 120, 252)
ESTIMATORS = ("edge", "cs", "ar")     # 우선순위 — EDGE가 주 추정량, CS·AR은 대조(§3.12(3))
PRIMARY = "edge_w252"                 # 대조 결과 채택 — 세 추정량·네 창 중 음수 비율 최저
CHUNK = 50


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true",
                    help="이미 만든 events_spread.csv로 표만 다시 낸다")
    args = ap.parse_args()

    if args.report_only:
        out = pd.read_csv(OUT)
        _report(out)
        _finalize(out).to_csv(OUT, index=False)
        return

    ev = pd.read_csv(ADDV, parse_dates=["filing_date"])
    syms = sorted(ev.symbol.unique())
    start = (ev.filing_date.min() - pd.Timedelta(days=max(WINDOWS) * 2)).date()
    end = (ev.filing_date.max() + pd.Timedelta(days=5)).date()
    print(f"대상 {len(syms)}종목 / {len(ev)}이벤트 · {start}~{end}", flush=True)

    spread = {(e, w): {} for e in ESTIMATORS for w in WINDOWS}
    for i in range(0, len(syms), CHUNK):
        chunk = syms[i:i + CHUNK]
        try:
            raw = yf.download(chunk, start=start, end=end, progress=False,
                              auto_adjust=False, group_by="ticker", threads=True)
        except Exception as e:                                  # noqa: BLE001
            print(f"  chunk {i} 실패: {e}", flush=True)
            continue
        for s in chunk:
            try:
                ohlc = raw[s][["Open", "High", "Low", "Close"]].dropna()
            except Exception:                                   # noqa: BLE001
                continue
            for w in WINDOWS:
                if len(ohlc) <= w:
                    continue
                # sign=False(기본)는 sqrt(|s2|)라 음수가 지워져 합격선 판정이 무의미해진다
                spread[("edge", w)][s] = edge_rolling(ohlc, window=w, sign=True)
                spread[("cs", w)][s] = corwin_schultz(ohlc.High, ohlc.Low, w)
                spread[("ar", w)][s] = abdi_ranaldo(ohlc.High, ohlc.Low, ohlc.Close, w)
        print(f"  {min(i + CHUNK, len(syms))}/{len(syms)}", flush=True)

    out = ev[["symbol", "cik", "filing_date", "mcap_usd", "addv"]].copy()
    for (est, w), panel in spread.items():
        sp = pd.DataFrame(panel).sort_index()
        sp.index = pd.to_datetime(sp.index).tz_localize(None)
        # 이벤트별 = 공시일 이전 최신 관측 (미래 누수 방지)
        vals = []
        for r in ev.itertuples():
            if r.symbol not in sp.columns:
                vals.append(None); continue
            ser = sp[r.symbol].loc[:r.filing_date].dropna()
            vals.append(ser.iloc[-1] if len(ser) else None)
        out[f"{est}_w{w}"] = vals
    print(f"\n[완료] {OUT.relative_to(ROOT)}")
    _report(out)
    _finalize(out).to_csv(OUT, index=False)


def _report(out: pd.DataFrame) -> None:
    main = out[(out.mcap_usd < 300e6) & (out.addv >= 200e3)]
    for name, sub in (("전체(<$500M)", out), ("주 스펙(<$300M ∩ ADDV≥$200k)", main)):
        print(f"\n=== {name} (이벤트 {len(sub)}) ===")
        print("  {:<6}{:<7}{:>8}{:>10}{:>8}{:>26}".format(
            "추정량", "창", "산출률", "음수비율", "합격선", "편도 스프레드 p25/p50/p90"))
        for est in ESTIMATORS:
            for w in WINDOWS:
                col = f"{est}_w{w}"
                if col not in sub:
                    continue
                ok = sub[col].dropna()
                if ok.empty:
                    continue
                neg = (ok < 0).mean()
                pos = ok.clip(lower=0)
                print(f"  {est:<6}{w:<7}{len(ok)/len(sub):>8.1%}{neg:>10.1%}"
                      f"{'통과' if neg <= 0.10 else '미달':>8}"
                      f"{f'{pos.quantile(.25):.2%} / {pos.median():.2%} / {pos.quantile(.9):.2%}':>26}")

    passing = [(est, w) for est in ESTIMATORS for w in WINDOWS
               if f"{est}_w{w}" in main
               and (main[f"{est}_w{w}"].dropna() < 0).mean() <= 0.10]
    grid = [(0.0023, "0.23%"), (0.008, "0.80%"), (0.015, "1.50%"), (0.020, "2.00%")]
    if passing:
        est, w = min(passing, key=lambda p: (ESTIMATORS.index(p[0]), p[1]))
        med = main[f"{est}_w{w}"].dropna().clip(lower=0).median()
        loc = int(np.searchsorted([g for g, _ in grid], med))
        print(f"\n★ 합격선을 넘는 (추정량, 창) 중 우선순위 1위 = ({est}, {w}거래일) · 중앙값 {med:.2%} "
              f"→ §9 #8 격자 {'최저행 아래' if loc == 0 else grid[min(loc, len(grid)-1)][1] + ' 부근'}")
    else:
        print("\n★ 어느 추정량·창도 합격선(음수 ≤10%)을 넘지 못했다 — 세 추정량 전부가 이 유니버스에서"
              " 같은 방향으로 실패한다. 합격선 자체를 재명세할지 사용자 판단 필요(§3.12(3))")


def _finalize(out: pd.DataFrame) -> pd.DataFrame:
    """단계 3이 부과할 `spread_final`.

    음수는 "스프레드 0"이 아니라 추정 실패다. 0으로 클립하면 비용을 과소 계상해 판정이
    낙관으로 기울므로, 같은 ADDV 십분위의 양수 중앙값으로 대체한다(이탈 D-2).
    """
    src = out[PRIMARY].astype(float)
    decile = pd.qcut(out.addv.rank(method="first"), 10, labels=False)
    med = src.where(src > 0).groupby(decile).transform("median")
    out["spread_final"] = src.where(src > 0, med)
    filled = int(src.notna().sum() - (src > 0).sum())
    print(f"\n=== 부과 스프레드 `spread_final` ({PRIMARY}, 음수·결측은 ADDV 십분위 중앙값 대체) ===")
    print(f"  대체 {filled + int(src.isna().sum())}건 / {len(out)}  ·  잔여 결측 {int(out.spread_final.isna().sum())}건")
    main = out[(out.mcap_usd < 300e6) & (out.addv >= 200e3)].spread_final.dropna()
    print("  주 스펙 분포: " + "  ".join(
        f"p{int(q*100)}={main.quantile(q):.2%}" for q in (.25, .5, .75, .9)) +
        f"  평균 {main.mean():.2%}")
    return out


if __name__ == "__main__":
    main()
