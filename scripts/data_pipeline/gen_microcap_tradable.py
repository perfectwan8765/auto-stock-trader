"""Edge v2 단계 0 산출물: 실제 거래 가능한 마이크로캡 유니버스 → universe/microcap_tradable.txt

입력은 06_microcap_coverage.py가 저장한 data/toss_stock_meta.csv(Toss 종목 메타 실측).
후보(microcap_candidates.txt)에서 아래를 걸러 남긴다:

  - Toss 미취급          : 메타에 없는 심볼
  - 상장폐지             : status != ACTIVE
  - ETF·폐쇄형펀드       : securityType != STOCK 또는 isCommonShare != true
        후보가 Form 4 발행사 기준이라 CEF/ETF가 섞인다(실측 10%). 이들 임원도 Form 4를 내지만
        우리가 노리는 마이크로캡 주식 anomaly와 무관하다.

여기서 **시총은 거르지 않는다.** Toss가 주는 sharesOutstanding은 현재값이라 과거 이벤트를
거르면 승자 배제 편향이 생긴다(실측: PIT 마이크로캡 이벤트의 35.9% 탈락).
시총 컷은 이벤트 시점 PIT로 계산하는 gen_universe_by_mcap.py가 담당한다.

실행:  uv run python scripts/data_pipeline/gen_microcap_tradable.py
"""
from __future__ import annotations


import collections
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
META = ROOT / "data" / "toss_stock_meta.csv"
PROBED = ROOT / "data" / "toss_probed_symbols.txt"
CANDIDATES = ROOT / "universe" / "microcap_candidates.txt"
OUT = ROOT / "universe" / "microcap_tradable.txt"

_TRUE = {"True", "true", "TRUE", "1"}


def read_candidates() -> list[str]:
    return [s.strip().upper() for s in CANDIDATES.read_text().splitlines()
            if s.strip() and not s.startswith("#")]


def main() -> None:
    if not META.exists():
        raise SystemExit(f"[오류] {META.relative_to(ROOT)} 없음 — 먼저 scripts/toss_probe/06_microcap_coverage.py 실행")

    meta = {r["symbol"]: r for r in csv.DictReader(open(META, newline="", encoding="utf-8"))}
    candidates = read_candidates()

    # 미조회를 '미취급'으로 처리하면 유니버스가 조용히 깎인다.
    if PROBED.exists():
        probed = {s.strip().upper() for s in PROBED.read_text().splitlines()
                  if s.strip() and not s.startswith("#")}
        unprobed = [s for s in candidates if s not in probed]
        if unprobed:
            raise SystemExit(
                f"[중단] 후보 {len(unprobed):,}종목이 프로브되지 않았다(예: {', '.join(unprobed[:5])}).\n"
                "  '미취급'으로 오분류되면 유니버스가 조용히 깎인다.\n"
                "  scripts/toss_probe/06_microcap_coverage.py를 --limit 없이 다시 실행할 것."
            )
    else:
        print(f"  ⚠️ {PROBED.name} 없음 — 메타에 없는 심볼을 전부 '미취급'으로 간주한다(구버전 프로브 산출물).")

    drop = collections.Counter()
    kept: list[str] = []

    for sym in candidates:
        m = meta.get(sym)
        if m is None:
            drop["Toss 미취급"] += 1
            continue
        if m.get("status") != "ACTIVE":
            drop["상장폐지(status)"] += 1
            continue
        if m.get("securityType") != "STOCK" or m.get("isCommonShare") not in _TRUE:
            drop["ETF·펀드·비보통주"] += 1
            continue
        kept.append(sym)

    print(f"후보 {len(candidates):,} → 거래가능 {len(kept):,} ({100*len(kept)/max(len(candidates),1):.1f}%)")
    for label, n in drop.most_common():
        print(f"  제외 {label:20s} {n:6,}")

    OUT.write_text("\n".join([
        f"# 거래가능 마이크로캡 유니버스 — microcap_candidates.txt ∩ Toss 취급·ACTIVE·보통주.",
        f"# {len(kept)}종목 (후보 {len(candidates)}개 중 {100*len(kept)/max(len(candidates),1):.1f}%).",
        "# gen_microcap_tradable.py로 재생성. 입력: data/toss_stock_meta.csv(06_microcap_coverage.py 산출).",
        *kept,
    ]) + "\n")
    print(f"\n[완료] {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
