import os
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from models import TripRequest, TripRouteResponse, Place, DayRoute
from optimizer import optimize_trip, infer_place_type
from naver_api import search_local_place, geocode_address, recommend_nearby
from db import init_db, save_shared_route, get_shared_route

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
def search_place(query: str):
    """
    네이버 지역 검색 API로 장소 후보 검색.
    이 서비스는 제주 여행 플래너라 검색 범위를 제주로 한정한다.
    지역 검색 API에 위치 반경 파라미터가 없어서, 검색어 자체에
    "제주"를 붙이고 결과도 주소 기준으로 한 번 더 필터링한다.
    """
    try:
        results = search_local_place(f"제주 {query}")
        jeju_results = [
            r for r in results
            if r.get("address") and "제주" in r["address"]
        ]
        return {"items": jeju_results}
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


class ShareRouteRequest(BaseModel):
    places: List[Place]
    num_days: int
    routes: List[DayRoute]


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
