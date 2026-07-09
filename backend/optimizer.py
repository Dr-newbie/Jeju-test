import math
import numpy as np
from typing import List, Dict
from sklearn.cluster import KMeans

from models import Place, DayRoute, RouteStop


def haversine_km(a: Place, b: Place) -> float:
    """
    위경도 기반 직선거리.
    MVP에서는 직선거리로 시작하고,
    이후 Naver Directions API 또는 distance matrix로 교체 가능.
    """
    R = 6371.0

    lat1 = math.radians(a.lat)
    lon1 = math.radians(a.lng)
    lat2 = math.radians(b.lat)
    lon2 = math.radians(b.lng)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    x = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )

    return 2 * R * math.asin(math.sqrt(x))


def infer_place_type(naver_category: str | None) -> str:
    """
    네이버 카테고리를 내부 카테고리로 단순 매핑.
    실제 서비스에서는 category mapping table로 분리하는 게 좋음.
    """
    if not naver_category:
        return "etc"

    c = naver_category.lower()

    if "음식" in c or "식당" in c or "한식" in c or "중식" in c or "일식" in c:
        return "restaurant"
    if "카페" in c or "디저트" in c:
        return "cafe"
    if "호텔" in c or "숙박" in c or "펜션" in c:
        return "accommodation"
    if "관광" in c or "명소" in c or "박물관" in c or "전시" in c:
        return "tourist_spot"
    if "쇼핑" in c or "시장" in c:
        return "shopping"

    return "etc"


def choose_accommodation_for_day(
    places: List[Place],
    day: int,
    accommodation_by_day: dict[int, str] | None,
) -> Place | None:
    accommodations = [p for p in places if p.type == "accommodation"]

    if accommodation_by_day and day in accommodation_by_day:
        target_id = accommodation_by_day[day]
        for p in places:
            if p.id == target_id:
                return p

    if accommodations:
        return accommodations[0]

    return None


def assign_places_to_days(
    places: List[Place],
    num_days: int,
    must_place_by_day: dict[int, List[str]] | None = None,
) -> Dict[int, List[Place]]:
    """
    장소를 N일차에 배정.
    1순위: preferred_day
    2순위: must_place_by_day
    3순위: 좌표 기반 KMeans
    """
    result = {day: [] for day in range(1, num_days + 1)}

    fixed_ids = set()

    # 날짜별 필수 장소 고정
    if must_place_by_day:
        place_by_id = {p.id: p for p in places}
        for day, ids in must_place_by_day.items():
            for pid in ids:
                if pid in place_by_id and 1 <= day <= num_days:
                    result[day].append(place_by_id[pid])
                    fixed_ids.add(pid)

    # preferred_day 고정
    for p in places:
        if p.id in fixed_ids:
            continue
        if p.preferred_day and 1 <= p.preferred_day <= num_days:
            result[p.preferred_day].append(p)
            fixed_ids.add(p.id)

    remaining = [
        p for p in places
        if p.id not in fixed_ids and p.type != "accommodation"
    ]

    if not remaining:
        return result

    if len(remaining) <= num_days:
        for i, p in enumerate(remaining):
            result[(i % num_days) + 1].append(p)
        return result

    coords = np.array([[p.lat, p.lng] for p in remaining])
    kmeans = KMeans(n_clusters=num_days, random_state=42, n_init="auto")
    labels = kmeans.fit_predict(coords)

    for p, label in zip(remaining, labels):
        result[int(label) + 1].append(p)

    return result


def nearest_neighbor_route(
    start: Place | None,
    places: List[Place],
) -> List[Place]:
    """
    간단한 nearest-neighbor route.
    """
    if not places:
        return []

    unvisited = places[:]
    route = []

    current = start if start is not None else unvisited.pop(0)

    if start is None:
        route.append(current)

    while unvisited:
        next_place = min(unvisited, key=lambda p: haversine_km(current, p))
        route.append(next_place)
        unvisited.remove(next_place)
        current = next_place

    return route


