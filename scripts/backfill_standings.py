# -*- coding: utf-8 -*-
"""
시즌 시작부터 오늘까지 날짜별 팀 순위(승/패/무/승률)를 KBO 공식
순위 페이지에서 수집해 data/standings_history.csv 로 저장한다.

- 소스: koreabaseball.com Record/TeamRank/TeamRankDaily.aspx (ASP.NET 포스트백)
- 이미 수집된 날짜는 건너뛰므로 재실행해도 안전하다 (증분 수집).
- 개막 전 날짜(전 팀 0경기)는 자동으로 제외한다.

사용법 (프로젝트 루트에서):
    python -m scripts.backfill_standings [시작일 YYYY-MM-DD, 기본 3월 1일]
"""
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import DATA_DIR  # noqa: E402

KST = timezone(timedelta(hours=9))
RANK_URL = "https://www.koreabaseball.com/Record/TeamRank/TeamRankDaily.aspx"
HEADERS = {"User-Agent": "Mozilla/5.0 (dashboard; contact: admin)"}
OUT_CSV = DATA_DIR / "standings_history.csv"
DELAY_SEC = 0.3  # 서버 부하 방지용 요청 간격

FORM_PREFIX = "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents"


def _hidden_fields(html: str) -> dict:
    return dict(re.findall(r'<input type="hidden" name="([^"]+)"[^>]* value="([^"]*)"', html))


def _parse_table(html: str) -> pd.DataFrame:
    df = pd.read_html(StringIO(html))[0]
    df = df.rename(columns={"팀명": "TEAM", "순위": "RANK", "경기": "G",
                            "승": "W", "패": "L", "무": "D", "승률": "WPCT"})
    return df[["RANK", "TEAM", "G", "W", "L", "D", "WPCT"]]


def fetch_range(start: date, end: date, have: set[str]) -> list[pd.DataFrame]:
    """포스트백 체이닝으로 [start, end] 구간의 일자별 순위를 수집."""
    session = requests.Session()
    resp = session.get(RANK_URL, headers=HEADERS, timeout=15)
    form = _hidden_fields(resp.text)

    frames = []
    day = start
    while day <= end:
        ds = day.strftime("%Y-%m-%d")
        if ds in have:
            day += timedelta(days=1)
            continue
        form[f"{FORM_PREFIX}$hfSearchDate"] = day.strftime("%Y%m%d")
        form["__EVENTTARGET"] = f"{FORM_PREFIX}$btnCalendarSelect"
        form["__EVENTARGUMENT"] = ""
        resp = session.post(RANK_URL, headers=HEADERS, data=form, timeout=15)
        form = _hidden_fields(resp.text)  # 다음 요청용 VIEWSTATE 갱신
        try:
            df = _parse_table(resp.text)
        except ValueError:
            print(f"  {ds}: 테이블 없음 — 건너뜀")
            day += timedelta(days=1)
            continue
        if df["G"].sum() == 0:  # 개막 전
            day += timedelta(days=1)
            continue
        df.insert(0, "DATE", ds)
        frames.append(df)
        print(f"  {ds}: 1위 {df.iloc[0]['TEAM']} ({df.iloc[0]['W']}승)")
        time.sleep(DELAY_SEC)
        day += timedelta(days=1)
    return frames


def main():
    today = datetime.now(KST).date()
    start = (date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1
             else date(today.year, 3, 1))

    have: set[str] = set()
    old = None
    if OUT_CSV.exists():
        old = pd.read_csv(OUT_CSV, encoding="utf-8-sig")
        have = set(old["DATE"].unique())
        print(f"기존 수집분 {len(have)}일 — 누락 날짜만 수집")

    frames = fetch_range(start, today, have)
    if not frames and old is None:
        print("수집된 데이터 없음")
        return
    if not frames:
        print("추가 수집할 날짜 없음 — 기존 데이터 정리만 수행")
    parts = ([old] if old is not None else []) + frames
    out = pd.concat(parts, ignore_index=True)
    out = out.sort_values(["DATE", "RANK"]).reset_index(drop=True)

    # 개막 전 날짜엔 페이지가 전 시즌 최종 순위를 반환한다.
    # 경기수(G)가 감소하는 마지막 지점 = 개막일 → 그 이전 날짜는 제거.
    gmax = out.groupby("DATE")["G"].max()
    resets = [d for i, d in enumerate(gmax.index)
              if i > 0 and gmax.iloc[i] < gmax.iloc[i - 1]]
    if resets:
        opening = resets[-1]
        dropped = out["DATE"] < opening
        if dropped.any():
            print(f"개막 전 데이터 제거: {opening} 이전 {out[dropped]['DATE'].nunique()}일")
        out = out[~dropped].reset_index(drop=True)
    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n저장 완료: {OUT_CSV} ({out['DATE'].nunique()}일, {len(out)}행)")


if __name__ == "__main__":
    main()
