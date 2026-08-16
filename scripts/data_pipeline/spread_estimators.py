"""Corwin-Schultz(2012)·Abdi-Ranaldo(2017) 스프레드 추정량 — EDGE 대조용(계획서 §3.12(3)).

둘 다 일봉 고저만 쓰고 상대 스프레드(0.01 = 1%)를 돌려준다. **부호를 지우지 않는다** —
음수 추정 비율 자체가 추정량 품질의 판정 재료다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def corwin_schultz(high: pd.Series, low: pd.Series, window: int) -> pd.Series:
    """CS(2012) 상대 스프레드. 인접 2일 고저 범위를 쓰므로 결과는 창 평균."""
    h, l = np.log(high), np.log(low)
    beta = ((h - l) ** 2).rolling(2).sum()
    gamma = (np.maximum(high, high.shift(1)) / np.minimum(low, low.shift(1))).pipe(np.log) ** 2

    k = 3 - 2 * np.sqrt(2)
    alpha = (np.sqrt(2 * beta) - np.sqrt(beta)) / k - np.sqrt(gamma / k)
    s = 2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha))
    return s.rolling(window).mean()


def abdi_ranaldo(high: pd.Series, low: pd.Series, close: pd.Series, window: int) -> pd.Series:
    """AR(2017) 상대 스프레드. eta = (log high + log low)/2 기준."""
    eta = (np.log(high) + np.log(low)) / 2
    c = np.log(close)
    s2 = 4 * ((c - eta) * (c - eta.shift(-1))).rolling(window).mean()
    est = np.sign(s2) * np.sqrt(np.abs(s2))
    # 창의 마지막 항이 eta_{t+1}이라 날짜 t의 값에 t+1의 고저가 들어 있다. as-of 조회가
    # 공시 다음 날(공시가 주가를 움직이는 날)의 범위를 집게 되므로 한 칸 민다.
    return est.shift(1)
