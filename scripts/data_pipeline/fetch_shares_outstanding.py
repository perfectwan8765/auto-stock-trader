"""PIT 발행주식수·유통시가총액 수집 (SEC XBRL) → data/shares_outstanding.csv

Toss `/api/v1/stocks`의 `sharesOutstanding`은 현재값이라 과거 이벤트 필터에 쓰면 승자 배제
편향이 생긴다. SEC XBRL companyconcept은 관측마다 `end`(기준일)과 `filed`(공시일)을 주므로,
`filed`로 잘라내면 PIT가 된다.

concept 폴백 체인 (40종목 표본 커버리지 실측):
  dei:EntityCommonStockSharesOutstanding   90%  분기(표지)   ← 1순위
  us-gaap:CommonStockSharesIssued          90%  분기
  us-gaap:CommonStockSharesOutstanding     80%  분기
  dei:EntityPublicFloat                   100%  연 1회(10-K) ← 별도 수집(유통시총, USD)

EntityPublicFloat는 주식수가 아니라 USD 유통시가총액이라 단위가 다르다. 연 1회 갱신이라
최대 12개월 stale이지만, 가격 조인이 필요 없어 폐지 종목의 유일한 시총 경로가 된다.

실행:  .venv/bin/python scripts/data_pipeline/fetch_shares_outstanding.py
옵션:  --limit 100   (상위 N종목만)
"""
from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANDIDATES_CSV = ROOT / "universe" / "microcap_candidates.csv"
OUT = ROOT / "data" / "shares_outstanding.csv"

UA = "qlib-toss research ax2team@didim.com"  # SEC는 이메일 포함 UA 요구(없으면 403)
RATE_SLEEP = 0.11   # EDGAR 10 req/s 준수
MAX_RETRIES = 4
BACKOFF_BASE = 0.5  # 지수 백오프 기준(초): 0.5 → 1 → 2

# 앞에서부터 시도해 값이 나오면 멈춘다.
SHARE_CONCEPTS = [
    ("dei", "EntityCommonStockSharesOutstanding"),
    ("us-gaap", "CommonStockSharesIssued"),
    ("us-gaap", "CommonStockSharesOutstanding"),
]
FLOAT_CONCEPT = ("dei", "EntityPublicFloat")


def _get_concept(cik: int, ns: str, concept: str) -> tuple[list[dict], str]:
    """concept 조회. Returns (rows, status) — status는 'ok' | 'missing' | 'error'.

    404(미보고)와 429/5xx/타임아웃(전송 실패)을 구분한다. 둘을 빈 리스트로 뭉개면 전송 실패가
    '미보고'로 둔갑해 하류에서 조용히 유니버스에서 탈락한다.

    실측(2026-08-09): 재시도 도입 후 전송실패 0건이고 커버리지도 그대로였다(82.2%).
    즉 미확보분은 진짜 미보고다. 구분 자체는 유지한다 — 없으면 다음에 실제 전송실패가 나도 모른다.
    """
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/{ns}/{concept}.json"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    body = None
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                body = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return [], "missing"  # 미보고 — 재시도 무의미
            if attempt == MAX_RETRIES - 1:
                return [], "error"
            time.sleep(BACKOFF_BASE * (2 ** attempt))
        except (urllib.error.URLError, ValueError, TimeoutError, OSError):
            if attempt == MAX_RETRIES - 1:
                return [], "error"
            time.sleep(BACKOFF_BASE * (2 ** attempt))
    if body is None:
        return [], "error"

    rows = []
    for unit, entries in (body.get("units") or {}).items():
        for e in entries:
            if e.get("val") is None or not e.get("end") or not e.get("filed"):
                continue
            rows.append({"end": e["end"], "filed": e["filed"], "val": e["val"],
                         "form": e.get("form", ""), "unit": unit})
    return rows, ("ok" if rows else "missing")


def _dedup_latest(rows: list[dict]) -> list[dict]:
    """같은 (end, filed)에 여러 값이 오면(복수 클래스 등) 최대값만 남긴다.

    복수 클래스 주식은 companyconcept가 클래스 축을 떨어뜨려 같은 키에 여러 값이 온다.
    합산하면 중복 위험이 있어 보수적으로 최대값을 쓴다 — 시총을 과대추정하는 방향이라
    '마이크로캡이 아닌데 마이크로캡으로 분류'되는 오류를 줄인다.
    """
    best: dict[tuple[str, str], dict] = {}
    for r in rows:
        k = (r["end"], r["filed"])
        if k not in best or r["val"] > best[k]["val"]:
            best[k] = r
    return sorted(best.values(), key=lambda x: (x["filed"], x["end"]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    if not CANDIDATES_CSV.exists():
        raise SystemExit(f"[오류] {CANDIDATES_CSV.relative_to(ROOT)} 없음 — gen_microcap_candidates.py 먼저 실행")
    rows = list(csv.DictReader(open(CANDIDATES_CSV, newline="", encoding="utf-8")))
    if args.limit is not None:  # `--limit 0`을 '제한 없음'으로 오해하지 않도록
        rows = rows[: args.limit]
    if not rows:
        raise SystemExit("[오류] 처리할 종목이 없음 — 후보 CSV가 비었거나 --limit 0")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    n_shares = n_float = n_none = n_err = 0
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "cik", "metric", "concept", "end", "filed", "val", "unit", "form"])
        for i, row in enumerate(rows, 1):
            symbol, cik = row["symbol"], int(row["cik"])

            got, had_error = [], False
            for ns, concept in SHARE_CONCEPTS:
                found, status = _get_concept(cik, ns, concept)
                time.sleep(RATE_SLEEP)
                had_error |= status == "error"
                got = _dedup_latest(found)
                if got:
                    for r in got:
                        w.writerow([symbol, cik, "shares", f"{ns}:{concept}",
                                    r["end"], r["filed"], r["val"], r["unit"], r["form"]])
                    n_shares += 1
                    break
            if not got:
                # 전송 실패는 '미보고'와 다르다. 하류가 구분할 수 있도록 별도 행으로 남긴다.
                w.writerow([symbol, cik, "error" if had_error else "missing", "shares", "", "", "", "", ""])
                n_err += had_error
                n_none += not had_error

            found, status = _get_concept(cik, *FLOAT_CONCEPT)
            time.sleep(RATE_SLEEP)
            fl = _dedup_latest(found)
            if fl:
                for r in fl:
                    w.writerow([symbol, cik, "public_float", f"{FLOAT_CONCEPT[0]}:{FLOAT_CONCEPT[1]}",
                                r["end"], r["filed"], r["val"], r["unit"], r["form"]])
                n_float += 1
            elif status == "error":
                w.writerow([symbol, cik, "error", "public_float", "", "", "", "", ""])

            if i % 100 == 0:
                print(f"  ...{i}/{len(rows)}  주식수 {n_shares}  float {n_float}  "
                      f"미보고 {n_none}  전송실패 {n_err}")

    n = len(rows)
    print(f"\n종목 {n:,} → 주식수 확보 {n_shares:,} ({100*n_shares/n:.1f}%) · "
          f"public_float {n_float:,} ({100*n_float/n:.1f}%)")
    print(f"주식수 미확보 {n - n_shares:,} 중 — 미보고(404/빈값) {n_none:,} · **전송실패 {n_err:,}**")
    if n_err:
        print("  ⚠️ 전송실패는 재실행하면 회수될 수 있다. metric='error' 행으로 기록됨.")
    print(f"[완료] {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
