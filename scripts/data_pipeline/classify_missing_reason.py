"""가격이 사라진 종목의 소멸 사유 분류 (EDGAR) → data/missing_reason.csv

생존편향 보정의 입력이다. yfinance는 폐지 티커의 이력을 통째로 지우므로, 결측 종목을
'전부 파산'으로 가정하면 경계가 무의미해진다. 실제로는 반대에 가깝다 —
200종목 표본 실측: **피인수 70.5% / 파산 10.5% / 미상 19%**.
즉 결측을 버리는 것은 인수 프리미엄을 버리는 것이라 수익을 과소추정한다.

판별 근거(전부 무료):
  파산     8-K Item 1.03 (Bankruptcy or Receivership)
  피인수   DEFM14A · PREM14A · SC 14D9   ← **대상회사만 제출**하므로 확실 근거
  상폐     Form 25 · 25-NSE · Form 15
⚠️ S-4·SC TO-T·8-K Item 2.01은 **인수하는 쪽도 제출**한다. 확실 근거로 쓰면 피인수가
   부풀려진다(느슨한 기준 85% vs 엄격 기준 70.5%). 약한 근거로만 쓴다.

실행:  .venv/bin/python scripts/data_pipeline/classify_missing_reason.py
옵션:  --limit 200   (표본만)
"""
from __future__ import annotations

import sys

import argparse
import collections
import csv
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CANDIDATE_CLOSES_CSV  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CANDIDATES_CSV = ROOT / "universe" / "microcap_candidates.csv"
PRICES = CANDIDATE_CLOSES_CSV
OUT = ROOT / "data" / "missing_reason.csv"

UA = "qlib-toss research ax2team@didim.com"
RATE_SLEEP = 0.11

TARGET_ONLY = {"DEFM14A", "PREM14A", "SC 14D9", "SC 14D-9"}   # 피인수 대상회사만 제출
ACQUIRER_TOO = {"S-4", "SC TO-T", "DEFA14A"}                  # 인수자도 제출 → 약한 근거
DELIST_FORMS = {"25", "25-NSE", "15-12B", "15-12G", "15F-12B", "15F-12G"}


def _submissions(cik: int) -> dict | None:
    url = f"https://data.sec.gov/submissions/CIK{cik:010d}.json"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
            return json.load(r)
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError, TimeoutError, OSError):
        return None


def classify(body: dict) -> tuple[str, str]:
    """(사유, 마지막 공시일). 조회 실패는 호출부에서 처리."""
    recent = (body.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    items = recent.get("items") or []
    dates = recent.get("filingDate") or []
    n = min(len(items), len(forms))

    bankrupt = any(forms[k] == "8-K" and "1.03" in (items[k] or "") for k in range(n))
    fset = set(forms)
    target = bool(fset & TARGET_ONLY)
    weak = bool(fset & ACQUIRER_TOO) or any(
        forms[k] == "8-K" and "2.01" in (items[k] or "") for k in range(n))
    delisted = bool(fset & DELIST_FORMS)

    if bankrupt:
        reason = "파산"
    elif target:
        reason = "피인수"
    elif weak and delisted:
        reason = "피인수(약한근거)"
    elif delisted:
        reason = "상폐(사유불명)"
    else:
        reason = "미상"
    return reason, (max(dates) if dates else "")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    if not PRICES.exists():
        raise SystemExit(f"[오류] {PRICES.relative_to(ROOT)} 없음 — gen_universe_by_mcap.py 먼저 실행")
    have_price = set(pd.read_csv(PRICES, index_col=0, nrows=1).columns)

    seen: set[str] = set()
    targets: list[tuple[str, str]] = []
    for r in csv.DictReader(open(CANDIDATES_CSV, newline="", encoding="utf-8")):
        if r["symbol"] in have_price or r["symbol"] in seen:
            continue
        seen.add(r["symbol"])
        targets.append((r["symbol"], r["cik"]))
    if args.limit is not None:
        targets = targets[: args.limit]
    if not targets:
        raise SystemExit("[오류] 분류할 결측 종목이 없음")

    print(f"가격 결측 {len(targets):,}종목 분류 시작")
    counts: collections.Counter = collections.Counter()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "cik", "reason", "last_filing"])
        for i, (symbol, cik) in enumerate(targets, 1):
            body = _submissions(int(cik))
            time.sleep(RATE_SLEEP)
            reason, last = ("조회실패", "") if body is None else classify(body)
            counts[reason] += 1
            w.writerow([symbol, cik, reason, last])
            if i % 100 == 0:
                print(f"  ...{i}/{len(targets)}")

    total = sum(counts.values())
    print(f"\n{'사유':20s} {'건수':>6s} {'비율':>7s}")
    for reason, n in counts.most_common():
        print(f"{reason:20s} {n:6,} {100*n/total:6.1f}%")
    print(f"\n[완료] {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
