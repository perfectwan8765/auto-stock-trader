"""Phase 2 · T4: raw CSV 정규화 → data/normalized/<SYMBOL>.csv

Qlib YahooNormalize1d(v0.9.7) 로직을 충실히 포팅. 손으로 구현하되 규약을 정확히 맞춰
Phase 3의 Alpha158·백테스트가 qlib 표준 데이터와 동일하게 동작하도록 한다.

단계(종목별):
  1) 날짜 인덱스 정렬·중복 제거
  2) volume<=0/NaN 행 → 전 컬럼 NaN (결측 유지, ffill 금지)
  3) [robustness] 연속일 배수 89~111 이상치(Yahoo 100배 글리치) → /100 보정
  4) factor = adjclose/close (ffill).  OHLC *= factor(수정주가), volume /= factor
  5) manual-adj: 첫 유효 close로 정규화(첫날≈1.0). raw가 복원 = $close/$factor
  6) vwap 프록시 = (H+L+C)/3 (Alpha158이 $vwap 참조, yfinance 미제공)
출력 컬럼: date, open, high, low, close, vwap, volume, factor, symbol

실행:  .venv/bin/python scripts/data_pipeline/02_normalize.py
"""
from __future__ import annotations

import pandas as pd

from _common import write_csv_atomic, DATA_NORM, DATA_RAW, log
from normalize import normalize_one

def main() -> None:
    if not DATA_RAW.exists():
        raise SystemExit(f"[오류] raw 데이터 없음: {DATA_RAW} (먼저 01_collect.py 실행)")
    raw_files = sorted(DATA_RAW.glob("*.csv"))
    if not raw_files:
        raise SystemExit(f"[오류] raw CSV 0개: {DATA_RAW}")

    DATA_NORM.mkdir(parents=True, exist_ok=True)
    log(f"🔧 정규화 시작: {len(raw_files)}개 → {DATA_NORM}")

    ok, skipped = 0, []
    for fp in raw_files:
        df = pd.read_csv(fp)
        out = normalize_one(df)
        if out.empty:
            log(f"   ⚠️ {fp.stem}: 유효 데이터 없음, 건너뜀")
            skipped.append(fp.stem)
            continue
        write_csv_atomic(out, DATA_NORM / fp.name, index=False)
        ok += 1

    log(f"\n정규화 요약: 성공 {ok} · 건너뜀 {len(skipped)}")
    if skipped:
        log(f"  건너뜀: {', '.join(skipped)}")
    if ok == 0:
        raise SystemExit("[치명] 정규화 산출물 0개")


if __name__ == "__main__":
    main()
