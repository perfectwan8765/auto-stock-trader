"""브로커 비의존 리밸런싱·주문 관리(OMS) 로직.

`src/toss`(브로커 transport)와 분리 — 리밸 계산·멱등키·최소금액·자금이월·안전장치는
브로커에 종속되지 않는다. 브로커는 `interface.Broker` 프로토콜로 주입 → mock으로 단위테스트.
"""
from .interface import Broker, OrderIntent, RebalanceParams
from .rebalance import compute_rebalance, make_client_order_id

__all__ = ["Broker", "OrderIntent", "RebalanceParams", "compute_rebalance", "make_client_order_id"]
