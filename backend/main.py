import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import TripRequest, TripRouteResponse
from optimizer import optimize_trip, infer_place_type
from naver_api import search_local_place, geocode_address

app = FastAPI(title="Travel Route Planner MVP")

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
    """
    try:
        results = search_local_place(query)
        return {"items": results}
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
    )

    return TripRouteResponse(routes=routes)
