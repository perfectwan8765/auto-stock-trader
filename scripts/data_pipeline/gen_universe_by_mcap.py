"""이벤트 시점 PIT 시가총액 산정 → data/insider_events_mcap.csv, universe/microcap_by_mcap.txt

`시총 = (filed <= 이벤트일 인 최신 발행주식수) × (이벤트일 종가)` — 두 입력 모두 PIT.

Toss의 `sharesOutstanding`은 현재값이라 과거 이벤트 필터에 쓰면 "그땐 마이크로캡, 지금 $2B"인
종목만 빠지는 승자 배제 편향이 생긴다. 주가 밴드($5~$50)도 프록시로 실패했다(중앙값 $976M).

폐지 종목은 가격이 없어 위 식이 안 통한다(§3.8). 대체로 `dei:EntityPublicFloat`를 쓴다 —
USD 값이라 가격 조인이 불필요해 가격이 사라진 종목도 산출된다(가격 없는 395종목 중 85.8% 보유).
float은 내부자 지분을 뺀 값이라 시총보다 작으므로, 둘 다 있는 이벤트의 `float/시총` 중앙값으로
환산한다. 종목별 지분율 편차가 커 오차가 크므로 산포도 함께 출력하고 `mcap_source`에 출처를 남긴다.

실행:  .venv/bin/python scripts/data_pipeline/gen_universe_by_mcap.py
옵션:  --max-mcap 3e8  --min-mcap 5e7   (기본: 마이크로캡 <$300M)
"""
from __future__ import annotations

import sys

import argparse
import bisect
import collections
import csv
import statistics
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CANDIDATE_CLOSES_CSV, EVENTS_CSV, EVENTS_MCAP_CSV, write_csv_atomic

ROOT = Path(__file__).resolve().parents[2]
EVENTS = EVENTS_CSV
SHARES = ROOT / "data" / "shares_outstanding.csv"
PRICES = CANDIDATE_CLOSES_CSV
TRADABLE = ROOT / "universe" / "microcap_tradable.txt"
OUT_EVENTS = EVENTS_MCAP_CSV
OUT_UNIVERSE = ROOT / "universe" / "microcap_by_mcap.txt"

# 이벤트일과 직전 거래일 사이 허용 간극(달력일). 넘으면 가격 없음으로 본다.
MAX_PRICE_STALE_DAYS = 10

# 밴드 경계(USD). 통상 정의: micro < $300M < small < $2B < mid
BANDS = [(0, 5e7, "NANO(<$50M)"), (5e7, 3e8, "MICRO($50M~300M)"),
         (3e8, 2e9, "SMALL($300M~2B)"), (2e9, 1e10, "MID($2B~10B)"), (1e10, float("inf"), "LARGE(>$10B)")]


def load_closes() -> pd.DataFrame:
    """종가 행렬을 읽는다. 생산은 fetch_candidate_closes.py 담당이다."""
    if not PRICES.exists():
        raise SystemExit(
            f"[오류] {PRICES.name} 없음 — scripts/data_pipeline/fetch_candidate_closes.py 먼저 실행"
        )
    return pd.read_csv(PRICES, index_col=0, parse_dates=True)


