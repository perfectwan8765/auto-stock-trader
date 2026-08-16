"""발행사 SIC 수집 — 계획서 §5 단계 2, D9 섹터 통제용. 산출: data/issuer_sic.csv

⚠️ **PIT 아니다.** EDGAR submissions API는 현재 SIC를 준다. 공시 시점 값은 각 파일링의 SGML
헤더에 있으나 accession 단위라 요청이 수만 건이 된다. 섹터 통제용 근사로만 쓸 것.

실행:  .venv/bin/python scripts/data_pipeline/fetch_sic.py
옵션:  --events data/insider_events.csv (기본) — 이 파일의 CIK만 조회
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
OUT = ROOT / "data" / "issuer_sic.csv"

UA = "qlib-toss research ax2team@didim.com"      # SEC는 이메일 포함 UA 필수(없으면 403)
URL = "https://data.sec.gov/submissions/CIK{:010d}.json"
RATE_SLEEP = 0.11                                 # EDGAR 10 req/s


def read_ciks(events: Path) -> list[int]:
    with open(events, newline="", encoding="utf-8") as f:
        ciks = {int(r["cik"]) for r in csv.DictReader(f) if r.get("cik", "").strip().isdigit()}
    return sorted(ciks)


def fetch(cik: int) -> dict | None:
    req = urllib.request.Request(URL.format(cik), headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            d = json.loads(resp.read())
    # JSONDecodeError(ValueError)·IncompleteRead(OSError)까지 — 자매 구현과 같은 범위
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
        return None
    return {"cik": cik, "sic": d.get("sic", ""), "sic_description": d.get("sicDescription", ""),
            "entity_name": d.get("name", "")}


def _write(rows: list[dict]) -> None:
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["cik", "sic", "sic_description", "entity_name"])
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", type=Path, default=ROOT / "data" / "insider_events.csv")
    args = ap.parse_args()

    ciks = read_ciks(args.events)
    if not ciks:
        raise SystemExit(f"[오류] {args.events}에 파싱 가능한 CIK가 없다")
    print(f"CIK {len(ciks):,}건 조회 (약 {len(ciks) * RATE_SLEEP / 60:.0f}분)", flush=True)

    rows, missing = [], 0
    for i, cik in enumerate(ciks, 1):
        rec = fetch(cik)
        if rec and rec["sic"]:
            rows.append(rec)
        else:
            missing += 1
        time.sleep(RATE_SLEEP)
        if i % 250 == 0:
            _write(rows)        # 수천 건 루프라 중간에 죽어도 받은 것은 남긴다
            print(f"  {i}/{len(ciks)}  확보 {len(rows)}  미확보 {missing}", flush=True)

    _write(rows)
    print(f"\n[완료] {OUT.relative_to(ROOT)} — {len(rows)}/{len(ciks)} ({len(rows)/max(len(ciks), 1):.1%})")
    top = {}
    for r in rows:
        top[r["sic_description"]] = top.get(r["sic_description"], 0) + 1
    print("  상위 섹터: " + " · ".join(
        f"{k or '(없음)'} {v}" for k, v in sorted(top.items(), key=lambda x: -x[1])[:6]))


if __name__ == "__main__":
    main()
