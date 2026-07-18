# -*- coding: utf-8 -*-
"""애플리케이션 설정. 환경변수로 오버라이드 가능."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
STATIC_DIR = BASE_DIR / "static"

HISTORICAL_CSV = DATA_DIR / "kbo_historical.csv"
MODEL_PATH = DATA_DIR / "model.pkl"

# 예측 피처 (비율 지표만 사용 — 시즌 중반 적용 가능)
FEATURES = ["OPS", "RISP", "ERA", "WHIP", "FPCT", "SB%", "CS%"]

# 데이터 소스: "csv" (수동 CSV 업데이트) | "web" (KBO 사이트 스크레이핑)
DATA_SOURCE = os.getenv("DATA_SOURCE", "csv")
CURRENT_SEASON_CSV = DATA_DIR / "current_season.csv"

# 스케줄: 매일 00:00 KST
SCHEDULE_DAY_OF_WEEK = os.getenv("SCHEDULE_DAY_OF_WEEK", "*")
SCHEDULE_HOUR = int(os.getenv("SCHEDULE_HOUR", "0"))
TIMEZONE = "Asia/Seoul"

# 수동 갱신 API 보호 토큰 (설정 시 POST /api/refresh 에 X-Refresh-Token 헤더 필요)
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN", "")

PORT = int(os.getenv("PORT", "8000"))