def load_metric(metric: str) -> dict[str, tuple[list[str], list[float]]]:
    """symbol -> (filed 오름차순 배열, 그 시점까지 공시된 '가장 최근 기준일' 값).

    metric은 'shares'(발행주식수) 또는 'public_float'(유통시가총액 USD).

    filed 최신값을 그냥 쓰면 안 된다 — XBRL에는 나중에 제출된 서류가 과거 시점 값을 보고하는
    행이 흔하다(실측: 10x Genomics `end=2018-12-31` / `filed=2020-02-27`). 그걸 최신으로
    잡으면 2020년 이벤트에 2018년 주식수가 붙어 시총을 크게 과소추정한다.
    """
    by_sym: dict[str, list[tuple[str, str, float]]] = collections.defaultdict(list)
    with open(SHARES, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["metric"] != metric:
                continue
            try:
                by_sym[r["symbol"]].append((r["filed"], r["end"], float(r["val"])))
            except (ValueError, TypeError):
                continue  # metric='error'/'missing' 행은 val이 비어 여기서 걸러진다

    out: dict[str, tuple[list[str], list[float]]] = {}
    for sym, rows in by_sym.items():
        rows.sort()  # filed 오름차순
        dates: list[str] = []
        vals: list[float] = []
        best_end, best_val = "", 0.0
        for filed, end, val in rows:
            if end > best_end:
                best_end, best_val = end, val
            elif end == best_end:  # 같은 기준일 재보고(복수 클래스 등)는 최대값
                best_val = max(best_val, val)
            if dates and dates[-1] == filed:
                vals[-1] = best_val
            else:
                dates.append(filed)
                vals.append(best_val)
        out[sym] = (dates, vals)
    return out


def pit_at(series: dict[str, tuple[list[str], list[float]]], sym: str, day: str) -> float | None:
    """`filed <= day` 인 최신 공시값. 미래 정보가 새지 않는 유일한 조회 방법."""
    if sym not in series:
        return None
    dates, vals = series[sym]
    pos = bisect.bisect_right(dates, day) - 1
    return vals[pos] if pos >= 0 else None


def band_of(mcap: float | None) -> str:
    if mcap is None:
        return "UNKNOWN"
    for lo, hi, label in BANDS:
        if lo <= mcap < hi:
            return label
    return "UNKNOWN"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-mcap", type=float, default=0.0)
    ap.add_argument("--max-mcap", type=float, default=3e8)
    args = ap.parse_args()

    for p in (EVENTS, SHARES):
        if not p.exists():
            raise SystemExit(f"[오류] {p.relative_to(ROOT)} 없음")

    events = list(csv.DictReader(open(EVENTS, newline="", encoding="utf-8")))
    symbols = sorted({e["symbol"] for e in events})
    dates = sorted({e["filing_date"] for e in events})
    print(f"이벤트 {len(events):,}건 · 종목 {len(symbols):,} · 기간 {dates[0]} ~ {dates[-1]}")

    closes = load_closes()
    shares = load_metric("shares")
    floats = load_metric("public_float")
    print(f"가격 확보 {closes.shape[1]:,}종목 · 주식수 {len(shares):,}종목 · public_float {len(floats):,}종목")

    # 티커가 재사용되면 가격이 어느 발행사 것인지 결정할 수 없다(yfinance는 티커로만 조회).
    # 틀린 시총을 주느니 UNKNOWN으로 남긴다.
    cik_per_symbol = collections.defaultdict(set)
    for e in events:
        cik_per_symbol[e["symbol"]].add(e["cik"])
    ambiguous = {s for s, c in cik_per_symbol.items() if len(c) > 1}
    if ambiguous:
        print(f"복수 CIK 티커 {len(ambiguous)}건 → 시총 산정 제외: {', '.join(sorted(ambiguous)[:8])}")

    idx = {s: (closes[s].dropna().index, closes[s].dropna().values) for s in closes.columns}

    base = []
    for e in events:
        sym, day = e["symbol"], e["filing_date"]
        price = sh = fl = None
        if sym not in ambiguous:
            if sym in idx:
                di, dv = idx[sym]
                pos = di.searchsorted(pd.Timestamp(day), side="right") - 1
                # 간극 상한: 거래정지·폐지로 몇 달 전 종가가 붙는 것을 막는다.
                if pos >= 0 and (pd.Timestamp(day) - di[pos]).days <= MAX_PRICE_STALE_DAYS:
                    price = float(dv[pos])
            sh = pit_at(shares, sym, day)
            fl = pit_at(floats, sym, day)
        direct = price * sh if (price and sh) else None
        base.append((e, price, sh, fl, direct))

    ratios = sorted(fl / direct for _e, _p, _s, fl, direct in base if fl and direct and direct > 0)
    if ratios:
        r25, r50, r75 = (ratios[len(ratios) // 4], statistics.median(ratios), ratios[3 * len(ratios) // 4])
        print(f"\nfloat/시총 비율 {len(ratios):,}건 — p25={r25:.2f} p50={r50:.2f} p75={r75:.2f}")
        print(f"  → float 대체 시 시총 ≈ float / {r50:.2f}")
    else:
        r50 = None
        print("\n⚠️ float/시총 비율을 잴 표본이 없다 — float 대체 비활성화")

    counts, src_counts = collections.Counter(), collections.Counter()
    rows = []
    for e, price, sh, fl, direct in base:
        if direct:
            mcap, src = direct, "shares_price"
        elif fl and r50:
            mcap, src = fl / r50, "float_scaled"
        else:
            mcap = None
            src = ("ambiguous_ticker" if e["symbol"] in ambiguous
                   else "no_price" if price is None else "no_shares")
        b = band_of(mcap)
        counts[b] += 1
        src_counts[src] += 1
        rows.append({**e, "close": price, "shares_outstanding": sh, "public_float": fl,
                     "mcap_usd": round(mcap, 0) if mcap else "", "mcap_source": src, "mcap_band": b})

    with open(OUT_EVENTS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    total = len(events)
    print(f"\n{'밴드':22s} {'이벤트':>8s} {'비율':>7s}")
    for _lo, _hi, label in BANDS:
        print(f"{label:22s} {counts[label]:8,} {100*counts[label]/total:6.1f}%")
    print(f"{'UNKNOWN':22s} {counts['UNKNOWN']:8,} {100*counts['UNKNOWN']/total:6.1f}%")

    print(f"\n{'시총 출처':22s} {'이벤트':>8s} {'비율':>7s}")
    for src, n in src_counts.most_common():
        print(f"{src:22s} {n:8,} {100*n/total:6.1f}%")

    in_band = [r for r in rows
               if r["mcap_usd"] != "" and args.min_mcap <= float(r["mcap_usd"]) < args.max_mcap]
    keep = {r["symbol"] for r in in_band}

    # 최종 유니버스는 시총 밴드 ∩ Toss 집행가능. 두 조건은 직교하므로 둘 다 걸어야 한다.
    note = "Toss 필터 미적용"
    if TRADABLE.exists():
        tradable = {s.strip().upper() for s in TRADABLE.read_text().splitlines()
                    if s.strip() and not s.startswith("#")}
        before = len(keep)
        keep &= tradable
        in_band = [r for r in in_band if r["symbol"] in keep]
        note = f"Toss 거래가능 교집합 적용({before} → {len(keep)})"
        print(f"\n{note}")

    OUT_UNIVERSE.write_text("\n".join([
        f"# 최종 유니버스 — 이벤트 시점 PIT 시총 ${args.min_mcap:,.0f}~${args.max_mcap:,.0f} ∩ {note}.",
        f"# {len(keep)}종목 / 해당 이벤트 {len(in_band):,}건 (전체 {total:,}건 중 {100*len(in_band)/total:.1f}%).",
        "# gen_universe_by_mcap.py로 재생성. 밴드 판정은 이벤트 단위 — data/insider_events_mcap.csv 참조.",
        *sorted(keep),
    ]) + "\n")
    print(f"밴드 내 종목 {len(keep):,} · 이벤트 {len(in_band):,}건")
    print(f"[완료] {OUT_EVENTS.relative_to(ROOT)} · {OUT_UNIVERSE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
