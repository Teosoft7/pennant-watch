# -*- coding: utf-8 -*-
"""
KBO 우승 확률 대시보드 — FastAPI 앱.

엔드포인트:
    GET  /               대시보드 (static/index.html)
    GET  /api/latest              최신 일별 예측
    GET  /api/history             일별 예측 히스토리 (트렌드용)
    GET  /api/standings-history   시즌 시작부터의 날짜별 순위/승률 (트렌드용)
    POST /api/refresh    수동 갱신 (REFRESH_TOKEN 설정 시 헤더 검증)
    GET  /health         헬스체크

실행:
    uvicorn app.main:app --reload
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import storage
from app.config import REFRESH_TOKEN, STATIC_DIR
from app.scheduler import create_scheduler, run_daily_update

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("스케줄러 시작 (매일 00:00 KST 갱신)")
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="KBO Champion Probability Dashboard", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/latest")
def api_latest():
    latest = storage.load_latest()
    if latest is None:
        raise HTTPException(
            status_code=404,
            detail="스냅샷이 없습니다. POST /api/refresh 로 첫 갱신을 실행하세요.",
        )
    return latest


@app.get("/api/history")
def api_history(season: int | None = None):
    return {"snapshots": storage.load_history(season)}


@app.get("/api/standings-history")
def api_standings_history():
    return {"days": storage.load_standings_history()}


@app.post("/api/refresh")
def api_refresh(x_refresh_token: str = Header(default="")):
    if REFRESH_TOKEN and x_refresh_token != REFRESH_TOKEN:
        raise HTTPException(status_code=401, detail="잘못된 갱신 토큰입니다.")
    try:
        result = run_daily_update()
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"refreshed": True, "date": result["date"]}


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
