"""단계 2 검증 — 계획서 §5 단계 2(E9). 조인이 조용히 어긋나면 이후 전 결과가 무효다.

  (1) (발행사, FILING_DATE)로 접었을 때 거래행 대비 비율이 약 2.6배인가
  (2) 우리 이벤트 집합에 음수 공시지연이 0건인가 — 원자료 오기가 걸러졌는가
  (3) 스팟체크 — 직전 종가 간격·지연 범위·청산가 존재
  (4) AFF10B5ONE 부재 분기에서 필터가 실제로 꺼지는가

실행:  .venv/bin/python scripts/data_pipeline/verify_stage2.py
옵션:  --events data/insider_events_full.csv
"""
from __future__ import annotations

import sys

import argparse
import collections
import csv
from datetime import datetime

import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CANDIDATE_CLOSES_CSV, EVENTS_CSV

ROOT = Path(__file__).resolve().parents[2]
DERA = ROOT / "data" / "dera"
PRICES = CANDIDATE_CLOSES_CSV


def _rows(path: Path):
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        yield from csv.DictReader(f, delimiter="\t")


def _parse(v: str):
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    return None


def check_fold_and_leak(quarters: list[str]) -> tuple[bool, int]:
    """(1) 접기 비율, (2) 원자료 미래 누수 건수."""
    trans_rows = leak = 0
    pairs: set[tuple[str, str]] = set()
    for q in quarters:
        d = DERA / q
        sub = {r["ACCESSION_NUMBER"]: r for r in _rows(d / "SUBMISSION.tsv")}
        for r in _rows(d / "NONDERIV_TRANS.tsv"):
            if r.get("TRANS_CODE") != "P" or r.get("TRANS_ACQUIRED_DISP_CD") != "A":
                continue
            s = sub.get(r["ACCESSION_NUMBER"])
            if not s:
                continue
            trans_rows += 1
            fd, td = _parse(s["FILING_DATE"]), _parse(r.get("TRANS_DATE", ""))
            if fd and td and fd < td:
                leak += 1
            if fd:
                pairs.add((s["ISSUERCIK"], fd.date().isoformat()))

    ratio = trans_rows / len(pairs) if pairs else 0
    ok_fold = 2.0 <= ratio <= 3.2
    print(f"\n(1) 접기 비율 — 거래행 {trans_rows:,} / 이벤트 {len(pairs):,} = **{ratio:.2f}배**"
          f"  {'✅ (기대 약 2.6배)' if ok_fold else '❌ 접기가 동작하지 않는다'}")
    # 원자료의 오기 건수는 우리가 못 고친다 — 판정 대상은 **우리 이벤트 집합**이다.
    print(f"(2) 미래 누수 — DERA 원자료에 FILING_DATE < TRANS_DATE 인 거래행 {leak}건"
          " (원자료 오기, 아래에서 걸러졌는지 확인한다)")
    return ok_fold, leak


def check_events_leak(events: Path) -> bool:
    """(2) 산출된 이벤트 집합의 음수 공시지연 — 0건이어야 한다."""
    with open(events, newline="", encoding="utf-8") as f:
        lags = [int(r["filing_lag_days"]) for r in csv.DictReader(f)]
    neg = sum(1 for x in lags if x < 0)
    print(f"    → 이벤트 집합({events.name}) 음수 지연 **{neg}건** / {len(lags):,}"
          f"  {'✅ 전부 걸러짐' if neg == 0 else '❌ 필터가 음수를 통과시킨다'}")
    return neg == 0


def check_10b5_column(quarters: list[str]) -> bool:
    """(4) AFF10B5ONE 부재 분기에서 필터가 실제로 꺼지는가."""
    absent = []
    for q in quarters:
        with open(DERA / q / "SUBMISSION.tsv", encoding="utf-8", errors="replace") as f:
            header = f.readline().rstrip("\n").split("\t")
        if "AFF10B5ONE" not in header:
            absent.append(q)
    # 부재 분기에서 실제로 필터가 꺼지는가 — 값이 있는 분기에는 1(=10b5-1)이 존재해야 한다
    flagged = {}
    for q in quarters:
        vals = {r.get("AFF10B5ONE", "") for r in _rows(DERA / q / "SUBMISSION.tsv")}
        flagged[q] = "1" in vals
    present = [q for q in quarters if q not in absent]
    ok = all(not flagged[q] for q in absent) and any(flagged[q] for q in present)
    print(f"(4) `AFF10B5ONE` — 부재 {len(absent)}분기"
          f"{' (' + absent[0] + '~' + absent[-1] + ')' if absent else ''}"
          f" · 존재 {len(present)}분기 중 플래그 관측 {sum(flagged[q] for q in present)}분기"
          f"  {'✅' if ok else '❌ 부재 분기에서 플래그가 관측되거나 존재 분기에서 전무하다'}")
    return ok


