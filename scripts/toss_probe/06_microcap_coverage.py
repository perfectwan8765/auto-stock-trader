"""Edge v2 단계 0(집행가능성 게이트) — 읽기 전용 프로브.

작업계획서 §5 단계 0의 (a)(b)(e)를 실측한다. **주문은 내지 않는다.**
  (a) Toss가 마이크로캡 후보를 취급하는가 → 취급률·거래소(OTC 배제)·상장상태
  (b) /api/v1/prices 원 응답에 호가(bid/ask)가 있는가 → 스프레드 실측 경로 존재 여부

(b) 실측 결과 호가는 제공되지 않는다(lastPrice만). 스프레드는 일봉 OHLC 추정량으로 대체한다.

왜 게이트인가: 이 계획의 논거는 "$700이 마이크로캡 니치를 착취한다"인데, Toss가 그 니치를
취급하지 않으면 이후 단계가 통째로 사장된다. 데이터 수집보다 먼저 확인해야 한다.

최소수수료·지정가/정수주 지원((c)(d))은 **실주문이 필요**하므로 이 스크립트 범위 밖이다.

실행:  .venv/bin/python scripts/toss_probe/06_microcap_coverage.py
옵션:  --limit 300   (후보 상위 N개만 조회)   --batch 20
전제:  universe/microcap_candidates.txt (gen_microcap_candidates.py로 생성)
"""
import _bootstrap  # noqa: F401

import argparse
import collections
import csv
import time
from pathlib import Path

from toss.broker import TossBroker
from toss.client import TossApiError, TossClient
from toss.config import load_config

ROOT = Path(__file__).resolve().parents[2]
CANDIDATES = ROOT / "universe" / "microcap_candidates.txt"
META_OUT = ROOT / "data" / "toss_stock_meta.csv"
PROBED_OUT = ROOT / "data" / "toss_probed_symbols.txt"

# 응답에 무엇이 오는지 모르므로 넓게 잡고 발견되는 것을 보고한다.
_QUOTE_HINTS = ("bid", "ask", "offer", "spread", "high", "low", "open", "prev")


def read_candidates(limit: int | None) -> list[str]:
    if not CANDIDATES.exists():
        raise SystemExit(
            f"[오류] {CANDIDATES.relative_to(ROOT)} 없음 — "
            "먼저 scripts/data_pipeline/gen_microcap_candidates.py 실행"
        )
    out = []
    for line in CANDIDATES.read_text().splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            out.append(s.upper())
    return out[:limit] if limit else out


