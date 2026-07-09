from pydantic import BaseModel, Field
from typing import Optional, List, Literal


PlaceType = Literal[
    "accommodation",
    "restaurant",
    "cafe",
    "tourist_spot",
    "shopping",
    "etc",
]


class Place(BaseModel):
    id: str
    name: str
    address: Optional[str] = None
    lat: float
    lng: float

    type: PlaceType = "etc"
    naver_category: Optional[str] = None

    priority: int = Field(default=3, ge=1, le=5)
    must_visit: bool = False
    preferred_day: Optional[int] = None

    duration_min: int = 60

    meal_slot: Optional[Literal["breakfast", "lunch", "dinner"]] = None
    food_category: Optional[str] = None

    open_time: Optional[str] = None
    close_time: Optional[str] = None


class TripRequest(BaseModel):
    places: List[Place]
    num_days: int = Field(ge=1)
    start_hour: int = 9
    end_hour: int = 21

    accommodation_by_day: Optional[dict[int, str]] = None
    must_place_by_day: Optional[dict[int, List[str]]] = None


class RouteStop(BaseModel):
    order: int
    place: Place
    arrival_min_from_day_start: int
    note: Optional[str] = None


class DayRoute(BaseModel):
    day: int
    stops: List[RouteStop]
    total_distance_km: float
    total_duration_min: int


class TripRouteResponse(BaseModel):
    routes: List[DayRoute]
