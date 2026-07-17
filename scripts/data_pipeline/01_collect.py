"""Phase 2 · T3: yfinance로 유니버스 일봉 수집 → data/raw/<SYMBOL>.csv

개선9(yfinance 취약성 대응):
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
import time

import pandas as pd
import yfinance as yf

from _common import DATA_RAW, START_DATE, log, read_universe

MAX_RETRIES = 4
MIN_ROWS = 200  # 이보다 적으면 수집 실패로 간주(10년치면 수천 행이어야 정상)

# yfinance 원본 → 우리 스키마 컬럼명
_RENAME = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adjclose",
    "Volume": "volume",
}
_COLS = ["date", "open", "high", "low", "close", "adjclose", "volume", "symbol"]


def _download_one(symbol: str, start: str) -> pd.DataFrame | None:
    """한 종목 다운로드. 재시도+backoff. 성공 시 스키마 DataFrame, 실패 시 None."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            df = yf.download(
                symbol,
                start=start,
                auto_adjust=False,
                actions=False,
                progress=False,
                threads=False,
            )
        except Exception as e:  # 네트워크·스크래퍼 예외 광범위 → 재시도 대상
            log(f"   [{symbol}] 시도 {attempt}/{MAX_RETRIES} 예외: {e}")
            df = None

        if df is not None and not df.empty:
            # 최신 yfinance는 단일 티커도 MultiIndex 컬럼 반환 → 가격 레벨만 남김
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if "Adj Close" not in df.columns:
                log(f"   [{symbol}] 'Adj Close' 없음 — auto_adjust 확인 필요, 재시도")
            elif len(df) >= MIN_ROWS:
                df = df.rename(columns=_RENAME).reset_index()
                df = df.rename(columns={"Date": "date"})
                df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
                df["symbol"] = symbol
                return df[_COLS]
            else:
                log(f"   [{symbol}] 행 수 부족({len(df)}<{MIN_ROWS}), 재시도")

        if attempt < MAX_RETRIES:
            backoff = 2**attempt  # 2,4,8s
            time.sleep(backoff)
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="*", help="부분 수집할 심볼(생략 시 유니버스 전체)")
    ap.add_argument("--start", default=START_DATE)
    args = ap.parse_args()

    symbols = [s.upper() for s in args.symbols] if args.symbols else read_universe()
    DATA_RAW.mkdir(parents=True, exist_ok=True)

    log(f"📥 수집 시작: {len(symbols)}종목, start={args.start} → {DATA_RAW}")
    ok, kept_stale, failed = [], [], []

    for i, sym in enumerate(symbols, 1):
        log(f"[{i}/{len(symbols)}] {sym}")
        df = _download_one(sym, args.start)
        out_path = DATA_RAW / f"{sym}.csv"
        if df is not None:
            df.to_csv(out_path, index=False)
            log(f"   ✅ {len(df)}행 → {out_path.name}")
            ok.append(sym)
        elif out_path.exists():
            # 폴백: 직전 정상 CSV 유지(개선9)
            log(f"   ⚠️ 수집 실패 — 기존 {out_path.name} 유지(폴백)")
            kept_stale.append(sym)
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

    if not ok and not kept_stale:
        raise SystemExit("[치명] 사용 가능한 데이터가 하나도 없음")


if __name__ == "__main__":
    main()
