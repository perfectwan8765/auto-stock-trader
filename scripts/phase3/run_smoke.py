"""Phase 3 ① — Alpha158 + LightGBM 배선 스모크 러너.

workflow_config_alpha158_lgb_pilot.yaml을 실행하고 4개 스모크 게이트를 검증한다.
목적: "돌아가나 / Alpha158 지표 계산되나 / 라벨이 주간 fwd로 override됐나 / 백테스트가
주간 스텝으로 도나". 41종목 지표는 배선 확인용 — 전략 우열 판단 금지(B3).

실행:  .venv/bin/python scripts/phase3/run_smoke.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# 신버전 mlflow는 파일스토어 tracking 백엔드를 기본 차단 → 로컬 실험 기록에 opt-in.
os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")

import numpy as np
import pandas as pd
import ruamel.yaml as yaml

import qlib
from qlib.data import D
from qlib.data.dataset import DatasetH
from qlib.data.dataset.handler import DataHandlerLP
from qlib.utils import init_instance_by_config
from qlib.workflow import R
from qlib.workflow.record_temp import PortAnaRecord, SigAnaRecord, SignalRecord

ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path(__file__).with_name("workflow_config_alpha158_lgb_pilot.yaml")


def _load_config() -> dict:
    with CONFIG.open() as f:
        return yaml.YAML(typ="safe", pure=True).load(f)


def _gate(ok: bool, msg: str) -> bool:
    print(f"   {'✅' if ok else '❌'} {msg}")
    return ok


def main() -> None:
    cfg = _load_config()

    # provider_uri는 레포 루트 기준 상대경로 → 절대경로로.
    init_kwargs = dict(cfg["qlib_init"])
    init_kwargs["provider_uri"] = str(ROOT / init_kwargs["provider_uri"])
    qlib.init(**init_kwargs)

    # ① 벤치마크 = 41종목 등가중(실데이터). SPY 대비는 ② 확장(B3).
    universe = D.list_instruments(D.instruments("all"), as_list=True)
    cfg["port_analysis_config"]["backtest"]["benchmark"] = universe

    dataset: DatasetH = init_instance_by_config(cfg["task"]["dataset"])
    model = init_instance_by_config(cfg["task"]["model"])

    with R.start(experiment_name="phase3_smoke_alpha158_lgb_pilot"):
        print("\n🔧 학습 시작 (valid early-stop, seed 고정)")
        model.fit(dataset)  # R.log_metrics가 활성 recorder에 기록되도록 컨텍스트 안에서 학습

        recorder = R.get_recorder()
        SignalRecord(model=model, dataset=dataset, recorder=recorder).generate()
        SigAnaRecord(recorder=recorder, ana_long_short=False, ann_scaler=52).generate()
        PortAnaRecord(recorder=recorder, config=cfg["port_analysis_config"]).generate()

        _smoke_gates(cfg, dataset, recorder)


def _smoke_gates(cfg: dict, dataset: DatasetH, recorder) -> None:
    print("\n" + "=" * 60 + "\n스모크 게이트\n" + "=" * 60)
    passed = []

    # 1) Alpha158 158개 피처 계산
    feat = dataset.prepare("test", col_set="feature", data_key=DataHandlerLP.DK_I)
    passed.append(_gate(feat.shape[1] == 158,
                        f"Alpha158 피처 {feat.shape[1]}개 (기대 158), NaN 없음={not feat.isna().any().any()}"))

    # 2) 라벨이 주간 5거래일 fwd로 override됐나 (익일 라벨이 아니라)
    #    dataset raw 라벨을 D.features로 계산한 -6판/-2판과 상관 비교.
    raw_label = dataset.prepare("test", col_set="label", data_key=DataHandlerLP.DK_R).iloc[:, 0].dropna()
    seg = cfg["task"]["dataset"]["kwargs"]["segments"]["test"]
    insts = D.instruments("all")
    # D.features 인덱스는 (instrument, datetime), dataset 라벨은 (datetime, instrument) → 레벨 순서 맞춤.
    lv = raw_label.index.names
    wk = D.features(insts, ["Ref($close,-6)/Ref($close,-1)-1"], seg[0], seg[1]).iloc[:, 0].reorder_levels(lv)
    dy = D.features(insts, ["Ref($close,-2)/Ref($close,-1)-1"], seg[0], seg[1]).iloc[:, 0].reorder_levels(lv)
    j = pd.DataFrame({"raw": raw_label, "wk": wk, "dy": dy}).dropna()
    corr_wk, corr_dy = j["raw"].corr(j["wk"]), j["raw"].corr(j["dy"])
    passed.append(_gate(corr_wk > 0.99 and corr_wk > corr_dy,
                        f"라벨=주간5일fwd (corr wk={corr_wk:.3f} > 익일 dy={corr_dy:.3f})"))

    # 3) 백테스트가 주간 스텝으로 도나 (리포트 행수 ≈ 주수, 거래일수 아님)
    report = recorder.load_object("portfolio_analysis/report_normal_1week.pkl")
    n_steps, n_days = len(report), len(D.calendar(seg[0], seg[1]))
    passed.append(_gate(n_days * 0.15 < n_steps < n_days * 0.30,
                        f"주간 스텝 {n_steps} (거래일 {n_days}, 기대 ~{n_days // 5})"))

    # 4) IC/RankIC/포트폴리오 지표 산출됨
    ic = recorder.load_object("sig_analysis/ic.pkl")
    ric = recorder.load_object("sig_analysis/ric.pkl")
    risk = recorder.load_object("portfolio_analysis/port_analysis_1week.pkl")
    print(f"\n   IC={ic.mean():.4f}  RankIC={ric.mean():.4f}")
    print(risk)
    passed.append(_gate(np.isfinite(ic.mean()) and not risk.empty, "IC/RankIC/포트폴리오 지표 산출됨"))

    print("\n" + "=" * 60)
    if all(passed):
        print("✅ ① 배선 스모크 PASS. 지표는 배선 확인용(41종목 랭킹 무의미) — 엣지 판독은 ② 확장.")
    else:
        print("❌ 스모크 실패 — 위 게이트 확인")
        sys.exit(1)


if __name__ == "__main__":
    main()
