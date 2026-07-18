"""Phase 3 A1++ — GBDT 피어 모델 valid 프로브 (LightGBM vs XGBoost vs DoubleEnsemble).

질문: "LightGBM이 신호를 남기고 있나? 다른 GBDT가 더 뽑나?"
라벨 고정(config 주간 5일 fwd), 정규화 동급(med)으로 **모델만** 바꿔 valid IC 비교.

⚠️ 규율: test 미관측(②서 1회). valid 지표로만. 백테스트 없음.
   웹 캘리브레이션: qlib 리더보드 GBDT는 다 같은 대역(IC 0.045~0.050, CN·일간). US·주간선 압축 예상.

실행:  .venv/bin/python scripts/model_backtest/probe_models.py [--config <yaml>]
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")

import pandas as pd
import ruamel.yaml as yaml

import qlib
from qlib.contrib.model.gbdt import LGBModel
from qlib.contrib.model.xgboost import XGBModel
from qlib.contrib.model.double_ensemble import DEnsembleModel
from qlib.data.dataset import DatasetH
from qlib.data.dataset.handler import DataHandlerLP
from qlib.utils import init_instance_by_config

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = "workflow_config_alpha158_lgb_sp500.yaml"


def _load_config(path: Path) -> dict:
    with path.open() as f:
        return yaml.YAML(typ="safe", pure=True).load(f)


def calc_valid_ic(pred: pd.Series, label: pd.Series) -> tuple[float, float, float]:
    df = pd.concat([pred.rename("pred"), label.rename("label")], axis=1).dropna()
    g = df.groupby(level="datetime")
    ic = g.apply(lambda x: x["pred"].corr(x["label"]))
    ric = g.apply(lambda x: x["pred"].corr(x["label"], method="spearman"))
    return ic.mean(), ric.mean(), ic.mean() / ic.std()


def build_models():
    """정규화 동급(med): L1≈10, L2≈50, depth 6~8, lr 0.02~0.05. 공정 비교."""
    return {
        "lightgbm_med": LGBModel(loss="mse", num_threads=8, seed=2026,
                                 early_stopping_rounds=50, num_boost_round=1000,
                                 num_leaves=128, max_depth=8, learning_rate=0.02,
                                 lambda_l1=10.0, lambda_l2=50.0, colsample_bytree=0.8, subsample=0.8),
        "xgboost": XGBModel(objective="reg:squarederror", eta=0.05, max_depth=6,
                            subsample=0.8, colsample_bytree=0.8, **{"lambda": 50.0, "alpha": 10.0},
                            nthread=8, seed=2026),
        "double_ensemble": DEnsembleModel(base_model="gbm", loss="mse", num_models=6,
                                          decay=0.5,  # qlib DE는 decay 미설정 시 decay**k에서 크래시
                                          epochs=200, early_stopping_rounds=50,
                                          num_leaves=128, max_depth=8, learning_rate=0.02,
                                          lambda_l1=10.0, lambda_l2=50.0, colsample_bytree=0.8,
                                          subsample=0.8, num_threads=8, seed=2026),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    args = ap.parse_args()
    cfg_path = Path(args.config)
    if not cfg_path.is_absolute() and not cfg_path.exists():
        cfg_path = Path(__file__).with_name(args.config)
    cfg = _load_config(cfg_path)

    init_kwargs = dict(cfg["qlib_init"])
    init_kwargs["provider_uri"] = str(ROOT / init_kwargs["provider_uri"])
    qlib.init(**init_kwargs)

    print("🔧 dataset 빌드(1회, 주간 5일 라벨)...")
    dataset: DatasetH = init_instance_by_config(cfg["task"]["dataset"])
    label = dataset.prepare("valid", col_set="label", data_key=DataHandlerLP.DK_R).iloc[:, 0]

    rows = []
    for name, model in build_models().items():
        print(f"   학습: {name} ...")
        model.fit(dataset)
        pred = model.predict(dataset, segment="valid")
        ic, ric, icir = calc_valid_ic(pred, label)
        rows.append((name, ic, ric, icir))
        print(f"   {name:16s} IC={ic:+.4f} RankIC={ric:+.4f} ICIR={icir:+.3f}")

    res = pd.DataFrame(rows, columns=["model", "valid_IC", "valid_RankIC", "valid_ICIR"])
    res = res.sort_values("valid_RankIC", ascending=False).reset_index(drop=True)
    print("\n" + "=" * 60 + "\n모델별 valid 신호 (라벨 고정, test 미관측)\n" + "=" * 60)
    print(res.to_string(index=False))
    best = res.iloc[0]
    print(f"\n👉 최고: {best['model']} (valid RankIC={best['valid_RankIC']:+.4f})")
    print("   모두 노이즈급(RankIC<0.015)이면 → 모델 원인 아님 확정. 배관(Phase 5)+Phase 0 실측 대기.")


if __name__ == "__main__":
    main()
