import json
import os
from typing import List

import anthropic

from models import DayRoute

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


ADVICE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": "그날 동선과 식당 구성에 대한 한두 문장 총평 (한국어)",
        },
        "recommendations": {
            "type": "array",
            "description": "추가하면 좋을 식당/카페 후보. 후보 목록에 없으면 빈 배열.",
            "items": {
                "type": "object",
                "properties": {
                    "place_name": {
                        "type": "string",
                        "description": "후보 목록에 있는 이름과 정확히 일치해야 함",
                    },
                    "reason": {
                        "type": "string",
                        "description": "이 장소를 추천하는 이유 (동선, 카테고리 밸런스 등, 한국어 한 문장)",
                    },
                    "insert_after_order": {
                        "type": "integer",
                        "description": "이 순번(order)의 방문지 바로 다음에 넣는 것을 추천. 맨 앞이면 0.",
                    },
                },
                "required": ["place_name", "reason", "insert_after_order"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary", "recommendations"],
    "additionalProperties": False,
}


def _format_route(route: DayRoute) -> str:
    lines = [f"{route.day}일차, 총 {route.total_distance_km}km / {route.total_duration_min}분"]
    for stop in route.stops:
        lines.append(
            f"  {stop.order}. {stop.place.name} ({stop.place.type}) - {stop.note or ''}"
        )
    return "\n".join(lines)


def _format_candidates(label: str, candidates: List[dict]) -> str:
    if not candidates:
        return f"{label}: 없음"
    lines = [f"{label}:"]
    for c in candidates:
        lines.append(f"  - {c.get('name')} ({c.get('category', '')})")
    return "\n".join(lines)


def get_day_advice(
    route: DayRoute,
    restaurant_candidates: List[dict],
    cafe_candidates: List[dict],
) -> dict:
    """
    하루 경로와 주변 식당/카페 후보를 Claude에 보여주고, 끼워 넣을 만한 곳과
    그 이유를 구조화된 JSON으로 받는다.
    """
    prompt = f"""당신은 제주 여행 동선을 검토하는 여행 플래너입니다.

아래는 어떤 여행자의 {route.day}일차 동선과, 그 동선 주변에서 검색된 식당/카페 후보 목록입니다.
동선의 지리적 순서와 기존 식당 구성을 보고, 후보 중에서 실제로 끼워 넣을 만한 곳이 있으면 추천해주세요.
이미 동선에 있는 곳과 카테고리가 겹치거나 (예: 식당이 이미 3곳 있는데 또 식당 추천) 불필요하면 추천하지 마세요.
후보 목록에 없는 장소는 추천하지 마세요.

## 오늘 동선
{_format_route(route)}

## 주변 후보
{_format_candidates("식당", restaurant_candidates)}
{_format_candidates("카페", cafe_candidates)}
"""

    response = _get_client().messages.create(
        model="claude-opus-4-8",
        max_tokens=2000,
        output_config={"format": {"type": "json_schema", "schema": ADVICE_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )

    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)
