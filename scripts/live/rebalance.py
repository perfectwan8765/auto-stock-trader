"""Phase 5/6 — 라이브 리밸런싱 진입점.

시그널(signals/*.json) → 실 TossBroker로 주간 리밸런싱 발주. 데이터→예측→시그널→발주를
한 명령으로 묶는 실전 엔트리. dry_run_rebalance.py(오프라인 SyntheticBroker 데모)와 달리
실 브로커·화이트리스트(개선14)·예산 상한·안전장치를 조립한다.

⚠️ 안전:
- 기본 **dry-run**. `--confirm` 없으면 절대 실발주하지 않는다.
- kill switch 파일 존재 시 중단. 정규장 확인 후만 발주(runner). 화이트리스트로 사용자 수동
  보유·현금 보호. 멱등키로 재시도 중복 방지.
- 실 발주·응답필드 확정·손익 기반 서킷브레이커는 Phase 0(토스 키) 필요. 키 없으면 설정
  오류로 안전 종료.

실행:
  .venv/bin/python scripts/live/rebalance.py                 # dry-run(기본)
  .venv/bin/python scripts/live/rebalance.py --confirm       # 실발주(정규장·키 필요)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from execution.managed import ManagedState  # noqa: E402
from execution.runner import RebalanceRunner  # noqa: E402
from execution.safety import CircuitBreaker  # noqa: E402
from toss.broker import TossBroker  # noqa: E402
from toss.client import TossClient  # noqa: E402
from toss.config import load_config  # noqa: E402
from toss.errors import TossError  # noqa: E402

SIGNAL_DIR = ROOT / "signals"
LOG_DIR = ROOT / "execution_logs"


def _latest_signal() -> Path:
    sigs = sorted(SIGNAL_DIR.glob("signal_*.json"))
    if not sigs:
        raise SystemExit("[오류] signals/ 없음 — 먼저 generate_signal.py 실행")
    return sigs[-1]


def _print_result(res, dry_run: bool) -> None:
    print(f"\n{'DRY-RUN 발주계획' if dry_run else '실발주 결과':=^56}")
    if res.aborted_reason:
        print(f"  중단: {res.aborted_reason}")
    for o in res.plan.orders:
        v = f"${o.value}" if o.kind == "amount" else f"{o.value}주"
        placed = "✓발주" if o.client_order_id in res.placed else ("계획" if dry_run else "미발주")
        print(f"  {o.side:4s} {o.symbol:6s} {v:>10s}  [{o.reason}]  {placed}")
    total_buy = sum(o.value for o in res.plan.orders if o.side == "BUY")
    print(f"\n  총 {len(res.plan.orders)}건, 매수합 ${total_buy:.2f}, "
          f"스킵 {len(res.plan.skipped)}, 발주 {len(res.placed)}")
    if res.plan.skipped:
        print(f"  스킵: {res.plan.skipped}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--signal", default=None, help="시그널 JSON 경로(생략 시 최신)")
    ap.add_argument("--budget", type=float, default=700.0, help="봇 매수 예산 상한(USD)")
    ap.add_argument("--min-order", type=float, default=1.0, help="최소 주문금액(USD, Phase 0 실측 전 placeholder)")
    ap.add_argument("--state", default=str(LOG_DIR / "managed_state.json"), help="화이트리스트 상태 파일")
    ap.add_argument("--kill-switch", default=str(ROOT / "KILL"), help="이 파일 존재 시 발주 중단")
    ap.add_argument("--max-orders", type=int, default=60, help="일일 주문건수 상한(서킷브레이커)")
    ap.add_argument("--max-loss", type=float, default=700.0, help="일일 손실 상한(USD, 손익 배선은 Phase 0)")
    ap.add_argument("--confirm", action="store_true", help="실발주. 없으면 dry-run.")
    args = ap.parse_args()

    sig_path = Path(args.signal) if args.signal else _latest_signal()
    sig = json.loads(sig_path.read_text())
    weights, date = sig["weights"], sig["date"].replace("-", "")

    cfg = load_config(require_account=True)   # 주문 API는 X-Tossinvest-Account 필요
    broker = TossBroker(TossClient(cfg))
    state = ManagedState.load(args.state)
    cb = CircuitBreaker(max_orders_per_day=args.max_orders, max_loss_usd=args.max_loss)
    runner = RebalanceRunner(
        broker, min_order_usd=args.min_order, budget_usd=args.budget,
        managed_state=state, kill_switch_path=args.kill_switch,
        circuit_breaker=cb, log_dir=str(LOG_DIR),
    )

    dry_run = not args.confirm
    mode = "DRY-RUN(계획만)" if dry_run else "🔴 실발주"
    print(f"시그널: {sig_path.relative_to(ROOT)} (date={sig['date']}, topk={sig['topk']})")
    print(f"모드: {mode} · 예산 ${args.budget} · min ${args.min_order}")

    res = runner.run(weights, rebalance_date=date, dry_run=dry_run)
    _print_result(res, dry_run)

    if dry_run:
        print("\n⚠️ dry-run(실발주 없음). 실발주는 정규장 시간에 --confirm (토스 키 필요).")


def _cli() -> None:
    """CLI 경계: 라이브러리 TossError를 clean 메시지·exit로 변환(개선10)."""
    try:
        main()
    except TossError as e:
        raise SystemExit(str(e))


if __name__ == "__main__":
    _cli()
