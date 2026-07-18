"""발주 안전장치 (개선4): kill switch · 서킷브레이커.

- kill switch: 지정 파일이 존재하면 즉시 중단(외부에서 `touch`로 정지).
- 서킷브레이커: 일일 주문건수·손실 상한 초과 시 발주 차단.
자동화(cron)가 라이브러리 예외(개선10)와 함께 이 장치로 폭주를 막는다.
"""
from __future__ import annotations

from pathlib import Path

from .errors import CircuitBreakerTripped, KillSwitchActive


def check_kill_switch(path: str | Path) -> None:
    """kill switch 파일 존재 시 KillSwitchActive. 존재 자체가 정지 신호."""
    if Path(path).exists():
        raise KillSwitchActive(f"kill switch 활성: {path} 존재 → 발주 중단")


class CircuitBreaker:
    """일일 주문건수·손실 상한.

    발주 루프 사용 패턴(러너):
        cb.guard()            # 발주 직전 상한 확인(초과 시 CircuitBreakerTripped)
        broker.place(intent)
        cb.record_order()     # 발주 성공 후 카운트
        cb.record_loss(usd)   # 실현손실 확인 시 누적(다음 guard에서 반영)
    상태는 인메모리(단일 실행 한정). 프로세스 재기동 넘는 지속은 Phase 6에서 파일 상태로.
    """

    def __init__(self, max_orders_per_day: int, max_loss_usd: float):
        self.max_orders_per_day = max_orders_per_day
        self.max_loss_usd = max_loss_usd
        self.orders_today = 0
        self.realized_loss_usd = 0.0

    def guard(self) -> None:
        if self.orders_today >= self.max_orders_per_day:
            raise CircuitBreakerTripped(
                f"일일 주문건수 상한 초과: {self.orders_today}/{self.max_orders_per_day}"
            )
        if self.realized_loss_usd >= self.max_loss_usd:
            raise CircuitBreakerTripped(
                f"일일 손실 상한 초과: ${self.realized_loss_usd:.2f}/${self.max_loss_usd:.2f}"
            )

    def record_order(self) -> None:
        self.orders_today += 1

    def record_loss(self, usd: float) -> None:
        if usd > 0:
            self.realized_loss_usd += usd
