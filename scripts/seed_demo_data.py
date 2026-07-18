# -*- coding: utf-8 -*-
"""
데모 데이터 시드 (개발/시연용).

실제 현재 시즌 데이터가 없을 때, 2025시즌 최종 기록을
current_season.csv 로 넣고, 트렌드 차트 확인용 가상 일별 스냅샷
(노이즈 추가, demo=true 라벨)을 생성한다.

⚠ 생성된 과거 일자 스냅샷은 실제 데이터가 아니다.
   실운영 시작 시 data/snapshots/ 를 비우고 시작할 것.

사용법 (프로젝트 루트에서):
    python -m scripts.seed_demo_data
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import CURRENT_SEASON_CSV, HISTORICAL_CSV, SNAPSHOT_DIR  # noqa: E402
from app.model.predict import predict  # noqa: E402

KST = timezone(timedelta(hours=9))
rng = np.random.default_rng(42)

# 1) 2025 최종 기록 → current_season.csv (데모 입력)
#    W/L 은 팀 승패와 동일한 투수 기록 컬럼 사용, 무승부 D = G - W - L
hist = pd.read_csv(HISTORICAL_CSV, encoding="utf-8-sig")
snap = hist[hist["YEAR"] == 2025][
    ["TEAM", "G", "W", "L", "OPS", "RISP", "ERA", "WHIP", "FPCT", "SB%", "CS%"]
].copy()
snap["D"] = snap["G"] - snap["W"] - snap["L"]
snap = snap[["TEAM", "G", "W", "L", "D", "OPS", "RISP", "ERA", "WHIP", "FPCT", "SB%", "CS%"]]
snap.to_csv(CURRENT_SEASON_CSV, index=False, encoding="utf-8-sig")
print(f"current_season.csv 생성 (2025 최종 기록 기반 데모): {CURRENT_SEASON_CSV}")

# 2) 과거 14일 가상 스냅샷 (지표에 소량 노이즈 → 확률 추이 시각화 확인용)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
now = datetime.now(KST)
noise_scale = {"OPS": .012, "RISP": .012, "ERA": .18, "WHIP": .05,
               "FPCT": .002, "SB%": 2.0, "CS%": 2.0}

for days_ago in range(14, 0, -1):
    ts = now - timedelta(days=days_ago)
    noisy = snap.copy()
    for col, s in noise_scale.items():
        noisy[col] = noisy[col] + rng.normal(0, s * (days_ago / 14), len(noisy))
    result = predict(noisy, season=now.year)
    result["generated_at"] = ts.isoformat()
    result["date"] = ts.strftime("%Y-%m-%d")
    result["iso_week"] = ts.strftime("%G-W%V")
    result["demo"] = True  # 가상 데이터 표시
    path = SNAPSHOT_DIR / f"{result['date']}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"데모 스냅샷 생성: {path.name}")

print("\n완료. 이제 'python -m scripts.run_daily_update' 로 오늘자 스냅샷을 생성하세요.")
