"""Phase 4b — 오프라인 dry-run 데모: 시그널 → 발주계획(실발주 없음).

signals/signal_<date>.json(Phase 4a) + synthetic 브로커 상태로 RebalanceRunner를 dry-run.
데이터→예측→시그널→리밸계획 end-to-end를 **토스 API 없이** 확인. 실 브로커 상태(보유·가격·
가용)는 Phase 0(키 승인) 후 TossBroker로 교체 → dry_run=False로 실발주.

실행:  .venv/bin/python scripts/model_backtest/dry_run_rebalance.py [--signal <path>]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from execution.runner import RebalanceRunner  # noqa: E402


class SyntheticBroker:
    """오프라인 데모용: 빈 계좌 + 균일 가격 + 고정 가용현금. Phase 0 후 TossBroker로 교체."""

    def __init__(self, buying_power=700.0, flat_price=100.0):
        self._bp = buying_power
        self._price = flat_price

    def get_holdings(self):
        return {}

    def get_prices(self, symbols):
        return {s: self._price for s in symbols}

    def get_buying_power_usd(self):
        return self._bp

    def is_market_open(self):
        return True

    def place(self, intent):  # dry-run에선 호출 안 됨
        raise RuntimeError("SyntheticBroker.place는 실발주 불가(데모)")


def _latest_signal() -> Path:
    sigs = sorted((ROOT / "signals").glob("signal_*.json"))
    if not sigs:
        raise SystemExit("[오류] signals/ 없음 — 먼저 generate_signal.py 실행")
    return sigs[-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--signal", default=None, help="시그널 JSON 경로(생략 시 최신)")
    ap.add_argument("--buying-power", type=float, default=700.0)
    ap.add_argument("--min-order", type=float, default=1.0)
    args = ap.parse_args()

    sig_path = Path(args.signal) if args.signal else _latest_signal()
    sig = json.loads(sig_path.read_text())
    date = sig["date"].replace("-", "")

    broker = SyntheticBroker(buying_power=args.buying_power)
    runner = RebalanceRunner(broker, min_order_usd=args.min_order)
    res = runner.run(sig["weights"], rebalance_date=date, dry_run=True)

    print(f"📄 시그널: {sig_path.relative_to(ROOT)} (date={sig['date']}, topk={sig['topk']})")
    print(f"💵 synthetic: 빈 계좌, 가용 ${args.buying_power}, 균일가 $100\n")
    print(f"{'DRY-RUN 발주계획':=^56}")
    for o in res.plan.orders:
        v = f"${o.value}" if o.kind == "amount" else f"{o.value}주"
        print(f"  {o.side:4s} {o.symbol:6s} {v:>10s}  [{o.reason}]  {o.client_order_id}")
    total_buy = sum(o.value for o in res.plan.orders if o.side == "BUY")
    print(f"\n  총 {len(res.plan.orders)}건, 매수합 ${total_buy:.2f}, 스킵 {len(res.plan.skipped)}")
    if res.plan.skipped:
        print(f"  스킵: {res.plan.skipped}")
    print("\n⚠️ dry-run(실발주 없음). 실발주는 Phase 0 후 TossBroker + dry_run=False.")


if __name__ == "__main__":
    main()
