# -*- coding: utf-8 -*-
"""
GitHub Pages 배포용 정적 사이트 빌드.

site/ 디렉토리에 대시보드와 API 응답 JSON을 정적 파일로 생성한다:
    site/index.html               static/index.html 그대로
    site/api/latest               GET /api/latest 응답
    site/api/history              GET /api/history 응답 (최신 시즌)
    site/api/standings-history    GET /api/standings-history 응답

프론트엔드가 상대 경로(api/latest)로 fetch 하므로 FastAPI 서빙과
동일하게 동작한다. 확장자 없는 파일도 fetch().json() 파싱에 문제없다.

사용법 (프로젝트 루트에서):
    python -m scripts.build_static_site [출력경로, 기본 site]
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import storage  # noqa: E402
from app.config import BASE_DIR, STATIC_DIR  # noqa: E402


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE_DIR / "site"
    latest = storage.load_latest()
    if latest is None:
        raise SystemExit("스냅샷이 없습니다. 먼저 run_daily_update 를 실행하세요.")

    api = out / "api"
    api.mkdir(parents=True, exist_ok=True)
    shutil.copy(STATIC_DIR / "index.html", out / "index.html")

    def dump(name: str, obj: dict):
        (api / name).write_text(
            json.dumps(obj, ensure_ascii=False), encoding="utf-8")

    dump("latest", latest)
    dump("history", {"snapshots": storage.load_history(latest["season"])})
    dump("standings-history", {"days": storage.load_standings_history()})

    # Pages가 확장자 없는 파일을 Jekyll 처리하지 않도록
    (out / ".nojekyll").write_text("")
    print(f"정적 사이트 빌드 완료: {out}/ "
          f"(기준일 {latest.get('date', latest.get('iso_week'))})")


if __name__ == "__main__":
    main()
