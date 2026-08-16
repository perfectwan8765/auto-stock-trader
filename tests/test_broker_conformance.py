"""어댑터가 Broker Protocol을 실제로 만족하는지 확인한다.

Protocol은 선언일 뿐 강제되지 않았다. SyntheticBroker(dry_run_rebalance.py)는 읽기 5종 중
일부만 구현한 채로 오래 굴러갔다 — 보유가 비어 매도 주문이 안 생기니 없는 메서드가 우연히
호출되지 않았을 뿐이다. Protocol을 좁히는 작업의 효과가 "만족시키기 쉬워진다"인데,
만족 여부를 아무도 안 보면 그 효과가 확인되지 않는다.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from execution.interface import Broker
from toss.broker import TossBroker


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_toss_broker_satisfies_protocol():
    assert isinstance(TossBroker(client=object()), Broker)


def test_test_double_satisfies_protocol(make_broker):
    assert isinstance(make_broker(), Broker)


def test_synthetic_broker_satisfies_protocol():
    """오프라인 데모 브로커도 계약을 지킨다 — 종전에는 지키지 않았다."""
    root = Path(__file__).resolve().parent.parent
    mod = _load(root / "scripts" / "model_backtest" / "dry_run_rebalance.py", "dry_run_demo")
    assert isinstance(mod.SyntheticBroker(), Broker)
