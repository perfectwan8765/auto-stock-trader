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
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# 시그널 신선도는 미국 거래일 기준으로 잰다(멱등키와 동일). 정규장이 KST 자정을 넘겨
# 로컬 날짜가 하루 앞서면 경과일이 왜곡되기 때문.
US_MARKET_TZ = ZoneInfo("America/New_York")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from execution.errors import ExecutionError  # noqa: E402
from execution.managed import ManagedState  # noqa: E402
from execution.runner import RebalanceRunner  # noqa: E402
from execution.safety import CircuitBreaker  # noqa: E402
from toss.broker import TossBroker  # noqa: E402
from toss.client import TossClient  # noqa: E402
from toss.config import load_config  # noqa: E402
from toss.errors import TossError  # noqa: E402

SIGNAL_DIR = ROOT / "signals"
LOG_DIR = ROOT / "execution_logs"


def _positive_float(v: str) -> float:
    f = float(v)
    if f <= 0:
        raise argparse.ArgumentTypeError(f"양수여야 함: {v}")
    return f


def _positive_int(v: str) -> int:
    i = int(v)
    if i <= 0:
        raise argparse.ArgumentTypeError(f"양수여야 함: {v}")
    return i


def _signal_age_days(signal_date: str, today: date) -> int:
    """시그널 날짜(YYYY-MM-DD)로부터 today까지 경과 일수. 미래 날짜는 0으로 취급."""
    sig = datetime.strptime(signal_date, "%Y-%m-%d").date()
    return max(0, (today - sig).days)


def _latest_signal() -> Path:
    sigs = sorted(SIGNAL_DIR.glob("signal_*.json"))
    if not sigs:
        raise SystemExit("[오류] signals/ 없음 — 먼저 generate_signal.py 실행")
    return sigs[-1]


def _load_signal(path: Path) -> tuple[dict, str]:
    """시그널 JSON에서 weights·date 추출. 누락·손상은 clean SystemExit로."""
    try:
        sig = json.loads(path.read_text())
    except FileNotFoundError:
        raise SystemExit(f"[오류] 시그널 파일 없음: {path}")
    except json.JSONDecodeError as e:
        raise SystemExit(f"[오류] 시그널 JSON 파싱 실패: {path} ({e})")
    weights, date = sig.get("weights"), sig.get("date")
    if not isinstance(weights, dict) or not weights:
        raise SystemExit(f"[오류] 시그널에 weights 없음/빈값: {path}")
    if not isinstance(date, str):
        raise SystemExit(f"[오류] 시그널 date 형식 오류: {path}")
    return sig, date


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
    if res.rejected:
        print(f"  거부(개별): {res.rejected}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--signal", default=None, help="시그널 JSON 경로(생략 시 최신)")
    ap.add_argument("--budget", type=_positive_float, default=700.0, help="봇 매수 예산 상한(USD)")
    ap.add_argument("--min-order", type=_positive_float, default=1.0, help="최소 주문금액(USD, Phase 0 실측 전 placeholder)")
    ap.add_argument("--state", default=str(LOG_DIR / "managed_state.json"), help="화이트리스트 상태 파일")
    ap.add_argument("--kill-switch", default=str(ROOT / "KILL"), help="이 파일 존재 시 발주 중단")
    ap.add_argument("--max-orders", type=_positive_int, default=60, help="일일 주문건수 상한(서킷브레이커)")
    ap.add_argument("--max-loss", type=_positive_float, default=700.0, help="일일 손실 상한(USD, 손익 배선은 Phase 0)")
    ap.add_argument("--max-age-days", type=_positive_int, default=5,
                    help="시그널 최대 허용 경과일(미국 거래일 기준). 초과 시 실발주 거부(dry-run은 경고).")
    ap.add_argument("--confirm", action="store_true", help="실발주. 없으면 dry-run.")
    args = ap.parse_args()

    sig_path = Path(args.signal) if args.signal else _latest_signal()
    sig, date_raw = _load_signal(sig_path)
    weights, date = sig["weights"], date_raw.replace("-", "")

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

    # 시그널 신선도 가드: 오래된 시그널로 발주 방지(주간 cron에서 파이프라인 실패 시 지난
    # 시그널 재사용 차단). 실발주는 거부, dry-run은 경고만(계획 검토 허용).
    age = _signal_age_days(date_raw, datetime.now(US_MARKET_TZ).date())
    if age > args.max_age_days:
        warn = (f"시그널 {sig_path.name} 이 {age}일 경과 (> {args.max_age_days}일) "
                "— 데이터/시그널 파이프라인 실패 가능성.")
        if not dry_run:
            raise SystemExit(f"[중단] {warn}\n  최신 시그널 재생성 또는 --max-age-days 조정 후 재실행.")
        print(f"⚠️ {warn} dry-run이라 계획만 표시.")

    res = runner.run(weights, rebalance_date=date, dry_run=dry_run)
    _print_result(res, dry_run)

    if dry_run:
        print("\n⚠️ dry-run(실발주 없음). 실발주는 정규장 시간에 --confirm (토스 키 필요).")


def _cli() -> None:
    """CLI 경계: 라이브러리 예외(TossError·ExecutionError)를 clean 메시지·exit로 변환(개선10).
    서킷브레이커·kill switch(ExecutionError)도 traceback 없이 정지 메시지로."""
    try:
        main()
    except (TossError, ExecutionError) as e:
        raise SystemExit(str(e))


if __name__ == "__main__":
    _cli()
