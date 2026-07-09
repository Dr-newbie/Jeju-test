import math
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations

import numpy as np
from typing import List, Dict
from sklearn.cluster import KMeans

from models import Place, DayRoute, RouteStop, LatLng
from naver_api import get_driving_route, get_driving_path


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


class DistanceMatrix:
    """
    주어진 장소 집합에 대한 실제 도로 거리/시간 행렬 (NCP Directions,
    실시간 교통 반영). 쌍마다 API를 병렬로 호출해서 채우고, 경로를
    못 찾거나 호출이 실패한 쌍은 직선거리 + 평균 30km/h 가정으로
    보정한 값을 채운다.
    """

    def __init__(self, points: List[Place]):
        self._table: dict[frozenset, tuple[float, float]] = {}

        unique_points = list({p.id: p for p in points}.values())
        pairs = list(combinations(unique_points, 2))

        with ThreadPoolExecutor(max_workers=8) as executor:
            for key, value in executor.map(self._fetch_pair, pairs):
                self._table[key] = value

    @staticmethod
    def _fetch_pair(pair: tuple[Place, Place]) -> tuple[frozenset, tuple[float, float]]:
        a, b = pair
        result = get_driving_route(a.lat, a.lng, b.lat, b.lng)

        if result is None:
            dist = haversine_km(a, b)
            result = (dist, dist / 30 * 60)  # 평균 30km/h 가정으로 보정

        return frozenset((a.id, b.id)), result

    def get(self, a: Place, b: Place) -> tuple[float, float]:
        if a.id == b.id:
            return (0.0, 0.0)

        cached = self._table.get(frozenset((a.id, b.id)))
        if cached is not None:
            return cached

        dist = haversine_km(a, b)
        return (dist, dist / 30 * 60)

    def distance_km(self, a: Place, b: Place) -> float:
        return self.get(a, b)[0]

    def duration_min(self, a: Place, b: Place) -> float:
        return self.get(a, b)[1]


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
    if "공항" in c or "항공" in c:
        return "airport"

    return "etc"


DINNER_PREFERRED_KEYWORDS = ["회", "횟집", "물회", "돼지", "흑돼지", "제주삼겹"]


def is_preferred_dinner_place(p: Place) -> bool:
    text = " ".join(
        filter(None, [p.food_category, p.naver_category, p.name])
    )
    return any(keyword in text for keyword in DINNER_PREFERRED_KEYWORDS)


# 제주 주요 권역의 대표 좌표. 날짜별로 장소를 나눌 때 이 좌표를 KMeans의
# 초기 중심으로 사용해서, 임의의 초기값보다 실제 여행 동선에 맞는
# 권역 단위 클러스터가 나오도록 유도한다.
JEJU_REGION_SEEDS = [
    (33.4996, 126.5312),  # 제주시내
    (33.4633, 126.3306),  # 애월/한림
    (33.3016, 126.1650),  # 한경/고산 (서쪽 끝)
    (33.2496, 126.4132),  # 중문/서귀포
    (33.2809, 126.6389),  # 남원/표선
    (33.4581, 126.9425),  # 성산/우도
    (33.5427, 126.6668),  # 조천/함덕
]


def select_region_seeds(num_days: int) -> list[tuple[float, float]]:
    """
    num_days가 전체 권역 수보다 적을 때, 앞에서부터 자르면 특정 방향
    (동/서)이 통째로 누락될 수 있다. Farthest-point sampling으로
    최대한 섬 전체에 고르게 퍼진 시드를 고른다.
    """
    seeds = JEJU_REGION_SEEDS

    if num_days >= len(seeds):
        return seeds

    selected = [seeds[0]]
    remaining = seeds[1:]

    while len(selected) < num_days:
        best = max(
            remaining,
            key=lambda s: min(
                (s[0] - c[0]) ** 2 + (s[1] - c[1]) ** 2 for c in selected
            ),
        )
        selected.append(best)
        remaining.remove(best)

    return selected


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
        if p.id not in fixed_ids
        and p.type not in ("accommodation", "airport")
    ]

    if not remaining:
        return result

    if len(remaining) <= num_days:
        for i, p in enumerate(remaining):
            result[(i % num_days) + 1].append(p)
        return result

    coords = np.array([[p.lat, p.lng] for p in remaining])

    if num_days <= len(JEJU_REGION_SEEDS):
        init = np.array(select_region_seeds(num_days))
        kmeans = KMeans(n_clusters=num_days, init=init, n_init=1)
    else:
        kmeans = KMeans(n_clusters=num_days, random_state=42, n_init="auto")

    labels = kmeans.fit_predict(coords)

    for p, label in zip(remaining, labels):
        result[int(label) + 1].append(p)

    return result


