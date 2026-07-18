# -*- coding: utf-8 -*-
"""
일일 갱신 잡 + APScheduler 설정.

매일 00:00 KST에 실행:
    데이터 수집 → 예측 → 스냅샷 저장
"""
import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app import storage
from app.config import SCHEDULE_DAY_OF_WEEK, SCHEDULE_HOUR, TIMEZONE
from app.data.fetcher import fetch_current_season
from app.model.predict import predict

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))


def run_daily_update() -> dict:
    """갱신 잡 본체. 스케줄러와 수동 API(/api/refresh)가 공유."""
    season = datetime.now(KST).year
    logger.info("일일 갱신 시작: season=%s", season)
    snapshot = fetch_current_season()
    result = predict(snapshot, season=season)
    path = storage.save(result)
    storage.append_today_standings(result)  # 승률 추이 차트용 누적
    logger.info("일일 갱신 완료: %s", path)
    return result


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        run_daily_update,
        CronTrigger(day_of_week=SCHEDULE_DAY_OF_WEEK, hour=SCHEDULE_HOUR, minute=0),
        id="daily_update",
        replace_existing=True,
        misfire_grace_time=3600,  # 서버 재시작 등으로 놓친 경우 1시간 내 보정 실행
    )
    return scheduler
