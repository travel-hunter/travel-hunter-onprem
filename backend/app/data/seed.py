"""Development seed data only.

Do not treat these demo records as the operational policy catalog.
"""

USER = {
    "id": "1",
    "name": "테스트 사용자",
    "nickname": "테스트 사용자",
    "email": "test.user@example.com",
    "preferredRegions": "제주,부산,강원",
    "travelStyle": "휴식",
    "travelBudget": "1인 40만원 이하",
    "persona": "혜택을 꼼꼼히 챙기는 29세 직장인",
    "savedAmount": 120000,
    "onboardingCompleted": True,
    "socialAccounts": [],
    "createdAt": "2026-05-04T00:00:00Z",
    "updatedAt": "2026-05-04T00:00:00Z",
}

PROFILE = {
    "style": None,
    "budget": None,
}

PROFILE_OPTIONS = {
    "regions": [
        "서울",
        "부산",
        "대구",
        "인천",
        "광주",
        "대전",
        "울산",
        "세종",
        "경기",
        "강원",
        "충북",
        "충남",
        "전북",
        "전남",
        "경북",
        "경남",
        "제주",
    ],
    "travelStyles": ["휴식", "맛집", "체험", "자연", "사진"],
    "budgets": ["1인 30만원 이하", "1인 40만원 이하", "1인 60만원 이하", "상관없음"],
}

REGIONS = PROFILE_OPTIONS["regions"]
TRAVEL_STYLES = PROFILE_OPTIONS["travelStyles"]
BUDGETS = PROFILE_OPTIONS["budgets"]

import json
from pathlib import Path

_DATA_DIR = Path(__file__).parent


def _load_crawled() -> list[dict]:
    path = _DATA_DIR / "dgtourcard_policies.json"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return json.load(f)


POLICIES = _load_crawled()

TRIP = {
    "title": "제주 3일 여행",
    "dates": "2026.06.15 - 06.17",
    "people": ["테스트 사용자", "민서", "현우"],
    "expectedSaving": "12만원",
    "days": {
        1: [
            {"time": "09:00", "label": "성산 일출봉", "meta": "자연 · 관광지"},
            {"time": "12:30", "label": "해녀의 집", "meta": "해산물 · 로컬 맛집"},
            {"time": "15:00", "label": "우도 코스", "meta": "반나절 동선 · 사진 명소"},
        ],
        2: [
            {"time": "10:00", "label": "오설록 티뮤지엄", "meta": "카페 · 실내"},
            {"time": "13:00", "label": "협재 해변", "meta": "해변 · 산책"},
            {"time": "18:30", "label": "동문시장", "meta": "로컬 맛집 · 야시장"},
        ],
        3: [
            {"time": "09:30", "label": "사려니숲길", "meta": "숲길 · 자연"},
            {"time": "13:00", "label": "공항 근처 브런치", "meta": "이동 18분"},
            {"time": "15:00", "label": "렌터카 반납", "meta": "체크리스트 완료"},
        ],
    },
}

RECOMMENDATIONS = [
    {
        "label": "CA",
        "title": "월정리 바다 카페",
        "meta": "Day 2 오후에 적합 · 이동 18분",
        "reason": "비 오는 날에도 머물기 좋고 사진 만족도가 높습니다.",
    },
    {
        "label": "FO",
        "title": "고기국수 로컬 맛집",
        "meta": "Day 1 점심 대체 후보",
        "reason": "예산을 줄이면서 제주 대표 메뉴를 경험할 수 있습니다.",
    },
    {
        "label": "SP",
        "title": "사려니숲길 짧은 코스",
        "meta": "Day 3 오전 추천",
        "reason": "공항 이동 전 부담 없는 산책 동선입니다.",
    },
]

INVITE_URL = "http://127.0.0.1:5173/invites/jeju-3d/accept"
INVITE_TOKEN = "jeju-3d"
INVITE_CREATED_AT = "2026-05-04T00:00:00Z"
INVITE_EXPIRES_AT = "2026-12-31T23:59:59Z"
