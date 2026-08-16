"""정규화 단계의 알맹이 — Qlib YahooNormalize1d 규약 포팅.

`normalize_one`은 DataFrame → DataFrame 순수 함수라 CSV 없이 테스트할 수 있다.
`01_collect.py`와 같은 이유로 로직을 번호 없는 모듈에 둔다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

_PRICE_COLS = ["open", "high", "low", "close"]
_OUT_COLS = ["date", "open", "high", "low", "close", "vwap", "volume", "factor", "symbol"]


def _fix_abnormal(df: pd.DataFrame) -> pd.DataFrame:
    """Yahoo 간헐 100배 글리치 보정(qlib normalize_yahoo와 동일 원리)."""
    for _ in range(10):
        prev = df["close"].ffill().shift(1)
        change = df["close"].ffill() / prev - 1
        mask = (change >= 89) & (change <= 111)
        if not mask.any():
            break
        for c in ["high", "close", "low", "open", "adjclose"]:
            df.loc[mask, c] = df.loc[mask, c] / 100
    return df


def normalize_one(df: pd.DataFrame) -> pd.DataFrame:
    symbol = df["symbol"].iloc[0]
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates("date").sort_values("date").set_index("date")

    # 2) 거래정지/결측: volume<=0 또는 NaN → 가격·거래량 NaN
    bad = (df["volume"] <= 0) | df["volume"].isna()
    df.loc[bad, ["open", "high", "low", "close", "adjclose", "volume"]] = np.nan

    # 3) 이상치 보정
    df = _fix_abnormal(df)

    # 4) 수정주가: factor = adjclose/close
    df["factor"] = (df["adjclose"] / df["close"]).ffill()
    for c in _PRICE_COLS:
        df[c] = df[c] * df["factor"]
    df["volume"] = df["volume"] / df["factor"]

    # 5) manual-adj: 첫 유효 close 기준 정규화
    fvi = df["close"].first_valid_index()
    if fvi is None:
        return pd.DataFrame(columns=_OUT_COLS)  # 전부 결측
    first_close = df.loc[fvi, "close"]
    for c in _PRICE_COLS + ["factor"]:
        df[c] = df[c] / first_close
    df["volume"] = df["volume"] * first_close

    # Alpha158이 참조하는 $vwap 프록시(yfinance 미제공): 조정·정규화된 (H+L+C)/3.
    # 이미 조정·정규화된 H/L/C에서 파생 → 같은 단위. lookahead 없음(당일값).
    df["vwap"] = (df["high"] + df["low"] + df["close"]) / 3

    df["symbol"] = symbol
    df = df.reset_index()
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    return df[_OUT_COLS]
