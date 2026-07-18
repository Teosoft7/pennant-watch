# -*- coding: utf-8 -*-
"""
모델 학습 파이프라인.

과거 시즌(2015~) 데이터로 두 개의 로지스틱 회귀를 학습한다:
  1) 정규시즌 우승(1위) 예측
  2) 포스트시즌 진출 예측

피처는 비율 지표만 사용하며, 시즌별 Z-score로 표준화한다.
(리그 환경 변화 보정 + 시즌 중반 데이터에도 동일 스케일 적용 가능)

사용법:
    python -m app.model.train
"""
import pickle

import pandas as pd
from sklearn.linear_model import LogisticRegression

from app.config import FEATURES, HISTORICAL_CSV, MODEL_PATH

TEAM_MAP = {"넥센": "키움", "SK": "SSG"}  # 프랜차이즈 연속성


def season_zscore(df: pd.DataFrame, features: list[str], group_col: str = "YEAR") -> pd.DataFrame:
    """시즌(그룹)별 Z-score 변환. 시즌 중반 스냅샷에도 동일하게 적용."""
    out = df.copy()
    for f in features:
        out[f + "_Z"] = out.groupby(group_col)[f].transform(
            lambda x: (x - x.mean()) / x.std()
        )
    return out


def load_historical() -> pd.DataFrame:
    df = pd.read_csv(HISTORICAL_CSV, encoding="utf-8-sig")
    df["FRANCHISE"] = df["TEAM"].replace(TEAM_MAP)
    # 주의: WIN 컬럼은 '한국시리즈 우승'이 아닌 '정규시즌 1위'를 의미
    df["IS_PENNANT_WINNER"] = (df["WIN"] == "Y").astype(int)
    df["IS_PLAYOFF"] = (df["POST"] == "Y").astype(int)
    return df


def train_and_save() -> dict:
    df = load_historical()
    df = season_zscore(df, FEATURES)
    z_features = [f + "_Z" for f in FEATURES]

    model_win = LogisticRegression(max_iter=2000, C=1.0, random_state=42)
    model_win.fit(df[z_features], df["IS_PENNANT_WINNER"])

    model_po = LogisticRegression(max_iter=2000, C=1.0, random_state=42)
    model_po.fit(df[z_features], df["IS_PLAYOFF"])

    bundle = {
        "features": FEATURES,
        "z_features": z_features,
        "model_win": model_win,
        "model_playoff": model_po,
        "trained_on_seasons": sorted(df["YEAR"].unique().tolist()),
        "n_samples": len(df),
    }
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(bundle, f)
    return bundle


if __name__ == "__main__":
    bundle = train_and_save()
    print(f"모델 저장 완료: {MODEL_PATH}")
    print(f"학습 시즌: {bundle['trained_on_seasons']}")
    print(f"샘플 수: {bundle['n_samples']}")