def route_distance_km(route: List[Place], start: Place | None = None, end: Place | None = None) -> float:
    if not route:
        return 0.0

    total = 0.0
    current = start or route[0]

    for p in route:
        if p.id != current.id:
            total += haversine_km(current, p)
        current = p

    if end is not None and current.id != end.id:
        total += haversine_km(current, end)

    return total


def two_opt(route: List[Place], start: Place | None = None, end: Place | None = None) -> List[Place]:
    """
    2-opt로 경로 개선.
    """
    if len(route) < 4:
        return route

    best = route[:]
    best_distance = route_distance_km(best, start=start, end=end)

    improved = True
    while improved:
        improved = False

        for i in range(1, len(best) - 2):
            for j in range(i + 1, len(best)):
                if j - i == 1:
                    continue

                new_route = best[:]
                new_route[i:j] = reversed(new_route[i:j])

                new_distance = route_distance_km(new_route, start=start, end=end)

                if new_distance < best_distance:
                    best = new_route
                    best_distance = new_distance
                    improved = True

    return best


def insert_meal_places(route: List[Place]) -> List[Place]:
    """
    식당을 점심/저녁 위치 근처에 넣는 단순 rule.
    현재는 타입이 restaurant인 장소를 route 내에 유지하되,
    관광지 사이에 끼우는 정도로 단순화.
    """
    restaurants = [p for p in route if p.type == "restaurant"]
    non_restaurants = [p for p in route if p.type != "restaurant"]

    if not restaurants:
        return route

    lunch = None
    dinner = None
    others = []

    for r in restaurants:
        if r.meal_slot == "lunch" and lunch is None:
            lunch = r
        elif r.meal_slot == "dinner" and dinner is None:
            dinner = r
        else:
            others.append(r)

    new_route = non_restaurants[:]

    if lunch:
        idx = max(1, len(new_route) // 3)
        new_route.insert(idx, lunch)

    if dinner:
        idx = max(1, int(len(new_route) * 0.75))
        new_route.insert(idx, dinner)

    new_route.extend(others)

    return new_route


def build_day_route(
    day: int,
    day_places: List[Place],
    start_place: Place | None,
    start_hour: int,
) -> DayRoute:
    """
    하루 route 생성.
    """
    route = nearest_neighbor_route(start_place, day_places)
    route = two_opt(route, start=start_place, end=start_place)
    route = insert_meal_places(route)

    stops = []
    current_min = 0
    current_place = start_place

    total_distance = 0.0

    for order, p in enumerate(route, start=1):
        if current_place is not None:
            dist = haversine_km(current_place, p)
            total_distance += dist
            travel_min = int(dist / 30 * 60)  # 평균 30km/h 가정
        else:
            travel_min = 0

        current_min += travel_min

        stops.append(
            RouteStop(
                order=order,
                place=p,
                arrival_min_from_day_start=current_min,
                note=f"예상 도착 {start_hour + current_min // 60:02d}:{current_min % 60:02d}",
            )
        )

        current_min += p.duration_min
        current_place = p

    if start_place and current_place:
        total_distance += haversine_km(current_place, start_place)

    return DayRoute(
        day=day,
        stops=stops,
        total_distance_km=round(total_distance, 2),
        total_duration_min=current_min,
    )


def optimize_trip(
    places: List[Place],
    num_days: int,
    start_hour: int = 9,
    end_hour: int = 21,
    accommodation_by_day: dict[int, str] | None = None,
    must_place_by_day: dict[int, List[str]] | None = None,
) -> List[DayRoute]:
    assigned = assign_places_to_days(
        places=places,
        num_days=num_days,
        must_place_by_day=must_place_by_day,
    )

    routes = []

    for day in range(1, num_days + 1):
        start_place = choose_accommodation_for_day(
            places=places,
            day=day,
            accommodation_by_day=accommodation_by_day,
        )

        day_places = [
            p for p in assigned[day]
            if p.type != "accommodation"
        ]

        route = build_day_route(
            day=day,
            day_places=day_places,
            start_place=start_place,
            start_hour=start_hour,
        )

        routes.append(route)

    return routes
