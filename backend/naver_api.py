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
