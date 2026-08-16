"""수집 단계의 알맹이 — yfinance 다운로드와 리포트 산출.

번호 붙은 파일명(`01_collect.py`)은 Python 식별자가 아니라 import할 수 없어 단위 테스트가
불가능하다. 로직을 여기 두고 그 파일은 CLI 껍데기로 남긴다.
"""
from __future__ import annotations

import time

import pandas as pd
import yfinance as yf

from _common import log

MAX_RETRIES = 4
MIN_ROWS = 200  # 10년치면 수천 행이 정상 — 이보다 적으면 수집 실패로 본다

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


def download_one(symbol: str, start: str) -> pd.DataFrame | None:
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


def last_date_of(path) -> str | None:
    """폴백으로 유지된 CSV의 마지막 날짜 — stale 판정의 근거값."""
    try:
        return str(pd.read_csv(path, usecols=["date"])["date"].iloc[-1])[:10]
    except (OSError, ValueError, KeyError, IndexError):
        return None
