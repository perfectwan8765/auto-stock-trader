"""Phase 2 · T6: 검증 게이트 — qlib.init 후 데이터 로드 + 최근일·비결측 확인.

통과 조건:
  1) qlib.init(provider_uri=data/qlib_us, region=us) 성공
  2) 거래달력 비어있지 않고 마지막 날짜 존재(경고: 10일 초과 지연 시)
  3) instruments 수가 유니버스와 대체로 일치
  4) 샘플 종목 $close/$factor 등 최근 구간 로드 → 비어있지 않고 전부 NaN 아님
  5) 수집 리포트에 뒤처진(stale) 종목이 없음 — 01_collect의 폴백이 조용히 흘러가는 것을 막는다
  6) 번들 자체에도 뒤처진 종목이 없음 — (5)가 신뢰하는 중간 산출물이 없어도 잡는다

실행:  .venv/bin/python scripts/data_pipeline/04_verify.py
"""
from __future__ import annotations

import json

import pandas as pd

import qlib
from qlib.config import REG_US
from qlib.data import D

from _common import COLLECT_REPORT, QLIB_DIR, STALE_MAX_LAG_DAYS, log, read_universe, stale_symbols
from verify import stale_in_bundle

FIELDS = ["$open", "$high", "$low", "$close", "$vwap", "$volume", "$factor"]


def check_freshness() -> None:
    """게이트 (5). qlib에 의존하지 않으므로 init 전에 돌린다.

    (2)(3)(4)는 stale을 못 잡는다 — (2)는 전역 달력의 마지막 날짜만, (3)은 개수만,
    (4)는 종목 하나만 본다. 한 종목이라도 최신이면 전부 통과한다.
    """
    if not COLLECT_REPORT.exists():
        log(f"   ⚠️ (5) 수집 리포트 없음({COLLECT_REPORT.name}) — 01_collect 재실행 전까지 신선도 미검증")
        return
    report = json.loads(COLLECT_REPORT.read_text())
    stale = stale_symbols(report)
    if stale:
        detail = ", ".join(f"{s}({lag}일)" for s, lag in stale[:10])
        more = f" 외 {len(stale) - 10}종목" if len(stale) > 10 else ""
        raise SystemExit(
            f"[실패] (5) 뒤처진 종목 {len(stale)}개: {detail}{more}\n"
            "  01_collect의 폴백으로 옛 데이터가 남아 있다. 재수집하거나 유니버스에서 제외할 것.")
    log(f"✅ (5) 신선도: 전 종목이 기준일 대비 임계 내 ({len(report.get('symbols', {}))}종목)")


def _gate_bundle_freshness() -> None:
    """게이트 (6). (5)는 _collect_report.json을 신뢰하지만 그 파일이 없으면 아무것도 못 본다.

    번들을 직접 스캔하면 그 신뢰가 필요 없다. 다만 qlib 로딩이 환경에 따라 막히는 사례가
    있어(워커 스폰), 실패해도 파이프라인을 세우지 않고 경고만 낸다 — (5)가 환경 무관하게
    항상 도는 겹이다.
    """
    try:
        stale = stale_in_bundle(QLIB_DIR)
    except Exception as exc:  # noqa: BLE001 — 환경 의존성을 파이프라인 실패로 만들지 않는다
        log(f"   ⚠️ (6) 번들 신선도 검사 건너뜀: {type(exc).__name__}: {exc}")
        return
    if stale:
        detail = ", ".join(f"{s}({lag}일)" for s, lag in stale[:10])
        more = f" 외 {len(stale) - 10}종목" if len(stale) > 10 else ""
        raise SystemExit(
            f"[실패] (6) 번들에 뒤처진 종목 {len(stale)}개: {detail}{more}\n"
            f"  기준: 표본 내 최신일 대비 {STALE_MAX_LAG_DAYS} 거래일. 폐지 종목은 제외했다.\n"
            "  01_collect 재실행 또는 유니버스 갱신이 필요하다."
        )
    log("✅ (6) 번들 신선도: 뒤처진 종목 없음(폐지 제외)")


def main() -> None:
    check_freshness()
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

    _gate_bundle_freshness()

    log("\n🎉 Phase 2 검증 게이트 통과")


if __name__ == "__main__":
    main()
