# -*- coding: utf-8 -*-
"""
예측 파이프라인.

현재 시즌 팀별 비율 지표 스냅샷(DataFrame)을 받아
우승 확률·포스트시즌 진출 확률을 계산한다.

입력 DataFrame 필수 컬럼:
    TEAM, G(치른 경기수), W/L/D(승/패/무), OPS, RISP, ERA, WHIP, FPCT, SB%, CS%
"""
import pickle
from datetime import datetime, timezone, timedelta

import pandas as pd

from app.config import MODEL_PATH, FEATURES

KST = timezone(timedelta(hours=9))

# 시즌 40% (144경기 기준 약 58경기) 미만이면 비율 지표 안정화 전이므로 경고 플래그
MIN_RELIABLE_GAMES = 58


def load_model() -> dict:
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


def predict(snapshot: pd.DataFrame, season: int) -> dict:
    """스냅샷 → 예측 결과 dict (저장/API 응답에 그대로 사용)."""
    bundle = load_model()
    df = snapshot.copy()

    missing = [c for c in FEATURES + ["TEAM", "G", "W", "L", "D"] if c not in df.columns]
    if missing:
        raise ValueError(f"스냅샷에 누락된 컬럼: {missing}")

    # 스냅샷 내(=현 시점 리그) Z-score — 학습 시와 동일한 변환
    for f in FEATURES:
        std = df[f].std()
        df[f + "_Z"] = 0.0 if std == 0 else (df[f] - df[f].mean()) / std

    z = df[bundle["z_features"]]
    df["prob_win"] = bundle["model_win"].predict_proba(z)[:, 1]
    df["prob_playoff"] = bundle["model_playoff"].predict_proba(z)[:, 1]

    # 우승 확률은 "시즌당 1팀" 제약에 맞게 합=1로 정규화한 값도 함께 제공
    total = df["prob_win"].sum()
    df["prob_win_normalized"] = df["prob_win"] / total if total > 0 else 0.0

    # 실제 순위 = 승률(무승부 제외) 내림차순. 승률 동률은 승수로 타이브레이크.
    decisions = (df["W"] + df["L"]).replace(0, pd.NA)
    df["win_pct"] = (df["W"] / decisions).fillna(0.0)
    df = df.sort_values(["win_pct", "W"], ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1

    now = datetime.now(KST)
    avg_games = float(df["G"].mean())
    return {
        "season": season,
        "generated_at": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "iso_week": now.strftime("%G-W%V"),  # 참고용 (스냅샷 키는 date)
        "avg_games_played": avg_games,
        "season_progress": round(avg_games / 144, 3),
        "reliability_warning": avg_games < MIN_RELIABLE_GAMES,
        "teams": [
            {
                "rank": int(row["rank"]),
                "team": row["TEAM"],
                "games": int(row["G"]),
                "wins": int(row["W"]),
                "losses": int(row["L"]),
                "draws": int(row["D"]),
                "win_pct": round(float(row["win_pct"]), 3),
                "prob_win": round(float(row["prob_win"]), 4),
                "prob_win_normalized": round(float(row["prob_win_normalized"]), 4),
                "prob_playoff": round(float(row["prob_playoff"]), 4),
                "stats": {f: float(row[f]) for f in FEATURES},
            }
            for _, row in df.iterrows()
        ],
    }
