# KBO 우승 확률 전광판 (Champion Probability Dashboard)

매일 자동 갱신되는 KBO 정규시즌 우승·포스트시즌 진출 확률 대시보드.

비율 지표(OPS, RISP, ERA, WHIP, FPCT, SB%, CS%)만 사용하는 로지스틱 회귀 모델로,
시즌 중반 데이터로도 당해년도 결과를 예측할 수 있다.
(모델 설계 근거와 검증은 `KBO_우승팀_예측모델.ipynb` 참조 — LOSO-CV 기준
우승 Top-1 적중 63.6%, PS진출 5팀 중 평균 4.18팀 적중, AUC 0.94)

## 아키텍처

```
데이터 수집 (fetcher) ──▶ 예측 (predict) ──▶ 스냅샷 저장 (storage)
        ▲                                          │
        │ 매일 00:00 KST (APScheduler)              ▼
        └────────── scheduler ◀──────── FastAPI (/api/*) ──▶ 대시보드 (static)
```

```
kbo-champ-dashboard/
├── app/
│   ├── main.py            # FastAPI 앱 (API + 대시보드 서빙 + 스케줄러 lifespan)
│   ├── config.py          # 설정 (환경변수 오버라이드)
│   ├── scheduler.py       # 일일 갱신 잡 + APScheduler
│   ├── storage.py         # 스냅샷 저장소 (JSON, MongoDB 확장점 문서화)
│   ├── model/
│   │   ├── train.py       # 모델 학습 (과거 시즌 → model.pkl)
│   │   └── predict.py     # 예측 파이프라인
│   └── data/fetcher.py    # 현재 시즌 데이터 수집 (csv | web)
├── static/index.html      # 대시보드 (전광판 UI, Chart.js)
├── data/
│   ├── kbo_historical.csv # 학습 데이터 (2015-2025)
│   ├── current_season.csv # 현재 시즌 스냅샷 (일일 갱신 입력)
│   ├── model.pkl          # 학습된 모델
│   ├── snapshots/         # 일별 예측 결과 (날짜별 JSON)
│   └── standings_history.csv # 날짜별 실제 순위/승률 (추이 차트용)
└── scripts/
    ├── run_daily_update.py   # 수동 갱신 1회 실행
    ├── backfill_standings.py # 시즌 개막부터 날짜별 순위 수집 (증분)
    ├── build_static_site.py  # GitHub Pages용 정적 사이트 빌드
    └── seed_demo_data.py     # 데모 데이터 생성 (개발용)
```

## 빠른 시작

```bash
pip install -r requirements.txt

# 1. 모델 학습 (최초 1회, 시즌 종료 후 재학습 권장)
python -m app.model.train

# 2. 데모 데이터로 바로 확인하려면 (2025 최종 기록 + 가상 일별 히스토리)
python -m scripts.seed_demo_data
python -m scripts.run_daily_update

# 3. 서버 실행
uvicorn app.main:app --reload
# → http://localhost:8000  (대시보드)
```

## API

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/` | 대시보드 |
| GET | `/api/latest` | 최신 일별 예측 |
| GET | `/api/history?season=2026` | 일별 스냅샷 히스토리 (추이 차트용) |
| GET | `/api/standings-history` | 시즌 개막부터의 날짜별 순위/승률 (승률 추이용) |
| POST | `/api/refresh` | 수동 갱신 (REFRESH_TOKEN 설정 시 `X-Refresh-Token` 헤더 필요) |
| GET | `/health` | 헬스체크 |

## 운영 워크플로우

**수동 모드 (DATA_SOURCE=csv, 기본값)**
1. 매일 KBO 공식 기록실에서 팀 기록을 확인해 `data/current_season.csv` 갱신
   (필수 컬럼: `TEAM, G, W, L, D, OPS, RISP, ERA, WHIP, FPCT, SB%, CS%`)
2. 스케줄러가 매일 00:00 KST에 자동으로 예측·저장
   (또는 `POST /api/refresh` 로 즉시 갱신)

**스크레이핑 모드 (DATA_SOURCE=web, 권장)**
- `fetch_from_kbo_web()` 이 KBO 공식 순위·타자·투수·수비·주루 5개 페이지를
  병합해 수집한다 (2026-07 실페이지 구조로 검증됨).
- 성공 시 `current_season.csv` 에 캐시를 남기고, 실패(사이트 구조 변경 등) 시
  마지막 성공 캐시로 자동 폴백한다. 배포 환경에서는 이 모드를 사용할 것.

## 배포

### 방법 1: GitHub Actions + Pages (권장 — 무료, 서버리스)

상시 서버 없이 매일 자정 KST에 Actions가 갱신하고 Pages가 정적 서빙한다.

1. 리포지토리를 GitHub에 푸시
2. Settings → Pages → Source 를 **GitHub Actions** 로 변경
3. 끝 — `.github/workflows/daily-update.yml` 이 매일 00:00 KST에
   스크레이핑 → 예측 → `data/` 커밋(영속화) → 정적 사이트 빌드·배포를 수행한다.
   수동 갱신은 Actions 탭에서 Run workflow.

로컬에서 정적 빌드 확인:

```bash
python -m scripts.build_static_site
python -m http.server 8000 --directory site
```

### 방법 2: Railway (상시 서버 + API)

`Procfile` 포함. Railway에 리포지토리 연결 후 환경변수 설정:

```
DATA_SOURCE=web
REFRESH_TOKEN=<임의의 시크릿>
```

주의: Railway 기본 파일시스템은 재배포 시 초기화되므로, 스냅샷 영속화를
위해 Volume을 `data/` 에 마운트할 것 (또는 MongoDB로 전환).

## MongoDB(Beanie) 확장

`app/storage.py` 는 `save / load_latest / load_history` 3개 함수만 노출한다.
MongoDB Atlas 전환 시 이 파일만 교체하면 된다 (Document 스키마 예시는
storage.py docstring 참조). OOHLIB에서 쓰는 Beanie 패턴 그대로 적용 가능.

## 유의사항

- **'우승' = 정규시즌 1위**. 한국시리즈 결과와 다를 수 있다 (2015, 2018 사례).
- **시즌 초반 신뢰도**: 팀 단위 비율 지표는 약 58경기(시즌 40%) 이후 안정화된다.
  그 전에는 대시보드에 신뢰도 경고가 표시된다.
- **데모 데이터**: `seed_demo_data.py` 가 만드는 과거 일자 스냅샷은
  가상 데이터(`"demo": true`)다. 실운영 시작 시 `data/snapshots/` 를 비울 것.
- **재학습**: 시즌 종료 후 `kbo_historical.csv` 에 신규 시즌을 추가하고
  `python -m app.model.train` 을 재실행하면 모델이 갱신된다.