def nearest_neighbor_route(
    start: Place | None,
    places: List[Place],
    matrix: DistanceMatrix,
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
        next_place = min(unvisited, key=lambda p: matrix.distance_km(current, p))
        route.append(next_place)
        unvisited.remove(next_place)
        current = next_place

    return route


def route_distance_km(
    route: List[Place],
    matrix: DistanceMatrix,
    start: Place | None = None,
    end: Place | None = None,
) -> float:
    if not route:
        return 0.0

    total = 0.0
    current = start or route[0]

    for p in route:
        if p.id != current.id:
            total += matrix.distance_km(current, p)
        current = p

    if end is not None and current.id != end.id:
        total += matrix.distance_km(current, end)

    return total


def two_opt(
    route: List[Place],
    matrix: DistanceMatrix,
    start: Place | None = None,
    end: Place | None = None,
) -> List[Place]:
    """
    2-opt로 경로 개선.
    """
    if len(route) < 4:
        return route

    best = route[:]
    best_distance = route_distance_km(best, matrix, start=start, end=end)

    improved = True
    while improved:
        improved = False

        for i in range(1, len(best) - 2):
            for j in range(i + 1, len(best)):
                if j - i == 1:
                    continue

                new_route = best[:]
                new_route[i:j] = reversed(new_route[i:j])

                new_distance = route_distance_km(new_route, matrix, start=start, end=end)

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

    lunch_candidates = [r for r in restaurants if r.meal_slot == "lunch"]
    dinner_candidates = [r for r in restaurants if r.meal_slot == "dinner"]

    lunch = lunch_candidates[0] if lunch_candidates else None

    # 저녁은 여러 후보 중 횟집/돼지고기 계열을 우선한다.
    dinner = None
    if dinner_candidates:
        preferred = [r for r in dinner_candidates if is_preferred_dinner_place(r)]
        dinner = preferred[0] if preferred else dinner_candidates[0]

    others = [
        r for r in restaurants
        if r is not lunch and r is not dinner
    ]

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
    end_place: Place | None,
    start_hour: int,
) -> DayRoute:
    """
    하루 route 생성. 실제 도로 거리/시간(NCP Directions)을 기준으로 짠다.
    """
    anchor_points = [p for p in [start_place, end_place] if p is not None]
    matrix = DistanceMatrix(anchor_points + day_places)

    route = nearest_neighbor_route(start_place, day_places, matrix)
    route = two_opt(route, matrix, start=start_place, end=end_place)
    route = insert_meal_places(route)

    stops = []
    current_min = 0
    current_place = start_place

    total_distance = 0.0

    for order, p in enumerate(route, start=1):
        if current_place is not None:
            dist, travel_min = matrix.get(current_place, p)
            total_distance += dist
        else:
            travel_min = 0

        current_min += round(travel_min)

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

    if end_place and current_place and current_place.id != end_place.id:
        total_distance += matrix.distance_km(current_place, end_place)

    ordered_points = [
        (p.lat, p.lng)
        for p in ([start_place] if start_place else []) + route + ([end_place] if end_place else [])
    ]
    path = get_driving_path(ordered_points) or []

    return DayRoute(
        day=day,
        stops=stops,
        total_distance_km=round(total_distance, 2),
        total_duration_min=current_min,
        path=[LatLng(lat=lat, lng=lng) for lat, lng in path],
    )


def optimize_trip(
    places: List[Place],
    num_days: int,
    start_hour: int = 9,
    end_hour: int = 21,
    accommodation_by_day: dict[int, str] | None = None,
    must_place_by_day: dict[int, List[str]] | None = None,
    airport_id: str | None = None,
) -> List[DayRoute]:
    assigned = assign_places_to_days(
        places=places,
        num_days=num_days,
        must_place_by_day=must_place_by_day,
    )

    airport = None
    if airport_id:
        airport = next((p for p in places if p.id == airport_id), None)

    routes = []

    for day in range(1, num_days + 1):
        accommodation = choose_accommodation_for_day(
            places=places,
            day=day,
            accommodation_by_day=accommodation_by_day,
        )

        # 1일차는 공항에서 출발, 마지막날은 공항에서 여행이 끝난다.
        # 그 외 날짜는 그날 배정된 숙소를 시작/종료 기준으로 삼는다.
        start_place = airport if (day == 1 and airport) else accommodation
        end_place = airport if (day == num_days and airport) else accommodation

        day_places = [
            p for p in assigned[day]
            if p.type not in ("accommodation", "airport")
        ]

        route = build_day_route(
            day=day,
            day_places=day_places,
            start_place=start_place,
            end_place=end_place,
            start_hour=start_hour,
        )

        routes.append(route)

    return routes
