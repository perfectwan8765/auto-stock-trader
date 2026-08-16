"""단계 3 입력 패널 — 판정 모집단·가격·팩터. 모집단 정의는 사전등록 §9 A-2.

가격은 `data/normalized_small/*.csv`를 직접 읽는다. `data/qlib_us_small` 번들의 입력 파일이라
같은 데이터이며(03_dump_bin.py), OHLC에 `factor = adjclose/close`가 곱해져 배당·분할 조정돼 있다.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
NORM = ROOT / "data" / "normalized_small"
SPREAD = ROOT / "data" / "events_spread.csv"
TOSS_META = ROOT / "data" / "toss_stock_meta.csv"
TRADABLE = ROOT / "universe" / "microcap_tradable.txt"
EVENTS_MCAP = ROOT / "data" / "insider_events_mcap.csv"
FF = ROOT / "data" / "ff_factors.csv"
BENCH = ROOT / "data" / "benchmarks.csv"
SIC = ROOT / "data" / "issuer_sic.csv"

MCAP_MAX = 300e6
ADDV_MIN = 200e3


def read_symbols(path: Path) -> set[str]:
    """유니버스 파일 파서. `split()`만 쓰면 헤더 주석의 단어가 티커로 섞인다."""
    return {t for line in path.read_text().splitlines()
            if (t := line.strip().upper()) and not t.startswith("#")}


def judged_population() -> tuple[pd.DataFrame, pd.DataFrame]:
    """(관측 이벤트, 결측 이벤트). 사전등록 §9 A-2(1)."""
    obs = pd.read_csv(SPREAD, parse_dates=["filing_date"])
    obs = obs[(obs.mcap_usd < MCAP_MAX) & (obs.addv >= ADDV_MIN)].copy()

    # 결측 = 폐지 배제로 사라졌지만 공시 시점엔 거래 가능했던 이벤트
    meta = pd.read_csv(TOSS_META).drop_duplicates("symbol")
    dl = meta[meta.status == "DELISTED"].dropna(subset=["delistDate"]).copy()
    dl["delistDate"] = pd.to_datetime(dl.delistDate, errors="coerce", utc=True).dt.tz_localize(None)

    ev = pd.read_csv(EVENTS_MCAP, parse_dates=["filing_date"])
    tradable = read_symbols(TRADABLE)
    dropped = ev[ev.symbol.isin(set(dl.symbol)) & ~ev.symbol.isin(tradable)]
    dropped = dropped.merge(dl[["symbol", "delistDate"]], on="symbol", how="left")
    miss = dropped[(dropped.mcap_usd < MCAP_MAX) & (dropped.filing_date < dropped.delistDate)]
    return obs, miss


def load_prices() -> dict[str, pd.DataFrame]:
    """종목별 OHLC. 거래정지일이 제거되므로 인덱스는 실제 거래일만의 압축 목록이다 —
    "H거래일 보유"가 달력일로는 더 길어질 수 있다(실측 p99 48일 vs 정상 43일).
    """
    out = {}
    for f in NORM.glob("*.csv"):
        df = pd.read_csv(f, parse_dates=["date"]).set_index("date")
        df = df[["open", "close"]].dropna()
        if len(df) > 120:
            out[f.stem.upper()] = df
    return out


def load_factors() -> pd.DataFrame:
    """FF5 + MOM + IWC 초과수익 + rf. 일별, 소수 단위."""
    ff = pd.read_csv(FF, index_col=0, parse_dates=True)
    bench = pd.read_csv(BENCH, index_col=0, parse_dates=True)
    iwc = bench["IWC"].pct_change()
    df = ff.join(iwc.rename("IWC_raw"), how="inner")
    df["IWC"] = df.IWC_raw - df.RF          # 초과수익으로 맞춘다 (D15)
    return df.drop(columns=["IWC_raw"]).dropna()


def load_sic() -> pd.Series:
    """CIK → SIC 2자리. 현재 값이라 PIT 아니다(§9 A-2(3))."""
    s = pd.read_csv(SIC)
    s["sic2"] = s.sic.astype(str).str.zfill(4).str[:2]
    return s.set_index("cik").sic2
