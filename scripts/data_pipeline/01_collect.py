"""Phase 2 · T3: yfinance로 유니버스 일봉 수집 → data/raw/<SYMBOL>.csv

yfinance 취약성 대응:
  - 심볼당 재시도 + 지수 backoff
  - 지속 실패 시 직전 정상 CSV 폴백(있으면 유지, 없으면 실패 리포트)
  - 실패 심볼 요약 출력

auto_adjust=False 로 raw close와 adjclose를 함께 받는다(정규화에서 factor 계산에 필요).
결측/거래정지일은 여기서 채우지 않는다(ffill 금지) — 정규화·dump 단계에서 NaN 유지.

실행:  .venv/bin/python scripts/data_pipeline/01_collect.py
옵션:  --symbols AAPL MSFT (부분 수집)  --start 2015-01-01
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone

from _common import write_csv_atomic, COLLECT_REPORT, DATA_RAW, START_DATE, log, read_universe
from collect import download_one, last_date_of

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="*", help="부분 수집할 심볼(생략 시 유니버스 전체)")
    ap.add_argument("--start", default=START_DATE)
    args = ap.parse_args()

    symbols = [s.upper() for s in args.symbols] if args.symbols else read_universe()
    DATA_RAW.mkdir(parents=True, exist_ok=True)

    log(f"📥 수집 시작: {len(symbols)}종목, start={args.start} → {DATA_RAW}")
    ok, kept_stale, failed = [], [], []

    report: dict[str, dict] = {}

    for i, sym in enumerate(symbols, 1):
        log(f"[{i}/{len(symbols)}] {sym}")
        df = download_one(sym, args.start)
        out_path = DATA_RAW / f"{sym}.csv"
        if df is not None:
            write_csv_atomic(df, out_path, index=False)
            log(f"   ✅ {len(df)}행 → {out_path.name}")
            ok.append(sym)
            report[sym] = {"last_date": str(df["date"].iloc[-1])[:10], "stale": False}
        elif out_path.exists():
            # 폴백: 직전 정상 CSV 유지
            log(f"   ⚠️ 수집 실패 — 기존 {out_path.name} 유지(폴백)")
            kept_stale.append(sym)
            report[sym] = {"last_date": last_date_of(out_path), "stale": True}
        else:
            log(f"   ❌ 수집 실패, 폴백 없음")
            failed.append(sym)
        time.sleep(0.5)  # 심볼 간 간격(스크래퍼 배려)

    log("\n" + "=" * 50)
    log(f"수집 요약: 성공 {len(ok)} · 폴백유지 {len(kept_stale)} · 실패 {len(failed)}")
    if kept_stale:
        log(f"  폴백유지(직전 데이터): {', '.join(kept_stale)}")
    if failed:
        log(f"  실패(데이터 없음):    {', '.join(failed)}")

    # 폴백 사실을 파일로 남긴다 — 로그만으로는 하류(02·03·04)가 알 수 없다
    write_text_atomic(COLLECT_REPORT, json.dumps(
        {"collected_at": datetime.now(timezone.utc).isoformat(), "symbols": report},
        indent=2, ensure_ascii=False))
    log(f"수집 리포트: {COLLECT_REPORT.name} ({len(report)}종목)")

    if not ok and not kept_stale:
        raise SystemExit("[치명] 사용 가능한 데이터가 하나도 없음")


if __name__ == "__main__":
    main()
