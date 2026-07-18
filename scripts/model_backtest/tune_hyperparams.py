"""Phase 3 A1 — LightGBM 하이퍼파라미터 재튜닝 (valid 전용).

②에서 CN(CSI300) 튜닝값이 US 500·주간라벨엔 과도 정규화 → LGB 즉시 early-stop([1]) 언더피팅.
여기선 정규화·트리 파라미터를 낮춘 후보들을 학습하고 **valid IC/RankIC/best_iter**로 비교한다.

⚠️ 규율: test는 ②에서 이미 1회 관측 → 여기서 **재관측 금지**. valid 지표로만 후보 선택.
   백테스트/PortAnaRecord 실행 안 함. dataset은 1회 빌드 후 후보 간 재사용(피처 동일, 모델만 교체).

실행:  .venv/bin/python scripts/model_backtest/tune_hyperparams.py [--config <yaml>]
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
from qlib.data.dataset import DatasetH
from qlib.data.dataset.handler import DataHandlerLP
from qlib.utils import init_instance_by_config

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = "workflow_config_alpha158_lgb_sp500.yaml"

# 후보: baseline(CN) + 정규화·트리 완화 5종. seed 고정, lr·early_stop 공통 축은 후보별 명시.
# 원리: L1/L2를 크게 낮춰 즉시 early-stop 해소, leaves/depth로 용량 조절.
CANDIDATES = {
    "baseline_cn":  dict(num_leaves=210, max_depth=8, learning_rate=0.0421, lambda_l1=205.7, lambda_l2=580.98, colsample_bytree=0.8879, subsample=0.8789),
    "light_reg":    dict(num_leaves=64,  max_depth=6, learning_rate=0.05,   lambda_l1=1.0,   lambda_l2=1.0,    colsample_bytree=0.8,    subsample=0.8),
    "med_reg":      dict(num_leaves=128, max_depth=8, learning_rate=0.02,   lambda_l1=10.0,  lambda_l2=50.0,   colsample_bytree=0.8,    subsample=0.8),
    "very_light":   dict(num_leaves=31,  max_depth=5, learning_rate=0.05,   lambda_l1=0.0,   lambda_l2=0.0,    colsample_bytree=0.8,    subsample=0.8),
    "low_lr_mid":   dict(num_leaves=64,  max_depth=6, learning_rate=0.01,   lambda_l1=20.0,  lambda_l2=100.0,  colsample_bytree=0.8,    subsample=0.8),
    "shallow_reg":  dict(num_leaves=48,  max_depth=5, learning_rate=0.03,   lambda_l1=5.0,   lambda_l2=20.0,   colsample_bytree=0.85,   subsample=0.85),
}
COMMON = dict(loss="mse", num_threads=8, seed=2026, early_stopping_rounds=50, num_boost_round=1000)


def _load_config(path: Path) -> dict:
    with path.open() as f:
        return yaml.YAML(typ="safe", pure=True).load(f)


def calc_valid_ic(pred: pd.Series, label: pd.Series) -> tuple[float, float, float]:
    """valid IC(pearson) / RankIC(spearman) / ICIR. 일자별 횡단상관 후 평균."""
    df = pd.concat([pred.rename("pred"), label.rename("label")], axis=1).dropna()
    g = df.groupby(level="datetime")
    ic = g.apply(lambda x: x["pred"].corr(x["label"]))
    ric = g.apply(lambda x: x["pred"].corr(x["label"], method="spearman"))
    return ic.mean(), ric.mean(), ic.mean() / ic.std()


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

    print("🔧 dataset 빌드(1회)...")
    dataset: DatasetH = init_instance_by_config(cfg["task"]["dataset"])
    valid_label = dataset.prepare("valid", col_set="label", data_key=DataHandlerLP.DK_R).iloc[:, 0]

    rows = []
    for name, params in CANDIDATES.items():
        model = LGBModel(**COMMON, **params)
        model.fit(dataset)
        pred = model.predict(dataset, segment="valid")
        ic, ric, icir = calc_valid_ic(pred, valid_label)
        best_it = model.model.best_iteration
        rows.append((name, ic, ric, icir, best_it))
        print(f"   {name:12s} IC={ic:+.4f} RankIC={ric:+.4f} ICIR={icir:+.3f} best_iter={best_it}")

    res = pd.DataFrame(rows, columns=["cand", "valid_IC", "valid_RankIC", "valid_ICIR", "best_iter"])
    res = res.sort_values("valid_RankIC", ascending=False).reset_index(drop=True)
    print("\n" + "=" * 60 + "\nvalid 랭킹 (RankIC 내림차순) — test 미관측\n" + "=" * 60)
    print(res.to_string(index=False))
    best = res.iloc[0]
    print(f"\n👉 최고: {best['cand']} (valid RankIC={best['valid_RankIC']:+.4f}, best_iter={best['best_iter']})")
    print("   baseline_cn이 즉시 early-stop([1])이면 언더피팅 확인. 개선 후보를 config에 반영 후 walk-forward로 확증.")


if __name__ == "__main__":
    main()
