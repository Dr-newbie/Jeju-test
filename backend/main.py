import os
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from models import TripRequest, TripRouteResponse, Place, DayRoute
from optimizer import optimize_trip, infer_place_type, build_day_route_from_order
from naver_api import search_local_place, geocode_address, recommend_nearby
from naver_import import fetch_naver_shared_bookmarks, parse_naver_bookmarks
from db import init_db, save_shared_route, get_shared_route
from llm_advisor import get_day_advice
from regions import get_region_config, RegionId

app = FastAPI(title="Travel Route Planner MVP")


@app.on_event("startup")
def on_startup():
    init_db()

allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health_check():
    return {"status": "ok"}


@app.get("/api/search-place")
def search_place(query: str, region: RegionId = "jeju"):
    """
    네이버 지역 검색 API로 장소 후보 검색.
    이 서비스는 지역별 여행 플래너라 검색 범위를 선택된 지역으로 한정한다.
    지역 검색 API에 위치 반경 파라미터가 없어서, 검색어 자체에
    지역 키워드를 붙이고 결과도 주소 기준으로 한 번 더 필터링한다.
    """
    try:
        cfg = get_region_config(region)
        results = search_local_place(f"{cfg.search_keyword} {query}")
        filtered = [
            r for r in results
            if r.get("address") and cfg.search_keyword in r["address"]
        ]
        return {"items": filtered}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/geocode")
def geocode(query: str):
    """
    주소를 좌표로 변환.
    """
    try:
        result = geocode_address(query)
        if result is None:
            raise HTTPException(status_code=404, detail="No geocoding result")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class NaverFavoritesImportRequest(BaseModel):
    url: str


@app.post("/api/import/naver-favorites", response_model=List[Place])
def import_naver_favorites(req: NaverFavoritesImportRequest):
    """
    네이버 지도 저장 리스트 공유 링크(또는 shareId)를 받아 서버에서 직접
    가져와 Place 목록으로 변환한다. (공식 export 기능이 없어 내부 API 사용)
    """
    try:
        payload = fetch_naver_shared_bookmarks(req.url)
        return parse_naver_bookmarks(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"네이버 지도에서 가져오기 실패: {e}")


@app.post("/api/optimize", response_model=TripRouteResponse)
def optimize(req: TripRequest):
    """
    N일차 여행 루트 최적화.
    """
    normalized_places = []

    for p in req.places:
        if p.type == "etc":
            inferred = infer_place_type(p.naver_category)
            p = p.model_copy(update={"type": inferred})

        normalized_places.append(p)

    routes = optimize_trip(
        places=normalized_places,
        num_days=req.num_days,
        start_hour=req.start_hour,
        end_hour=req.end_hour,
        accommodation_by_day=req.accommodation_by_day,
        must_place_by_day=req.must_place_by_day,
        airport_id=req.airport_id,
        region=req.region,
    )

    return TripRouteResponse(routes=routes)


@app.get("/api/recommend")
def recommend(lat: float, lng: float, category: str, display: int = 5):
    """
    좌표 주변 카테고리별 추천 장소 (별점 데이터 없음, 네이버 지역 검색 결과 순).
    """
    try:
        items = recommend_nearby(lat=lat, lng=lng, category=category, display=display)
        return {"items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ReorderDayRequest(BaseModel):
    day: int
    places: List[Place]
    start_place: Place | None = None
    end_place: Place | None = None
    start_hour: int = 9


@app.post("/api/reorder-day", response_model=DayRoute)
def reorder_day(req: ReorderDayRequest):
    """
    사용자가 드래그로 정한 방문 순서를 그대로 써서 그날 route를 다시 조립한다.
    """
    try:
        return build_day_route_from_order(
            day=req.day,
            ordered_places=req.places,
            start_place=req.start_place,
            end_place=req.end_place,
            start_hour=req.start_hour,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class DayAdviceRequest(BaseModel):
    route: DayRoute
    restaurant_candidates: List[dict] = []
    cafe_candidates: List[dict] = []
    region: RegionId = "jeju"


@app.post("/api/day-advice")
def day_advice(req: DayAdviceRequest):
    """
    하루 경로 + 주변 식당/카페 후보를 Claude에 보내서 끼워 넣을 만한
    곳과 이유를 추천받는다.
    """
    try:
        return get_day_advice(
            route=req.route,
            restaurant_candidates=req.restaurant_candidates,
            cafe_candidates=req.cafe_candidates,
            region_name=get_region_config(req.region).display_name,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ShareRouteRequest(BaseModel):
    places: List[Place]
    num_days: int
    routes: List[DayRoute]
    region: RegionId = "jeju"


@app.post("/api/routes/share")
def create_shared_route(req: ShareRouteRequest):
    """
    생성된 루트를 저장하고 공유용 id를 발급한다.
    """
    route_id = save_shared_route(req.model_dump())
    return {"id": route_id}


@app.get("/api/routes/share/{route_id}")
def read_shared_route(route_id: str):
    data = get_shared_route(route_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Route not found")
    return data
