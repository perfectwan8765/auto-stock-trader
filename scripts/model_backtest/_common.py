"""model_backtest 공통: config 로딩·qlib.init 준비.

live 스크립트(run_backtest·generate_signal)가 공유. `import qlib`보다 위에서 import 할 것
(MLFLOW 환경변수를 qlib 로드 전 설정).
"""
from __future__ import annotations

import os
from pathlib import Path

# 신버전 mlflow는 파일스토어 tracking 백엔드를 기본 차단 → 로컬 실험 기록에 opt-in.
# qlib import 전에 설정돼야 하므로 이 모듈 로드 시점(=qlib import 전)에 실행.
os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")

import ruamel.yaml as yaml

ROOT = Path(__file__).resolve().parents[2]


def load_config(config_arg: str) -> tuple[dict, Path]:
    """config 경로 해석(절대/상대/파일명) + YAML 파싱. (cfg, 해석된 경로) 반환."""
    p = Path(config_arg)
    if not p.is_absolute() and not p.exists():
        p = Path(__file__).with_name(config_arg)
    with p.open() as f:
        return yaml.YAML(typ="safe", pure=True).load(f), p


def qlib_init_kwargs(cfg: dict) -> tuple[dict, Path]:
    """cfg['qlib_init']의 provider_uri를 ROOT 기준 절대경로화. (qlib.init kwargs, provider_uri) 반환.

    provider_uri를 별도로 돌려줘 호출부가 qlib.init 전에 쓸 수 있게 한다
    (run_backtest는 init 전 instruments 파일 생성에 필요)."""
    kw = dict(cfg["qlib_init"])
    provider_uri = ROOT / kw["provider_uri"]
    kw["provider_uri"] = str(provider_uri)
    return kw, provider_uri
