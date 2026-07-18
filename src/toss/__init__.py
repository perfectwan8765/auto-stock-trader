"""토스증권 OpenAPI 어댑터 공통 모듈.

Phase 0 실측 툴킷에서 사용하며, Phase 5 발주 어댑터에서 재사용한다.
"""
from .errors import TossApiError, TossAuthError, TossConfigError, TossError

__all__ = ["TossError", "TossConfigError", "TossAuthError", "TossApiError"]
