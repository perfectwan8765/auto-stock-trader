"""Phase 3 — Alpha158 + LightGBM 학습·백테스트 러너 (config 구동).

주어진 workflow config를 실행하고 4개 게이트를 검증한다:
  1) Alpha158 158피처 계산  2) 라벨이 주간 5일 fwd override  3) 백테스트 주간 스텝
  4) IC/RankIC/포트폴리오 지표 산출.

  ① 배선 스모크:  --config workflow_config_alpha158_lgb_pilot.yaml  (41종목, 지표=배선용)
  ② 엣지 판독:    --config workflow_config_alpha158_lgb_sp500.yaml  (S&P500 전체, SPY 벤치)

실행:  .venv/bin/python scripts/model_backtest/run_backtest.py [--config <yaml>]
"""
from __future__ import annotations

import argparse
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
DEFAULT_CONFIG = "workflow_config_alpha158_lgb_pilot.yaml"


def _load_config(path: Path) -> dict:
    with path.open() as f:
        return yaml.YAML(typ="safe", pure=True).load(f)


def _gate(ok: bool, msg: str) -> bool:
    print(f"   {'✅' if ok else '❌'} {msg}")
    return ok


def _ensure_tradable_instruments(provider_uri: Path, market: str, benchmark: str | None) -> None:
    """벤치마크(SPY 등)를 매매 유니버스에서 제외한 instruments/<market>.txt 생성.

    dump_bin은 all.txt(전체, SPY 포함)만 만든다. 벤치 전용 종목을 랭킹·매매에서 빼려면
    all.txt에서 benchmark를 제외한 별도 instruments 파일이 필요. all.txt 갱신 반영 위해 매번 재생성.
    """
    if market == "all" or not benchmark:
        return
    inst_dir = provider_uri / "instruments"
    all_txt = inst_dir / "all.txt"
    if not all_txt.exists():
        raise SystemExit(f"[오류] {all_txt} 없음 — 먼저 Phase 2 파이프라인으로 dump 필요")
    all_lines = all_txt.read_text().splitlines()
    kept = [ln for ln in all_lines if ln.strip() and ln.split("\t")[0].upper() != benchmark.upper()]
    (inst_dir / f"{market}.txt").write_text("\n".join(kept) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=DEFAULT_CONFIG, help="model_backtest 디렉토리 내 workflow config 파일명(또는 경로)")
    args = ap.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.is_absolute() and not cfg_path.exists():
        cfg_path = Path(__file__).with_name(args.config)
    cfg = _load_config(cfg_path)

    init_kwargs = dict(cfg["qlib_init"])
    provider_uri = ROOT / init_kwargs["provider_uri"]
    init_kwargs["provider_uri"] = str(provider_uri)

    market = cfg["task"]["dataset"]["kwargs"]["handler"]["kwargs"]["instruments"]
    benchmark = cfg["port_analysis_config"]["backtest"].get("benchmark")
    _ensure_tradable_instruments(provider_uri, market, benchmark)

    qlib.init(**init_kwargs)

    # 벤치마크: config에 지정(SPY 등) 있으면 그대로, null이면 매매 유니버스 등가중 주입.
    if not benchmark:
        eqw = D.list_instruments(D.instruments(market), as_list=True)
        cfg["port_analysis_config"]["backtest"]["benchmark"] = eqw
        print(f"ℹ️  벤치마크 미지정 → {market} {len(eqw)}종목 등가중 주입")
    else:
        print(f"ℹ️  벤치마크 = {benchmark}")

    dataset: DatasetH = init_instance_by_config(cfg["task"]["dataset"])
    model = init_instance_by_config(cfg["task"]["model"])

    exp_name = cfg_path.stem
    with R.start(experiment_name=exp_name):
        print("\n🔧 학습 시작 (valid early-stop, seed 고정)")
        model.fit(dataset)  # R.log_metrics가 활성 recorder에 기록되도록 컨텍스트 안에서 학습

        recorder = R.get_recorder()
        SignalRecord(model=model, dataset=dataset, recorder=recorder).generate()
        SigAnaRecord(recorder=recorder, ana_long_short=False, ann_scaler=52).generate()
        PortAnaRecord(recorder=recorder, config=cfg["port_analysis_config"]).generate()

        _gates(cfg, market, dataset, recorder)


def _gates(cfg: dict, market: str, dataset: DatasetH, recorder) -> None:
    print("\n" + "=" * 60 + "\n게이트\n" + "=" * 60)
    passed = []

    # 1) Alpha158 158개 피처 계산
    feat = dataset.prepare("test", col_set="feature", data_key=DataHandlerLP.DK_I)
    passed.append(_gate(feat.shape[1] == 158,
                        f"Alpha158 피처 {feat.shape[1]}개 (기대 158), NaN 없음={not feat.isna().any().any()}"))

    # 2) 라벨이 주간 5거래일 fwd로 override됐나 (익일 라벨이 아니라)
    raw_label = dataset.prepare("test", col_set="label", data_key=DataHandlerLP.DK_R).iloc[:, 0].dropna()
    seg = cfg["task"]["dataset"]["kwargs"]["segments"]["test"]
    insts = D.instruments(market)
    lv = raw_label.index.names  # D.features는 (instrument, datetime), 라벨은 (datetime, instrument) → 맞춤
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
        n_inst = len(D.list_instruments(D.instruments(market), as_list=True))
        note = ("지표는 배선 확인용(랭킹 무의미)" if n_inst < 100
                else "유니버스 충분 → 지표로 엣지 판독 가능. Sharpe 4+면 과최적 의심")
        print(f"✅ PASS ({market}, {n_inst}종목). {note}")
    else:
        print("❌ 실패 — 위 게이트 확인")
        sys.exit(1)


if __name__ == "__main__":
    main()
