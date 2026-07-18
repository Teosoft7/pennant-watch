# -*- coding: utf-8 -*-
"""
일별 스냅샷 저장소.

파일 기반 JSON 저장 (data/snapshots/{YYYY-MM-DD}.json + latest.json).
과거 주간 운영 시절의 스냅샷({ISO주차}.json)도 히스토리에서 함께 읽는다.
운영 규모가 커지면 MongoDB(Beanie ODM)로 교체 가능하도록
save / load_latest / load_history 인터페이스만 사용한다.

MongoDB 확장 예시:
    class DailySnapshot(Document):
        season: int
        date: str  # YYYY-MM-DD
        generated_at: datetime
        teams: list[dict]
        class Settings:
            name = "daily_snapshots"
            indexes = ["season", "date"]
"""
import csv
import json
from pathlib import Path

from app.config import DATA_DIR, SNAPSHOT_DIR

STANDINGS_CSV = DATA_DIR / "standings_history.csv"


def save(result: dict) -> Path:
    """스냅샷 저장. 같은 날짜는 덮어쓴다(당일 재실행 시 최신값 유지)."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    key = result.get("date") or result["iso_week"]  # 구 포맷 폴백
    day_path = SNAPSHOT_DIR / f"{key}.json"
    latest_path = SNAPSHOT_DIR / "latest.json"
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    day_path.write_text(payload, encoding="utf-8")
    latest_path.write_text(payload, encoding="utf-8")
    return day_path


def load_latest() -> dict | None:
    latest_path = SNAPSHOT_DIR / "latest.json"
    if not latest_path.exists():
        return None
    return json.loads(latest_path.read_text(encoding="utf-8"))


def load_history(season: int | None = None) -> list[dict]:
    """시간순 정렬된 스냅샷 목록 (트렌드 차트용). 구 주간 스냅샷 포함."""
    if not SNAPSHOT_DIR.exists():
        return []
    snapshots = []
    for p in SNAPSHOT_DIR.glob("*.json"):
        if p.name == "latest.json":
            continue
        snap = json.loads(p.read_text(encoding="utf-8"))
        if season is None or snap.get("season") == season:
            snapshots.append(snap)
    # 파일명이 날짜/주차 혼재라 사전순이 시간순이 아님 → generated_at 기준 정렬
    snapshots.sort(key=lambda s: s.get("generated_at", ""))
    return snapshots


def load_standings_history() -> list[dict]:
    """날짜별 순위/승률 목록 (승률 추이 차트용).

    scripts/backfill_standings.py 가 만드는 standings_history.csv 를 읽어
    [{date, teams: [{team, rank, wins, losses, draws, win_pct}]}] 로 반환.
    """
    if not STANDINGS_CSV.exists():
        return []
    days: dict[str, list[dict]] = {}
    with open(STANDINGS_CSV, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            days.setdefault(row["DATE"], []).append({
                "team": row["TEAM"],
                "rank": int(row["RANK"]),
                "games": int(row["G"]),
                "wins": int(row["W"]),
                "losses": int(row["L"]),
                "draws": int(row["D"]),
                "win_pct": float(row["WPCT"]),
            })
    return [{"date": d, "teams": sorted(teams, key=lambda t: t["rank"])}
            for d, teams in sorted(days.items())]


def append_today_standings(result: dict) -> None:
    """일일 갱신 결과에서 당일 순위를 standings_history.csv 에 추가.

    이미 해당 날짜가 있으면 아무것도 하지 않는다 (재실행 안전).
    """
    date = result.get("date")
    if not date:
        return
    if STANDINGS_CSV.exists():
        with open(STANDINGS_CSV, encoding="utf-8-sig") as f:
            if any(row["DATE"] == date for row in csv.DictReader(f)):
                return
        mode, header = "a", False
    else:
        mode, header = "w", True
    with open(STANDINGS_CSV, mode, encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        if header:
            w.writerow(["DATE", "RANK", "TEAM", "G", "W", "L", "D", "WPCT"])
        for t in result["teams"]:
            w.writerow([date, t["rank"], t["team"], t["games"],
                        t["wins"], t["losses"], t["draws"], f"{t['win_pct']:.3f}"])
