"""단계 3 입력 패널 구성 — 판정 모집단 · 가격 · 팩터.

사전등록 §9 A-2가 확정한 정의를 코드로 옮긴 것이다. 이벤트스터디 본체(`run_event_study.py`)가
이 모듈을 통해서만 데이터를 받으므로, 모집단 정의가 한 곳에만 존재한다.

판정 모집단
    필터 통과 ∩ PIT 시총 <$300M ∩ ADDV >= $200k
    ∩ Toss 취급 ∩ (status == ACTIVE  OR  filing_date < delistDate)
  관측 = 가격 있는 것 · 결측 = 가격 없는 것(전량 계상, h 경계로 처리)

가격
    data/normalized_small/*.csv — `data/qlib_us_small` 번들의 **입력 파일**이다
    (03_dump_bin.py가 이 디렉터리를 읽어 .bin을 만든다). 같은 데이터이며 여기서는
    qlib provider를 거치지 않고 직접 읽는다.
    OHLC는 `factor = adjclose/close`가 곱해져 있어 **배당·분할 조정**된 값이다(02_normalize.py).
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
    """유니버스 파일 파서 — 주석(`#`)·빈 줄을 제외한다.

    `read_text().split()`로 읽으면 헤더 주석의 단어가 전부 티커로 들어온다. 지금은 우연히
    실제 티커와 충돌하지 않지만, 헤더에 대문자 단어 하나만 추가돼도 유령 심볼이 생긴다.
    """
    return {t for line in path.read_text().splitlines()
            if (t := line.strip().upper()) and not t.startswith("#")}


def judged_population() -> tuple[pd.DataFrame, pd.DataFrame]:
    """(관측 이벤트, 결측 이벤트) — 사전등록 §9 A-2 (1)의 모집단 정의."""
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
    """종목별 OHLC (배당·분할 조정).

    ⚠️ 거래정지일(02_normalize가 전 컬럼 NaN으로 둔 행)은 **여기서 제거**된다. 따라서
    인덱스는 실제 거래일만의 압축 목록이고, "H거래일 보유"가 달력일로는 더 길 수 있다.
    실측: 진입~청산 달력일 p50 43일 · p99 48일 · 50일 초과 2건(0.1%)이라 영향은 무시할 수준이다.
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
    """CIK → SIC 2자리 (섹터 통제용. 현재 값이라 PIT 아님 — §9 A-2 (3))."""
    s = pd.read_csv(SIC)
    s["sic2"] = s.sic.astype(str).str.zfill(4).str[:2]
    return s.set_index("cik").sic2
