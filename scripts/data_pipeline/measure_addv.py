"""이벤트별 ADDV(30거래일 평균 거래대금) 산출.

작업계획서 §5 단계 1(k). 거래량이 파이프라인에 없어 §9 #11(ADDV 유동성 하한)을
정할 수 없었다. yfinance Volume × Close로 이벤트 시점 trailing ADDV를 만든다.

산출: data/events_addv.csv  (symbol, filing_date, mcap_usd, mcap_source, addv)

구조 통계만 만든다 — 수익률은 계산하지 않는다(사전등록 오염 방지, 계획서 §9 서두).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[2]
EVENTS = ROOT / "data" / "insider_events_mcap.csv"
TRADABLE = ROOT / "universe" / "microcap_tradable.txt"
OUT = ROOT / "data" / "events_addv.csv"

WINDOW = 30      # 거래일
CHUNK = 50       # yfinance 배치


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mcap-max", type=float, default=500e6,
                    help="이 시총 미만 이벤트만 대상 (기본 $500M — N #13 대안까지 커버)")
    ap.add_argument("--report-only", action="store_true",
                    help="이미 만든 events_addv.csv로 표만 다시 낸다 (yfinance 재수집 없음)")
    args = ap.parse_args()

    if args.report_only:
        done = pd.read_csv(OUT)
        _report_cuts(done[done.addv.notna()])
        return

    ev = pd.read_csv(EVENTS, parse_dates=["filing_date"])
    tradable = set(TRADABLE.read_text().split())
    uni = ev[ev.mcap_usd.notna() & ev.symbol.isin(tradable) & (ev.mcap_usd < args.mcap_max)]
    syms = sorted(uni.symbol.unique())
    print(f"대상 {len(syms)}종목 / {len(uni)}이벤트", flush=True)

    start = (uni.filing_date.min() - pd.Timedelta(days=90)).date()
    end = (uni.filing_date.max() + pd.Timedelta(days=5)).date()

    vols, closes = {}, {}
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
                v, c = raw[s]["Volume"].dropna(), raw[s]["Close"].dropna()
                if len(v) > 20:
                    vols[s], closes[s] = v, c
            except Exception:                                   # noqa: BLE001
                pass
        print(f"  {min(i + CHUNK, len(syms))}/{len(syms)}", flush=True)

    dv = (pd.DataFrame(vols) * pd.DataFrame(closes)).sort_index()
    dv = dv.rolling(WINDOW, min_periods=WINDOW // 2).mean()
    dv.index = pd.to_datetime(dv.index).tz_localize(None)

    # 이벤트별 = 공시일 이전 최신 관측 (미래 누수 방지)
    addv = []
    for r in uni.itertuples():
        if r.symbol not in dv.columns:
            addv.append(None); continue
        ser = dv[r.symbol].loc[:r.filing_date].dropna()
        addv.append(ser.iloc[-1] if len(ser) else None)

    out = uni.assign(addv=addv)[
        ["symbol", "cik", "filing_date", "mcap_usd", "mcap_source", "addv"]]
    out.to_csv(OUT, index=False)

    ok = out[out.addv.notna()]
    print(f"\n[완료] {OUT.relative_to(ROOT)} — 산출 {len(ok)}/{len(out)} ({len(ok)/len(out):.1%})",
          flush=True)
    print("\nADDV 분포: " + "  ".join(
        f"p{int(q*100)}=${ok.addv.quantile(q):,.0f}" for q in (.05, .1, .25, .5, .75, .9)))
    _report_cuts(ok)


def _report_cuts(ok: pd.DataFrame) -> None:
    """계획서 §3.14(2)(4) 표 — 하한별 잔존율과 시총 밴드 교차.

    이 두 표는 v3.3에서 임시 스크립트로 만들어져 유실됐다(E5 위반). 산출기에 붙여 재현 가능하게 둔다.
    """
    main = ok[ok.mcap_usd < 300e6]
    print(f"\n=== ADDV 하한별 잔존율 (분모 {len(main)} — `<$300M ∩ Toss ∩ ADDV 산출 성공`) ===")
    for lo in (50e3, 100e3, 200e3, 500e3, 1e6):
        sub = main[main.addv >= lo]
        print(f"  ${lo:>10,.0f}  {len(sub)/len(main):6.1%} ({len(sub):5d})  {sub.symbol.nunique():4d}종목")

    print(f"\n=== 시총 밴드 × ADDV 통과율 (분모 {len(main)}) ===")
    bands = [(0, 25e6, "<$25M"), (25e6, 50e6, "$25~50M"), (50e6, 100e6, "$50~100M"),
             (100e6, 200e6, "$100~200M"), (200e6, 300e6, "$200~300M")]
    for lo, hi, name in bands:
        b = main[(main.mcap_usd >= lo) & (main.mcap_usd < hi)]
        if b.empty:
            continue
        print(f"  {name:>10}  n={len(b):5d}  p50=${b.addv.median():>11,.0f}"
              f"  ≥$200k {(b.addv >= 200e3).mean():6.1%}  ≥$100k {(b.addv >= 100e3).mean():6.1%}")

    nano = main[main.mcap_usd < 50e6]
    nano_pass = nano[nano.addv >= 200e3]
    print(f"\nNANO(<$50M): {len(nano)}건 {len(nano)/len(main):.1%} "
          f"→ ADDV≥$200k 적용 후 {len(nano_pass)}건 "
          f"{len(nano_pass)/max(len(main[main.addv >= 200e3]), 1):.1%} (층화 보고 대상)")


if __name__ == "__main__":
    main()
