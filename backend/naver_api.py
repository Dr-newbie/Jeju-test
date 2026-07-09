import os
import requests
from dotenv import load_dotenv

load_dotenv()


NAVER_MAP_CLIENT_ID = os.getenv("NAVER_MAP_CLIENT_ID")
NAVER_MAP_CLIENT_SECRET = os.getenv("NAVER_MAP_CLIENT_SECRET")

NAVER_SEARCH_CLIENT_ID = os.getenv("NAVER_SEARCH_CLIENT_ID")
NAVER_SEARCH_CLIENT_SECRET = os.getenv("NAVER_SEARCH_CLIENT_SECRET")


def geocode_address(address: str):
    """
    Naver Cloud Maps Geocoding.
    주소 -> 좌표 변환.
    """
    url = "https://maps.apigw.ntruss.com/map-geocode/v2/geocode"

    headers = {
        "x-ncp-apigw-api-key-id": NAVER_MAP_CLIENT_ID,
        "x-ncp-apigw-api-key": NAVER_MAP_CLIENT_SECRET,
    }

    params = {"query": address}

    r = requests.get(url, headers=headers, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    addresses = data.get("addresses", [])
    if not addresses:
        return None

    item = addresses[0]

    return {
        "address": item.get("roadAddress") or item.get("jibunAddress") or address,
        "lat": float(item["y"]),
        "lng": float(item["x"]),
        "raw": item,
    }


def reverse_geocode(lat: float, lng: float) -> str | None:
    """
    Naver Cloud Maps Reverse Geocoding.
    좌표 -> 대략적인 지역명 (시군구 + 읍면동) 문자열.
    """
    url = "https://maps.apigw.ntruss.com/map-reversegeocode/v2/gc"

    headers = {
        "x-ncp-apigw-api-key-id": NAVER_MAP_CLIENT_ID,
        "x-ncp-apigw-api-key": NAVER_MAP_CLIENT_SECRET,
    }

    params = {
        "coords": f"{lng},{lat}",
        "orders": "legalcode",
        "output": "json",
    }

    r = requests.get(url, headers=headers, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    results = data.get("results", [])
    if not results:
        return None

    region = results[0].get("region", {})
    area2 = region.get("area2", {}).get("name", "")
    area3 = region.get("area3", {}).get("name", "")

    parts = [p for p in [area2, area3] if p]
    return " ".join(parts) if parts else None


_driving_route_cache: dict[tuple[float, float, float, float], tuple[float, float] | None] = {}


def get_driving_route(
    start_lat: float, start_lng: float, goal_lat: float, goal_lng: float
) -> tuple[float, float] | None:
    """
    NCP Directions 5 (trafast, 실시간 교통 반영 빠른길).
    실패하거나 경로가 없으면 None (호출부에서 직선거리로 fallback).
    반환값: (distance_km, duration_min)
    """
    cache_key = (
        round(start_lat, 5),
        round(start_lng, 5),
        round(goal_lat, 5),
        round(goal_lng, 5),
    )
    if cache_key in _driving_route_cache:
        return _driving_route_cache[cache_key]

    url = "https://maps.apigw.ntruss.com/map-direction/v1/driving"

    headers = {
        "x-ncp-apigw-api-key-id": NAVER_MAP_CLIENT_ID,
        "x-ncp-apigw-api-key": NAVER_MAP_CLIENT_SECRET,
    }

    params = {
        "start": f"{start_lng},{start_lat}",
        "goal": f"{goal_lng},{goal_lat}",
        "option": "trafast",
    }

    result = None
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        summary = data.get("route", {}).get("trafast", [{}])[0].get("summary")
        if summary:
            distance_km = summary["distance"] / 1000
            duration_min = summary["duration"] / 1000 / 60
            result = (distance_km, duration_min)
    except Exception:
        result = None

    _driving_route_cache[cache_key] = result
    return result


def get_driving_path(points: list[tuple[float, float]]) -> list[tuple[float, float]] | None:
    """
    (lat, lng) 지점들을 순서대로 지나는 실제 도로 경로의 좌표열을 반환한다.
    NCP Directions 5 (trafast)의 waypoints 기능을 이용해 한 번의 호출로 전체
    구간의 path를 가져온다. 실패하면 None (호출부에서 직선 연결로 fallback).
    """
    if len(points) < 2:
        return None

    start_lat, start_lng = points[0]
    goal_lat, goal_lng = points[-1]
    middle = points[1:-1]

    url = "https://maps.apigw.ntruss.com/map-direction/v1/driving"

    headers = {
        "x-ncp-apigw-api-key-id": NAVER_MAP_CLIENT_ID,
        "x-ncp-apigw-api-key": NAVER_MAP_CLIENT_SECRET,
    }

    params = {
        "start": f"{start_lng},{start_lat}",
        "goal": f"{goal_lng},{goal_lat}",
        "option": "trafast",
    }

    if middle:
        params["waypoints"] = "|".join(f"{lng},{lat}" for lat, lng in middle)

    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        path = data.get("route", {}).get("trafast", [{}])[0].get("path")
        if not path:
            return None

        return [(lat, lng) for lng, lat in path]
    except Exception:
        return None


def search_local_place(query: str, display: int = 5):
    """
    Naver Search API - Local Search.
    장소명 검색 -> 후보 장소 반환.
    """
    url = "https://openapi.naver.com/v1/search/local.json"

    headers = {
        "X-Naver-Client-Id": NAVER_SEARCH_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_SEARCH_CLIENT_SECRET,
    }

    params = {
        "query": query,
        "display": display,
        "sort": "random",
    }

    r = requests.get(url, headers=headers, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    results = []
    for item in data.get("items", []):
        title = (
            item.get("title", "")
            .replace("<b>", "")
            .replace("</b>", "")
        )

        results.append(
            {
                "name": title,
                "category": item.get("category"),
                "address": item.get("roadAddress") or item.get("address"),
                "telephone": item.get("telephone"),
                "mapx": item.get("mapx"),
                "mapy": item.get("mapy"),
                "link": item.get("link"),
                "raw": item,
            }
        )

    return results


def recommend_nearby(lat: float, lng: float, category: str, display: int = 5):
    """
    좌표 주변 지역명을 역지오코딩으로 구한 뒤, 그 지역명 + 카테고리로
    지역 검색을 돌려 근처 후보를 추천한다. (별점 데이터는 제공되지 않음)
    """
    region = reverse_geocode(lat, lng)
    query = f"{region} {category}".strip() if region else category

    items = search_local_place(query, display=display)

    for item in items:
        try:
            item["lat"] = int(item["mapy"]) / 1e7
            item["lng"] = int(item["mapx"]) / 1e7
        except (TypeError, ValueError):
            item["lat"] = None
            item["lng"] = None

    return items
