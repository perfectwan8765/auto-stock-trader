"""pytest 공통 설정: src/를 import 경로에 추가.

pytest가 테스트 수집 전 conftest.py를 먼저 로드 → 각 테스트 파일의 sys.path 부트스트랩 중복 제거.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
