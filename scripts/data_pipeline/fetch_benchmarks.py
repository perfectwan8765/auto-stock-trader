"""벤치마크 ETF + Ken French 팩터 수집 — 계획서 §5 단계 1(i), E8.

마이크로캡을 SPY에만 회귀하면 size premium이 통째로 alpha로 잡힌다(D9·D15).

산출: data/benchmarks.csv (IWM·IWC·IJS·SPY) · data/ff_factors.csv (FF5 + MOM, 일별 소수)
실행:  .venv/bin/python scripts/data_pipeline/fetch_benchmarks.py
"""
from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[2]
OUT_BENCH = ROOT / "data" / "benchmarks.csv"
OUT_FF = ROOT / "data" / "ff_factors.csv"

TICKERS = ["IWM", "IWC", "IJS", "SPY"]
START = "2015-01-01"

FF_BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{}"
FF_FILES = {
    "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip": ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"],
    "F-F_Momentum_Factor_daily_CSV.zip": ["Mom"],
}


def fetch_benchmarks() -> None:
    raw = yf.download(TICKERS, start=START, progress=False, auto_adjust=True)["Close"]
    raw.index = pd.to_datetime(raw.index).tz_localize(None)
    raw.to_csv(OUT_BENCH)
    print(f"[완료] {OUT_BENCH.relative_to(ROOT)} — {len(raw)}일 × {raw.shape[1]}종목 "
          f"({raw.index.min().date()}~{raw.index.max().date()})")
    print("  결측: " + "  ".join(f"{c} {raw[c].isna().sum()}" for c in raw.columns))


def _read_ff(fname: str, cols: list[str]) -> pd.DataFrame:
    """Ken French zip은 헤더 주석과 꼬리(연간 요약)가 붙어 있어 날짜 8자리 행만 남긴다."""
    req = urllib.request.Request(FF_BASE.format(fname), headers={"User-Agent": "qlib-toss research"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        zf = zipfile.ZipFile(io.BytesIO(resp.read()))
        text = zf.read(zf.namelist()[0]).decode("latin-1")
    rows = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == len(cols) + 1 and parts[0].isdigit() and len(parts[0]) == 8:
            rows.append([parts[0]] + [float(v) for v in parts[1:]])
    df = pd.DataFrame(rows, columns=["Date"] + cols)
    df["Date"] = pd.to_datetime(df.Date, format="%Y%m%d")
    return df.set_index("Date") / 100.0        # 원자료는 퍼센트


def fetch_ff() -> None:
    parts = [_read_ff(f, c) for f, c in FF_FILES.items()]
    ff = pd.concat(parts, axis=1).dropna().rename(columns={"Mom": "MOM"})
    ff = ff[ff.index >= START]
    ff.to_csv(OUT_FF)
    print(f"\n[완료] {OUT_FF.relative_to(ROOT)} — {len(ff)}일 × {ff.shape[1]}팩터 "
          f"({ff.index.min().date()}~{ff.index.max().date()})")
    print("  연환산 평균: " + "  ".join(f"{c} {ff[c].mean()*252:+.1%}" for c in ff.columns))


if __name__ == "__main__":
    fetch_benchmarks()
    fetch_ff()
