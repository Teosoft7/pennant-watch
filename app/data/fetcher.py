# -*- coding: utf-8 -*-
"""
현재 시즌 데이터 수집.

두 가지 소스를 지원한다 (config.DATA_SOURCE):

1) "csv"  — data/current_season.csv 파일을 읽는다. (기본값)
   필수 컬럼: TEAM, G, W, L, D, OPS, RISP, ERA, WHIP, FPCT, SB%, CS%
             (W/L/D = 승/패/무 — 실제 순위 산출용, KBO 순위 페이지 기준)

2) "web"  — KBO 공식 사이트(koreabaseball.com) 5개 페이지를 스크레이핑해
   위와 동일한 형태로 병합한다 (2026-07 실페이지 구조로 검증됨):
     순위 페이지  → TEAM, G, W, L, D
     타자 Basic2 → OPS, RISP
     투수 Basic1 → ERA, WHIP
     수비 Basic  → FPCT, CS%
     주루 Basic  → SB%
   성공 시 current_season.csv 에 캐시로 저장하므로, 이후 스크레이핑이
   실패해도 마지막 성공 시점 데이터로 CSV 폴백된다.
"""
import logging
from io import StringIO

import pandas as pd

from app.config import CURRENT_SEASON_CSV, DATA_SOURCE

logger = logging.getLogger(__name__)

REQUIRED_COLS = ["TEAM", "G", "W", "L", "D", "OPS", "RISP", "ERA", "WHIP", "FPCT", "SB%", "CS%"]

# KBO 공식 기록 페이지 (스크레이핑 모드용, pd.read_html tables[0])
KBO_RANK_URL = "https://www.koreabaseball.com/Record/TeamRank/TeamRankDaily.aspx"
KBO_HITTER_URL = "https://www.koreabaseball.com/Record/Team/Hitter/Basic2.aspx"
KBO_PITCHER_URL = "https://www.koreabaseball.com/Record/Team/Pitcher/Basic1.aspx"
KBO_DEFENSE_URL = "https://www.koreabaseball.com/Record/Team/Defense/Basic.aspx"
KBO_RUNNER_URL = "https://www.koreabaseball.com/Record/Team/Runner/Basic.aspx"


def fetch_from_csv() -> pd.DataFrame:
    """data/current_season.csv 로드."""
    if not CURRENT_SEASON_CSV.exists():
        raise FileNotFoundError(
            f"{CURRENT_SEASON_CSV} 가 없습니다. "
            "DATA_SOURCE=web 으로 실행하거나 KBO 기록실에서 팀 기록을 받아 CSV로 저장해 주세요."
        )
    df = pd.read_csv(CURRENT_SEASON_CSV, encoding="utf-8-sig")
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"current_season.csv 누락 컬럼: {missing}")
    return df[REQUIRED_COLS].copy()


def fetch_from_kbo_web() -> pd.DataFrame:
    """KBO 공식 사이트 스크레이핑 (순위 + 팀 기록 4종 병합)."""
    import requests

    headers = {"User-Agent": "Mozilla/5.0 (dashboard; contact: admin)"}

    def read_table(url: str) -> pd.DataFrame:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        if "/Error/" in resp.url:
            raise ValueError(f"에러 페이지로 리다이렉트됨: {url}")
        tables = pd.read_html(StringIO(resp.text))
        if not tables:
            raise ValueError(f"테이블 파싱 실패: {url}")
        return tables[0].rename(columns={"팀명": "TEAM"})

    rank = read_table(KBO_RANK_URL).rename(
        columns={"경기": "G", "승": "W", "패": "L", "무": "D"})
    hitter = read_table(KBO_HITTER_URL)    # OPS, RISP
    pitcher = read_table(KBO_PITCHER_URL)  # ERA, WHIP
    defense = read_table(KBO_DEFENSE_URL)  # FPCT, CS%
    runner = read_table(KBO_RUNNER_URL)    # SB%

    df = rank[["TEAM", "G", "W", "L", "D"]]
    df = df.merge(hitter[["TEAM", "OPS", "RISP"]], on="TEAM")
    df = df.merge(pitcher[["TEAM", "ERA", "WHIP"]], on="TEAM")
    df = df.merge(defense[["TEAM", "FPCT", "CS%"]], on="TEAM")
    df = df.merge(runner[["TEAM", "SB%"]], on="TEAM")

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(
            f"스크레이핑 결과에 누락 컬럼 {missing} — "
            "KBO 페이지 구조가 변경되었을 수 있습니다. 셀렉터를 점검하세요."
        )
    if len(df) != 10:
        raise ValueError(f"팀 수 이상 ({len(df)}팀) — 병합 실패 가능성. 팀명 표기를 점검하세요.")
    if df[REQUIRED_COLS].isna().any().any():
        raise ValueError("스크레이핑 결과에 결측치 존재 — 페이지 구조를 점검하세요.")
    return df[REQUIRED_COLS].copy()


def fetch_current_season() -> pd.DataFrame:
    """설정된 소스에서 현재 시즌 스냅샷을 가져온다. web 실패 시 csv 폴백."""
    if DATA_SOURCE == "web":
        try:
            df = fetch_from_kbo_web()
        except Exception as e:  # noqa: BLE001
            logger.warning("웹 스크레이핑 실패, CSV 폴백: %s", e)
        else:
            # 마지막 성공 스냅샷을 CSV 캐시로 유지 → 이후 실패 시 폴백 데이터가 됨
            try:
                df.to_csv(CURRENT_SEASON_CSV, index=False, encoding="utf-8-sig")
            except OSError as e:
                logger.warning("current_season.csv 캐시 저장 실패: %s", e)
            return df
    return fetch_from_csv()
