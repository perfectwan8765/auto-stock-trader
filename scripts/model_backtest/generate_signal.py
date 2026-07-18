"""Phase 4 — 주간 목표 포트폴리오 시그널 생성.

학습 모델로 최신 거래일을 예측 → 상위 K종목 등가중 목표비중 → signals/signal_<date>.json.
이 JSON이 Phase 5 execution.compute_rebalance의 target_weights 입력.

⚠️ 현 베이스라인은 엣지 미검출(Phase 3 A1) → 이 시그널은 **배관/데모용, 실알파 아님**.
   실 가동 시엔 최신일까지 재학습 필요(여기선 config의 train/valid로 학습 후 test 마지막일 예측).

실행:  .venv/bin/python scripts/model_backtest/generate_signal.py [--config <yaml>] [--topk 20]
"""
from __future__ import annotations

import argparse
import json

from _common import ROOT, load_config, qlib_init_kwargs  # qlib import 전(MLFLOW env 설정)

import qlib
from qlib.data.dataset import DatasetH
from qlib.utils import init_instance_by_config

DEFAULT_CONFIG = "workflow_config_alpha158_lgb_sp500.yaml"
SIGNAL_DIR = ROOT / "signals"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--topk", type=int, default=20)
    args = ap.parse_args()

    cfg, cfg_path = load_config(args.config)
    init_kwargs, _ = qlib_init_kwargs(cfg)
    qlib.init(**init_kwargs)

    print("🔧 dataset 빌드 + 학습(valid early-stop, seed 고정)...")
    dataset: DatasetH = init_instance_by_config(cfg["task"]["dataset"])
    model = init_instance_by_config(cfg["task"]["model"])
    model.fit(dataset)

    pred = model.predict(dataset, segment="test")  # (datetime, instrument)
    latest = pred.index.get_level_values("datetime").max()
    latest_scores = pred.xs(latest, level="datetime").sort_values(ascending=False)

    k = args.topk
    top = latest_scores.head(k)
    weight = round(1.0 / k, 8)
    weights = {sym: weight for sym in top.index}

    date_str = latest.strftime("%Y-%m-%d")
    signal = {
        "date": date_str,
        "strategy": cfg_path.stem,
        "topk": k,
        "weights": weights,  # 등가중 롱온리, 비중합≈1
        "generated_from": {"config": cfg_path.name, "model": "LGBModel", "seed": 2026},
        "note": "엣지 미검출 베이스라인(Phase 3 A1) — 배관/데모용, 실알파 아님",
    }

    SIGNAL_DIR.mkdir(exist_ok=True)
    out = SIGNAL_DIR / f"signal_{date_str.replace('-', '')}.json"
    out.write_text(json.dumps(signal, indent=2, ensure_ascii=False) + "\n")

    # 검증(계획서 Phase 4 기준): K종목·비중합=1
    wsum = sum(weights.values())
    ok = len(weights) == k and abs(wsum - 1.0) < 1e-6
    print(f"\n{'✅' if ok else '❌'} 시그널 생성: {out.relative_to(ROOT)}")
    print(f"   date={date_str}  topk={k}  비중합={wsum:.6f}")
    print(f"   상위 5: {list(weights)[:5]}")
    if not ok:
        raise SystemExit(f"[검증 실패] 종목수 {len(weights)}≠{k} 또는 비중합 {wsum}≠1")


if __name__ == "__main__":
    main()
