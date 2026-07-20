"""모델/핸들러 실험 러너 — run_backtest의 Alpha158 전용 게이트 없이 임의 config로
학습→백테스트→IC/RankIC·포트지표만 출력. Alpha360+GRU 등 대안 비교용(공정 비교는
라벨·주간스텝·비용·세그먼트를 베이스라인과 동일하게 둔 config로).

실행: OMP_NUM_THREADS=1 .venv/bin/python scripts/model_backtest/run_experiment.py --config <yaml>
⚠️ macOS: torch↔lightgbm OpenMP 런타임 충돌로 DL 학습이 무음 크래시 → OMP_NUM_THREADS=1 필수.
"""
from __future__ import annotations

import argparse

from _common import load_config, qlib_init_kwargs  # qlib import 전 MLFLOW env

import qlib
from qlib.utils import init_instance_by_config
from qlib.workflow import R
from qlib.workflow.record_temp import PortAnaRecord, SigAnaRecord, SignalRecord

from run_backtest import _ensure_tradable_instruments


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg, cfg_path = load_config(args.config)
    init_kwargs, provider_uri = qlib_init_kwargs(cfg)
    market = cfg["task"]["dataset"]["kwargs"]["handler"]["kwargs"]["instruments"]
    benchmark = cfg["port_analysis_config"]["backtest"].get("benchmark")
    _ensure_tradable_instruments(provider_uri, market, benchmark)

    qlib.init(**init_kwargs)
    print(f"ℹ️  벤치마크 = {benchmark} · config = {cfg_path.name}")

    dataset = init_instance_by_config(cfg["task"]["dataset"])
    model = init_instance_by_config(cfg["task"]["model"])

    with R.start(experiment_name=cfg_path.stem):
        print("\n🔧 학습 시작")
        model.fit(dataset)
        rec = R.get_recorder()
        SignalRecord(model=model, dataset=dataset, recorder=rec).generate()
        SigAnaRecord(recorder=rec, ana_long_short=False, ann_scaler=52).generate()
        PortAnaRecord(recorder=rec, config=cfg["port_analysis_config"]).generate()

        ic = rec.load_object("sig_analysis/ic.pkl")
        ric = rec.load_object("sig_analysis/ric.pkl")
        risk = rec.load_object("portfolio_analysis/port_analysis_1week.pkl")
        feat = dataset.prepare("test", col_set="feature")

        print("\n" + "=" * 60)
        print(f"피처 수: {feat.shape[1]}")
        print(f"IC={ic.mean():.4f}  RankIC={ric.mean():.4f}")
        print(risk)


if __name__ == "__main__":
    main()