def spot_check(events: Path, n: int = 5) -> bool:
    """(3) 이벤트 5건 스팟체크."""
    with open(events, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["symbol"]]
    if not PRICES.exists():
        print("(3) 스팟체크 — 가격 패널 없음, 생략")
        return False

    with open(PRICES, newline="", encoding="utf-8") as f:
        rdr = csv.reader(f)
        cols = next(rdr)
        panel = {c: {} for c in cols[1:]}
        for row in rdr:
            for c, v in zip(cols[1:], row[1:]):
                if v:
                    panel[c][row[0]] = float(v)

    # 패널은 주 표본(2023~) 것이라 2015년 이벤트의 "직전 종가 없음"은 조인 오류가 아니다.
    lo = min(d for c in panel.values() if c for d in c)
    hi = max(d for c in panel.values() if c for d in c)
    rows = [r for r in rows if lo <= r["filing_date"] <= hi]
    print(f"    (가격 패널 구간 {lo}~{hi} 안의 이벤트 {len(rows):,}건에서 추출)")

    freq = collections.Counter(r["symbol"] for r in rows)
    picked, seen = [], set()
    for r in rows:
        if r["symbol"] in seen or r["symbol"] not in panel or not panel[r["symbol"]]:
            continue
        if freq[r["symbol"]] < 3:
            continue
        seen.add(r["symbol"])
        picked.append(r)
        if len(picked) == n:
            break

    print("\n(3) 스팟체크 — 공시일 이전 최신 종가가 붙는지 (PIT 정렬)")
    ok = True
    for r in picked:
        fd = r["filing_date"]
        prior = [d for d in panel[r["symbol"]] if d <= fd]
        if not prior:
            print(f"    {r['symbol']:<6} {fd}  ❌ 공시일 이전 종가 없음")
            ok = False
            continue
        d = max(prior)
        after = [x for x in panel[r["symbol"]] if x > fd]
        # `d <= fd`는 prior 구성상 자명하므로 단언 대상이 아니다(정정 A-3).
        gap = (pd.Timestamp(fd) - pd.Timestamp(d)).days
        lag = int(r["filing_lag_days"])
        bad = []
        if gap > 7:                       # 직전 거래일이 일주일 넘게 떨어져 있으면 조인 의심
            bad.append(f"직전종가 간격 {gap}일")
        if not (0 <= lag <= 5):           # 사전등록 필터가 실제로 적용됐는가
            bad.append(f"지연 {lag}일이 [0,5] 밖")
        if len(after) < 30:               # H=30 청산가가 있는가
            bad.append(f"이후 관측 {len(after)}일 < 30")
        print(f"    {r['symbol']:<6} CIK {r['cik']:<9} {fd}  "
              f"직전종가 {d} ${panel[r['symbol']][d]:.2f} (간격 {gap}일)  "
              f"거래단가 ${float(r['max_price']):.2f}  지연 {lag}일  "
              f"이후 관측 {len(after)}일{'  ❌ ' + ', '.join(bad) if bad else ''}")
        if bad:
            ok = False
    print(f"    → {'✅ PIT 정렬·필터·청산가 모두 정상' if ok else '❌ 위 ❌ 항목 확인'}")
    return ok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", type=Path, default=EVENTS_CSV)
    ap.add_argument("--quarters", nargs="+", default=None,
                    help="검증할 분기 (기본: data/dera 아래 전부)")
    args = ap.parse_args()

    quarters = args.quarters or sorted(d.name for d in DERA.iterdir()
                                       if (d / "SUBMISSION.tsv").exists())
    print(f"검증 대상 분기 {len(quarters)}개: {quarters[0]} ~ {quarters[-1]}")

    ok_fold, _raw_leak = check_fold_and_leak(quarters)
    ok_leak = check_events_leak(args.events)
    flat = [ok_fold, ok_leak, check_10b5_column(quarters), spot_check(args.events)]
    print(f"\n{'🎉 단계 2 검증 통과' if all(flat) else '⚠️ 실패 항목 있음 — 위 ❌ 확인'}")


if __name__ == "__main__":
    main()
