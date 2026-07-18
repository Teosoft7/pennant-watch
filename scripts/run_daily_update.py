# -*- coding: utf-8 -*-
"""
일일 갱신을 수동으로 1회 실행한다 (첫 세팅/디버깅용).

사용법 (프로젝트 루트에서):
    python -m scripts.run_daily_update
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.scheduler import run_daily_update  # noqa: E402

if __name__ == "__main__":
    result = run_daily_update()
    print(f"갱신 완료: {result['date']} / 시즌 {result['season']}")
    print(f"평균 소화 경기: {result['avg_games_played']:.0f} ({result['season_progress']:.0%})")
    print("\n우승 확률 상위 5팀 (정규화):")
    # teams 는 실제 순위순이므로 확률 기준으로 재정렬해 출력
    top = sorted(result["teams"], key=lambda t: t["prob_win_normalized"], reverse=True)
    for t in top[:5]:
        print(f"  {t['team']:>4} {t['prob_win_normalized']:6.1%}")
