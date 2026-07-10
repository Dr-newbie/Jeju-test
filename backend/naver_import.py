import re
from typing import Any

import requests

from models import Place
from optimizer import infer_place_type

# 검증된 mcid만 직접 매핑하고, 나머지는 기존 infer_place_type(카테고리 텍스트 기반)에 맡긴다.
MCID_TYPE_MAP = {
    "DINING": "restaurant",
    "CAFE": "cafe",
}

SHARE_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")
SHARE_ID_IN_URL_PATTERN = re.compile(r"folder/([a-f0-9]{32})")

_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://map.naver.com/",
}


def extract_share_id(url_or_id: str) -> str:
    """
    naver.me 단축 링크나 map.naver.com 공유 링크, 혹은 shareId 자체를 받아
    32자리 shareId를 뽑아낸다. 단축 링크는 실제 페이지로 리다이렉트되므로 따라간다.
    """
    url_or_id = url_or_id.strip()
    if SHARE_ID_PATTERN.match(url_or_id):
        return url_or_id

    resp = requests.get(
        url_or_id, allow_redirects=True, timeout=10, headers=_REQUEST_HEADERS
    )
    match = SHARE_ID_IN_URL_PATTERN.search(resp.url)
    if not match:
        raise ValueError("공유 링크에서 리스트 ID를 찾을 수 없습니다.")
    return match.group(1)


def fetch_naver_shared_bookmarks(url_or_id: str) -> dict[str, Any]:
    """
    네이버 지도 저장 리스트 공유 페이지가 내부적으로 호출하는 비공식 API를
    서버에서 직접 호출한다. 공식 export 기능이 없어 사용하는 방식이라,
    네이버가 이 API 구조를 바꾸면 언제든 깨질 수 있다.
    """
    share_id = extract_share_id(url_or_id)
    api_url = (
        f"https://pages.map.naver.com/save-pages/api/maps-bookmark/v3/shares/"
        f"{share_id}/bookmarks"
    )

    r = requests.get(
        api_url,
        params={
            "start": 0,
            "limit": 5000,
            "sort": "lastUseTime",
            "createIdNo": "false",
        },
        headers=_REQUEST_HEADERS,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def parse_naver_bookmarks(payload: dict[str, Any]) -> list[Place]:
    """
    네이버 지도 저장 리스트 공유 페이지의 API 응답(JSON)을 Place 목록으로 변환한다.
    공유 링크는 공식 export 기능이 없어, 사용자가 브라우저 개발자도구 Network 탭에서
    직접 복사해온 응답 JSON을 그대로 붙여넣는 방식으로 가져온다.
    """
    bookmarks = payload.get("bookmarkList", [])
    places = []

    for b in bookmarks:
        lat, lng = b.get("py"), b.get("px")
        if lat is None or lng is None or not b.get("name"):
            continue

        category_name = b.get("mcidName")
        place_type = MCID_TYPE_MAP.get(b.get("mcid")) or infer_place_type(category_name)

        places.append(
            Place(
                id=f"naver_{b['bookmarkId']}",
                name=b["name"],
                address=b.get("address"),
                lat=lat,
                lng=lng,
                type=place_type,
                naver_category=category_name,
                food_category=category_name if place_type == "restaurant" else None,
            )
        )

    return places
