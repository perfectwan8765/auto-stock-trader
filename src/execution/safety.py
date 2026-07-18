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
    """일일 주문건수·손실 상한. 발주 루프에서 각 주문 전 `guard()` 호출."""

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
