"""결측 티커의 '퇴출 시점'이 보유기간 안에 들어오는지 측정.

작업계획서 §5 단계 1(d) · §3.14(1). D13의 결측 경계와 kill(2) 판정의 입력이다.

왜 이걸 재나 — 결측을 "피인수 +25% / 파산 −55%"로 가르는 이전 방식은 **종국적 운명**을
**보유기간 수익률**의 경계로 쓴 것이었다. 그런데 인수 공시는 매수 공시로부터 p50 562일 뒤에 온다.
보유기간(30~90일) 안에 실제로 퇴출된 이벤트만이 파국 가정을 부과할 근거가 된다.

산출: data/exit_timing.csv        (티커별 폐지·파산·인수·마지막 공시일)
      data/exit_timing_events.csv (이벤트별 각 신호까지의 간격 일수)

구조 통계만 만든다 — 수익률은 계산하지 않는다(사전등록 오염 방지, 계획서 §9 서두).
"""
from __future__ import annotations

import sys

import argparse
import json
import time
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CANDIDATES_CSV, CANDIDATE_CLOSES_CSV, EVENTS_CSV, write_csv_atomic

ROOT = Path(__file__).resolve().parents[2]
CANDIDATES = CANDIDATES_CSV
PRICES = CANDIDATE_CLOSES_CSV
EVENTS = EVENTS_CSV
OUT_TICKER = ROOT / "data" / "exit_timing.csv"
OUT_EVENT = ROOT / "data" / "exit_timing_events.csv"

UA = "qlib-toss research ax2team@didim.com"   # SEC는 이메일 포함 UA 요구(없으면 403)
SLEEP = 0.11                                  # EDGAR 10 req/s

DELIST = {"25", "25-NSE"}
# 대상회사만 제출 → 피인수 확실 근거. S-4·8-K 2.01은 인수자도 제출하므로 제외(§3.11.1~3)
ACQ_STRONG = {"DEFM14A", "PREM14A", "SC 14D9", "SC 14D-9"}


def _submissions(cik: str) -> dict | None:
    url = f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except Exception:                                          # noqa: BLE001
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizons", type=int, nargs="+", default=[30, 60, 90],
                    help="보유기간(일). kill 판정은 최장값으로 한다")
    args = ap.parse_args()

    cand = pd.read_csv(CANDIDATES, dtype={"cik": str})
    have_price = set(pd.read_csv(PRICES, nrows=1).columns) - {"Date"}
    missing = cand[~cand.symbol.isin(have_price)]
    print(f"후보 {len(cand)} / 가격 보유 {len(have_price)} / **결측 {len(missing)}**", flush=True)

    ev = pd.read_csv(EVENTS, parse_dates=["filing_date"])
    ev_by_sym = {s: list(g.filing_date) for s, g in ev.groupby("symbol")}

    rows = []
    for i, r in enumerate(missing.itertuples(), 1):
        body = _submissions(r.cik)
        time.sleep(SLEEP)
        if i % 100 == 0:
            print(f"  {i}/{len(missing)}", flush=True)
        if not body:
            continue
        rec = (body.get("filings") or {}).get("recent") or {}
        forms, dates = rec.get("form") or [], rec.get("filingDate") or []
        items = rec.get("items") or [""] * len(forms)
        n = min(len(forms), len(dates))
        dl = sorted(dates[k] for k in range(n) if forms[k] in DELIST)
        bk = sorted(dates[k] for k in range(n) if forms[k] == "8-K"
                    and "1.03" in ((items[k] if k < len(items) else "") or ""))
        aq = sorted(dates[k] for k in range(n) if forms[k] in ACQ_STRONG)
        rows.append({"symbol": r.symbol, "cik": r.cik,
                     "delist_first": dl[0] if dl else "",
                     "bankrupt_first": bk[0] if bk else "",
                     "acq_first": aq[0] if aq else "",
                     "last_filing": max(dates) if dates else ""})

    t = pd.DataFrame(rows)
    write_csv_atomic(t, OUT_TICKER, index=False)
    print(f"\n조회 성공 {len(t)} — 폐지 {(t.delist_first != '').sum()} · "
          f"파산 {(t.bankrupt_first != '').sum()} · 인수 {(t.acq_first != '').sum()}", flush=True)

    recs = []
    for r in t.itertuples():
        for f in ev_by_sym.get(r.symbol, []):
            d = {"symbol": r.symbol, "filing_date": f}
            for key, col in [("delist", r.delist_first), ("bankrupt", r.bankrupt_first),
                             ("acq", r.acq_first), ("last", r.last_filing)]:
                d[f"{key}_gap"] = (pd.Timestamp(col) - f).days if col else None
            recs.append(d)
    g = pd.DataFrame(recs)
    write_csv_atomic(g, OUT_EVENT, index=False)
    print(f"결측 이벤트 {len(g)}\n")

    print("=== 퇴출 시점이 보유기간 안에 들어오는 비율 (분모는 각 신호 보유 이벤트) ===")
    hdr = "".join(f"{f'≤{h}일':>9}" for h in args.horizons)
    print(f"{'신호':>16} {'n':>6}{hdr}{'p50':>9}")
    for lbl, col in [("인수(강한근거)", "acq_gap"), ("폐지 Form25", "delist_gap"),
                     ("파산 8-K 1.03", "bankrupt_gap"), ("마지막 공시", "last_gap")]:
        v = g[col].dropna()
        v = v[v >= 0]
        line = f"{lbl:>16} {len(v):>6}"
        for h in args.horizons:
            line += f"{(v <= h).mean() * 100:>8.1f}%" if len(v) else f"{'-':>9}"
        line += f"{v.quantile(.5):>8.0f}일" if len(v) else f"{'-':>9}"
        print(line)

    H = max(args.horizons)
    alive = g[((g.delist_gap.isna()) | (g.delist_gap > H) | (g.delist_gap < 0))
              & ((g.bankrupt_gap.isna()) | (g.bankrupt_gap > H) | (g.bankrupt_gap < 0))]
    exit_rate = 1 - len(alive) / len(g)
    print(f"\n★ kill(2) 입력 — 보유기간 H={H}일 안에 퇴출 신호가 있는 결측 이벤트 비율: "
          f"**{exit_rate:.1%}** ({len(g) - len(alive)}/{len(g)})")
    print(f"  → 사전등록 임계 15% 대비 {'통과' if exit_rate <= 0.15 else '★KILL★'}")
    print(f"\n[완료] {OUT_TICKER.relative_to(ROOT)} · {OUT_EVENT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