def probe_stock_info(broker: TossBroker, symbols: list[str], batch: int) -> dict[str, dict]:
    """배치 조회. 배치가 통째로 실패하면 개별 조회로 낙하해 원인 심볼을 격리한다."""
    found: dict[str, dict] = {}
    for i in range(0, len(symbols), batch):
        chunk = symbols[i : i + batch]
        try:
            found.update(broker.get_stock_info(chunk))
        except TossApiError as e:
            print(f"  [배치 실패 {i}~{i+len(chunk)}] {e} → 개별 재시도")
            for sym in chunk:
                try:
                    found.update(broker.get_stock_info([sym]))
                except TossApiError:
                    pass
                time.sleep(0.2)
        time.sleep(0.2)  # GET rate-limit 미상 → 보수적으로 5 req/s 이하 유지
        if (i // batch) % 10 == 0:
            print(f"  ...{min(i + batch, len(symbols))}/{len(symbols)}")
    return found


def summarize(label: str, counter: collections.Counter, top: int = 8) -> None:
    total = sum(counter.values()) or 1
    print(f"\n  {label}")
    for key, n in counter.most_common(top):
        print(f"    {str(key):24s} {n:6,} {100*n/total:5.1f}%")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="후보 상위 N개만")
    ap.add_argument("--batch", type=int, default=20)
    args = ap.parse_args()

    symbols = read_candidates(args.limit)
    cfg = load_config(require_account=True)
    client = TossClient(cfg)
    broker = TossBroker(client)

    print(f"후보 {len(symbols):,}종목 — /api/v1/stocks 조회 (읽기 전용)")
    info = probe_stock_info(broker, symbols, args.batch)

    if not info:
        raise SystemExit("[중단] 취급 종목이 하나도 없음 — 심볼 형식·계정 권한 확인")

    covered = len(info)
    print(f"\n{'='*60}\n[a] 취급률: {covered:,}/{len(symbols):,} = {100*covered/len(symbols):.1f}%")

    summarize("market(거래소) 분포", collections.Counter(v.get("market") for v in info.values()))
    summarize("status 분포", collections.Counter(v.get("status") for v in info.values()))
    summarize("securityType 분포", collections.Counter(v.get("securityType") for v in info.values()))
    delisted = [s for s, v in info.items() if v.get("delistDate")]
    print(f"\n  delistDate 있는 종목: {len(delisted):,}건  예: {', '.join(delisted[:5])}")
    print(f"\n  응답 필드 전체: {sorted(next(iter(info.values())).keys())}")
    common = [s for s, v in info.items()
              if v.get("securityType") == "STOCK" and v.get("isCommonShare") in (True, "true", "TRUE")]
    print(f"  보통주(STOCK & isCommonShare): {len(common):,}/{covered:,} "
          f"= {100*len(common)/max(covered,1):.1f}%  ← 나머지는 ETF·폐쇄형펀드 등 오염")

    # get_prices는 lastPrice만 파싱하므로 원 응답을 본다.
    # 전수 조회: sharesOutstanding × lastPrice = 시가총액이라 유니버스 컷의 근거가 된다.
    tradable = [s for s, v in info.items() if v.get("status") == "ACTIVE"] or list(info)
    print(f"\n{'='*60}\n[b] /api/v1/prices 원 응답 확인 + 시세 전수 수집 ({len(tradable):,}종목)")
    items = []
    for i in range(0, len(tradable), args.batch):
        try:
            items.extend(broker.get_prices_raw(tradable[i : i + args.batch]))
        except TossApiError as e:
            print(f"  [배치 실패 {i}] {e}")
        time.sleep(0.2)

    prices = {str(it["symbol"]): it.get("lastPrice") for it in items if it.get("symbol")}
    for sym, px in prices.items():
        if sym in info:
            info[sym]["lastPrice"] = px
    cols = sorted({k for v in info.values() for k in v})
    META_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(META_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(info.values())
    print(f"  메타 저장(시세 포함 {len(prices):,}건): {META_OUT.relative_to(ROOT)}")

    # 이게 없으면 하류가 '미조회'와 'Toss 미취급'을 구분하지 못한다.
    PROBED_OUT.write_text("\n".join([
        f"# 06_microcap_coverage.py가 /api/v1/stocks로 조회를 시도한 심볼 {len(symbols)}건.",
        f"# 이 중 취급 확인 {covered}건. 여기 없는 심볼은 '미취급'이 아니라 '미조회'다.",
        *symbols,
    ]) + "\n")
    print(f"  조회 시도 목록: {PROBED_OUT.relative_to(ROOT)}")

    if items:
        keys = sorted({k for it in items for k in it.keys()})
        print(f"  필드: {keys}")
        hits = [k for k in keys if any(h in k.lower() for h in _QUOTE_HINTS)]
        print(f"  호가 후보 필드: {hits or '없음 — 스프레드 실측 경로 부재'}")
        print(f"  예시: {items[0]}")
    else:
        print("  응답 없음")

    print(f"\n{'='*60}\nUSD 매수가능액: ${broker.get_buying_power_usd():,.2f}")
    print(f"rate-limit 헤더: {client.rate_limit_headers()}")
    print("\n👉 결과를 phase0b-execution-gate.md에 기록.")
    print("   (c)최소수수료 · (d)지정가/정수주 지원은 실주문 필요 — 별도 승인 후 진행.")


if __name__ == "__main__":
    _bootstrap.cli(main)
