"""execution 레이어 예외 (브로커 비의존 — toss.errors와 독립).

안전장치 정지 신호. CLI/cron 러너가 잡아 정지·알림. 개선10 원칙대로 SystemExit은 CLI에서만.
"""
from __future__ import annotations


class ExecutionError(Exception):
    """execution 레이어 공통 베이스."""


class KillSwitchActive(ExecutionError):
    """kill switch 파일 존재 → 발주 중단."""


class CircuitBreakerTripped(ExecutionError):
    """일일 주문건수·손실 상한 초과 → 발주 차단."""
