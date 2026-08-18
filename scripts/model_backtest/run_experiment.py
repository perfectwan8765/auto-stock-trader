"""모델/핸들러 실험 러너 — run_backtest의 Alpha158 전용 **배선** 게이트 없이 임의 config로
학습→백테스트→IC/RankIC·포트지표 출력. **학습 게이트(null 대비)는 여기도 적용한다** —
그건 핸들러·모델에 무관하고, 이 경로가 대안 모델이 지나는 길이라 빠지면 정작 비교 대상이
검증 없이 표에 오른다. Alpha360+GRU 등 대안 비교용(공정 비교는
라벨·주간스텝·비용·세그먼트를 베이스라인과 동일하게 둔 config로).

실행: OMP_NUM_THREADS=1 .venv/bin/python scripts/model_backtest/run_experiment.py --config <yaml>
⚠️ macOS: torch↔lightgbm OpenMP 런타임 충돌로 DL 학습이 무음 크래시 → OMP_NUM_THREADS=1 필수.
"""
from __future__ import annotations

import argparse

from _common import check_learning, load_config, qlib_init_kwargs  # qlib import 전 MLFLOW env

import qlib
from qlib.utils import init_instance_by_config
from qlib.workflow import R
from qlib.workflow.record_temp import PortAnaRecord, SigAnaRecord, SignalRecord

from run_backtest import _ensure_tradable_instruments


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--seed", type=int, default=None, help="모델 시드 오버라이드(다중시드 비교용)")
    args = ap.parse_args()

    cfg, cfg_path = load_config(args.config)
    if args.seed is not None:
        cfg["task"]["model"]["kwargs"]["seed"] = args.seed
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
        evals_result: dict = {}
        model.fit(dataset, evals_result=evals_result)
        rec = R.get_recorder()
        SignalRecord(model=model, dataset=dataset, recorder=rec).generate()
        SigAnaRecord(recorder=rec, ana_long_short=False, ann_scaler=52).generate()
        PortAnaRecord(recorder=rec, config=cfg["port_analysis_config"]).generate()

        ic = rec.load_object("sig_analysis/ic.pkl")
        ric = rec.load_object("sig_analysis/ric.pkl")
        risk = rec.load_object("portfolio_analysis/port_analysis_1week.pkl")
        feat = dataset.prepare("test", col_set="feature")

        seed = cfg["task"]["model"]["kwargs"].get("seed")
        exc = risk.loc[("excess_return_with_cost", "annualized_return"), "risk"]
        ir = risk.loc[("excess_return_with_cost", "information_ratio"), "risk"]
        mdd = risk.loc[("excess_return_with_cost", "max_drawdown"), "risk"]

        print("\n" + "=" * 60 + "\n게이트 — 학습 (모델이 실제로 학습됐나)\n" + "=" * 60)
        learned = check_learning(cfg, model, evals_result)

        print("\n" + "=" * 60)
        print(f"피처 수: {feat.shape[1]}")
        print(f"IC={ic.mean():.4f}  RankIC={ric.mean():.4f}")
        print(risk)
        # 다중시드 집계용 파싱 라인
        # gate를 SUMMARY에 넣는 이유: 다중시드 집계가 이 줄만 파싱한다. 게이트 실패를
        # 여기 안 적으면 학습되지 않은 시드의 초과수익이 집계표에 그대로 올라간다.
        print(f"SUMMARY | seed={seed} | gate={'PASS' if learned else 'FAIL'} "
              f"| IC={ic.mean():.4f} | RankIC={ric.mean():.4f} "
              f"| exc_wc={exc:.4f} | IR_wc={ir:.4f} | MDD_wc={mdd:.4f}")

    # 지표를 다 출력한 뒤에 종료코드를 세운다 — 먼저 죽으면 그 시행의 기록이 사라진다.
    # 정지가 아니라 승격 차단이다(trial-accounting.md §10-11).
    if not learned:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
