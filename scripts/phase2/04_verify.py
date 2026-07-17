"""Phase 2 · T6: 검증 게이트 — qlib.init 후 데이터 로드 + 최근일·비결측 확인.

통과 조건:
  1) qlib.init(provider_uri=data/qlib_us, region=us) 성공
  2) 거래달력 비어있지 않고 마지막 날짜 존재(경고: 10일 초과 지연 시)
  3) instruments 수가 유니버스와 대체로 일치
  4) 샘플 종목 $close/$factor 등 최근 구간 로드 → 비어있지 않고 전부 NaN 아님

실행:  .venv/bin/python scripts/phase2/04_verify.py
"""
from __future__ import annotations

import pandas as pd

import qlib
from qlib.config import REG_US
from qlib.data import D

from _common import QLIB_DIR, log, read_universe

FIELDS = ["$open", "$high", "$low", "$close", "$vwap", "$volume", "$factor"]


def main() -> None:
    if not (QLIB_DIR / "calendars").exists():
        raise SystemExit(f"[오류] qlib 데이터 없음: {QLIB_DIR} (먼저 03_dump_bin.py 실행)")

    # 1) init
    qlib.init(provider_uri=str(QLIB_DIR), region=REG_US)
    log(f"✅ (1) qlib.init 성공: provider_uri={QLIB_DIR}")

    # 2) 달력
    cal = D.calendar(freq="day")
    if len(cal) == 0:
        raise SystemExit("[실패] 거래달력이 비어있음")
    last = pd.Timestamp(cal[-1])
    lag_days = (pd.Timestamp.now().normalize() - last.normalize()).days
    log(f"✅ (2) 달력: {len(cal)}일, {pd.Timestamp(cal[0]).date()} ~ {last.date()}")
    if lag_days > 10:
        log(f"   ⚠️ 마지막 거래일이 {lag_days}일 지연 — 데이터 신선도 확인 권장")

    # 3) instruments 수
    universe = read_universe()
    insts = D.list_instruments(D.instruments("all"), as_list=True)
    log(f"✅ (3) instruments: {len(insts)}개 (유니버스 {len(universe)}개)")
    if len(insts) < len(universe) * 0.8:
        log(f"   ⚠️ instruments 수가 유니버스의 80% 미만 — 수집 실패 종목 확인")

    # 4) 샘플 로드
    sample = insts[0]
    start = (last - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    df = D.features([sample], FIELDS, start_time=start, end_time=last.strftime("%Y-%m-%d"))
    if df is None or df.empty:
        raise SystemExit(f"[실패] {sample} feature 로드 결과 비어있음")
    if df["$close"].notna().sum() == 0:
        raise SystemExit(f"[실패] {sample} $close 전부 NaN")
    log(f"✅ (4) 샘플 {sample}: {len(df)}행 로드, $close 유효 {df['$close'].notna().sum()}행")
    log(f"      최근 3행:\n{df.tail(3).to_string()}")

    log("\n🎉 Phase 2 검증 게이트 통과")


if __name__ == "__main__":
    main()
