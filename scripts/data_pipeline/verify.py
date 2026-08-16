"""검증 게이트의 알맹이 — qlib 번들을 직접 읽어 신선도를 판정한다.

게이트 (5)는 `_collect_report.json`이라는 **중간 산출물을 신뢰**한다. 리포트가 없거나
(구버전 수집), 손으로 넣은 raw가 섞이면 통과한다. 여기서는 최종 산출물을 직접 스캔해
그 신뢰를 없앤다.

폐지 종목은 제외한다. 게이트가 잡으려는 건 "수집이 조용히 실패한 것"이고, 상장폐지는
"유니버스에서 빠져야 할 것"이다 — 후자를 stale 경고로 다루면 마이크로캡에서는 게이트가
상시 발동한다(표본 실측: 결측의 피인수 70.5%·파산 10.5%).
"""
from __future__ import annotations

import csv
from pathlib import Path

from _common import STALE_MAX_LAG_DAYS, TOSS_META_CSV

# 워커 스폰이 환경에 따라 멈춘다. 이 규모(수백 종목)에서는 단일 커널이 23배 빠르기도 하다
# — 533종목 실측 6.9s(기본) vs 0.3s(kernels=1).
_QLIB_KERNELS = 1


def delisted_symbols(meta_path: Path = TOSS_META_CSV) -> set[str]:
    """`delistDate`가 있거나 status가 ACTIVE가 아닌 심볼. 메타가 없으면 빈 집합."""
    if not meta_path.exists():
        return set()
    out = set()
    with open(meta_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sym = (row.get("symbol") or "").strip()
            if not sym:
                continue
            if (row.get("delistDate") or "").strip():
                out.add(sym)
            elif (row.get("status") or "ACTIVE").strip().upper() != "ACTIVE":
                out.add(sym)
    return out


SCAN_WINDOW_DAYS = 730   # 조회 창. 좁으면 가장 심하게 뒤처진 종목이 창 밖으로 빠져 면제된다


def lag_by_symbol(qlib_dir: Path) -> dict[str, int]:
    """번들의 종목별 '마지막 유효 종가'가 표본 내 최신일 대비 며칠(달력일) 뒤처졌는지.

    기준은 '오늘'이 아니라 표본 내 최신일이다 — 휴장·오래된 스냅샷에서 전 종목이 동시에
    stale로 뜨는 것을 막고, 잡으려는 건 "남들은 최신인데 혼자 뒤처진 종목"이다.

    창(`SCAN_WINDOW_DAYS`) 안에 유효 종가가 하나도 없는 종목은 **가장 심하게 뒤처진 경우**다.
    조회 결과에서 통째로 빠지므로 명시적으로 창 크기를 지연값으로 준다 — 그러지 않으면
    게이트가 잡으려던 대상이 정확히 면제된다.
    """
    import pandas as pd
    import qlib
    from qlib.config import REG_US
    from qlib.data import D

    qlib.init(provider_uri=str(qlib_dir), region=REG_US, kernels=_QLIB_KERNELS)
    cal = D.calendar(freq="day")
    if not len(cal):
        return {}
    newest = pd.Timestamp(cal[-1])
    insts = D.list_instruments(D.instruments("all"), as_list=True)
    if not insts:
        return {}
    start = (newest - pd.Timedelta(days=SCAN_WINDOW_DAYS)).strftime("%Y-%m-%d")
    df = D.features(insts, ["$close"], start_time=start)
    if df is None or df.empty:
        return {s: SCAN_WINDOW_DAYS for s in map(str, insts)}
    last = df["$close"].dropna().groupby(level=0).apply(lambda s: s.index[-1][1])
    out = {str(sym): int((newest - d).days) for sym, d in last.items()}
    for s in map(str, insts):
        out.setdefault(s, SCAN_WINDOW_DAYS)   # 창 밖 = 최소 이만큼 뒤처졌다
    return out


def stale_in_bundle(qlib_dir: Path, max_lag_days: int = STALE_MAX_LAG_DAYS,
                    exclude: set[str] | None = None) -> list[tuple[str, int]]:
    """임계를 넘게 뒤처진 (symbol, lag) 목록. 폐지 종목은 제외한다."""
    skip = exclude if exclude is not None else delisted_symbols()
    return sorted((s, lag) for s, lag in lag_by_symbol(qlib_dir).items()
                  if lag > max_lag_days and s not in skip)
