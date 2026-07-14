import math
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations

import numpy as np
from typing import List, Dict
from sklearn.cluster import KMeans

from models import Place, DayRoute, RouteStop, LatLng
from naver_api import get_driving_route
from regions import get_region_config, RegionId


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
    주어진 장소 집합에 대한 실제 도로 거리/시간/경로 행렬 (NCP Directions,
    실시간 교통 반영). 쌍마다 API를 병렬로 호출해서 채우고, 경로를
    못 찾거나 호출이 실패한 쌍은 직선거리 + 평균 30km/h 가정으로
    보정한 값을 채운다 (이 경우 실제 도로 path는 없음).
    """

    def __init__(self, points: List[Place]):
        # key: frozenset({a.id, b.id})
        # value: (distance_km, duration_min, path, from_id)
        #   path는 from_id 지점에서 시작하는 방향으로 저장되어 있어서,
        #   반대 방향으로 조회하면 뒤집어서 돌려준다.
        self._table: dict[frozenset, tuple[float, float, list[tuple[float, float]], str]] = {}

        unique_points = list({p.id: p for p in points}.values())
        pairs = list(combinations(unique_points, 2))

        with ThreadPoolExecutor(max_workers=8) as executor:
            for key, value in executor.map(self._fetch_pair, pairs):
                self._table[key] = value

    @staticmethod
    def _fetch_pair(pair: tuple[Place, Place]):
        a, b = pair
        result = get_driving_route(a.lat, a.lng, b.lat, b.lng)

        if result is None:
            dist = haversine_km(a, b)
            distance_km, duration_min, path = dist, dist / 30 * 60, []
        else:
            distance_km, duration_min, path = result

        return frozenset((a.id, b.id)), (distance_km, duration_min, path, a.id)

    def get(self, a: Place, b: Place) -> tuple[float, float]:
        if a.id == b.id:
            return (0.0, 0.0)

        cached = self._table.get(frozenset((a.id, b.id)))
        if cached is not None:
            return cached[0], cached[1]

        dist = haversine_km(a, b)
        return (dist, dist / 30 * 60)

    def distance_km(self, a: Place, b: Place) -> float:
        return self.get(a, b)[0]

    def duration_min(self, a: Place, b: Place) -> float:
        return self.get(a, b)[1]

    def path(self, a: Place, b: Place) -> list[tuple[float, float]]:
        """a->b 구간의 실제 도로 좌표열. 못 구했으면 빈 리스트."""
        if a.id == b.id:
            return []

        cached = self._table.get(frozenset((a.id, b.id)))
        if cached is None or not cached[2]:
            return []

        _, _, path, from_id = cached
        return path if from_id == a.id else list(reversed(path))


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


MAX_RESTAURANTS_PER_DAY = 3

# 자정 기준 분(minute) 단위 식사 시간대.
LUNCH_WINDOW = (11 * 60, 14 * 60)
DINNER_WINDOW = (17 * 60, 20 * 60)


def is_preferred_dinner_place(p: Place, dinner_keywords: list[str]) -> bool:
    text = " ".join(
        filter(None, [p.food_category, p.naver_category, p.name])
    )
    return any(keyword in text for keyword in dinner_keywords)


def select_restaurants_for_day(restaurants: List[Place]) -> List[Place]:
    """
    하루 최대 MAX_RESTAURANTS_PER_DAY개까지만 식당을 고른다.
    식사 슬롯(breakfast/lunch/dinner)이 지정된 식당을 우선 하나씩 고르고,
    자리가 남으면 슬롯 미지정 식당 중 priority가 높은 순으로 채운다.
    """
    by_slot: Dict[str, Place] = {}
    unslotted: List[Place] = []

    for r in restaurants:
        if not r.meal_slot:
            unslotted.append(r)
            continue
        current = by_slot.get(r.meal_slot)
        if current is None or r.priority > current.priority:
            by_slot[r.meal_slot] = r

    selected = list(by_slot.values())

    remaining_slots = MAX_RESTAURANTS_PER_DAY - len(selected)
    if remaining_slots > 0:
        selected.extend(
            sorted(unslotted, key=lambda r: -r.priority)[:remaining_slots]
        )

    return selected[:MAX_RESTAURANTS_PER_DAY]


def select_region_seeds(
    num_days: int, region_seeds: list[tuple[float, float]]
) -> list[tuple[float, float]]:
    """
    num_days가 전체 권역 수보다 적을 때, 앞에서부터 자르면 특정 방향
    (동/서)이 통째로 누락될 수 있다. Farthest-point sampling으로
    최대한 지역 전체에 고르게 퍼진 시드를 고른다.
    """
    seeds = region_seeds

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
    region_seeds: list[tuple[float, float]],
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

    if num_days <= len(region_seeds):
        init = np.array(select_region_seeds(num_days, region_seeds))
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


def _arrival_clock_minutes(
    route: List[Place],
    matrix: DistanceMatrix,
    start_place: Place | None,
    start_hour: int,
) -> List[int]:
    """
    route의 각 인덱스 앞에 도착(=직전 장소에서 막 출발)하는 시각을
    자정 기준 분 단위로 반환한다. 길이는 len(route)+1이고, 마지막
    값은 route를 다 돈 뒤의 시각이다.
    """
    times = []
    clock = start_hour * 60
    prev = start_place

    for p in route:
        times.append(clock)
        if prev is not None:
            _, travel_min = matrix.get(prev, p)
            clock += round(travel_min)
        clock += p.duration_min
        prev = p

    times.append(clock)
    return times


def _best_insert_index(
    route: List[Place],
    place: Place,
    matrix: DistanceMatrix,
    start_place: Place | None,
    start_hour: int,
    time_window: tuple[int, int] | None = None,
) -> int:
    """
    route에 place를 끼워 넣을 위치를 고른다.
    time_window(자정 기준 분)가 있으면, 그 시간대 안에 도착하는 위치들
    중 거리 증가가 가장 적은 곳을 고르고, 시간대 안에 드는 위치가 없으면
    그 시간대에 가장 가까운 위치를 쓴다. time_window가 없으면 거리
    증가가 가장 적은 위치를 고른다.
    """
    times = _arrival_clock_minutes(route, matrix, start_place, start_hour)

    scored = []
    for i in range(len(route) + 1):
        prev = route[i - 1] if i > 0 else start_place
        nxt = route[i] if i < len(route) else None

        added = (
            (matrix.distance_km(prev, place) if prev else 0.0)
            + (matrix.distance_km(place, nxt) if nxt else 0.0)
            - (matrix.distance_km(prev, nxt) if prev and nxt else 0.0)
        )
        scored.append((i, times[i], added))

    if time_window:
        lo, hi = time_window
        in_window = [s for s in scored if lo <= s[1] <= hi]
        if in_window:
            return min(in_window, key=lambda s: s[2])[0]
        return min(scored, key=lambda s: min(abs(s[1] - lo), abs(s[1] - hi)))[0]

    return min(scored, key=lambda s: s[2])[0]


def _parse_time_to_minutes(t: str) -> int:
    """'HH:MM' -> 자정 기준 분(minute)."""
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def insert_meal_places(
    route: List[Place],
    matrix: DistanceMatrix,
    start_place: Place | None,
    start_hour: int,
    dinner_keywords: list[str],
) -> List[Place]:
    """
    식당/카페를 실제 이동 거리와 식사 시간대(점심/저녁)를 함께 고려해
    끼워 넣는다. 하루 최대 MAX_RESTAURANTS_PER_DAY개까지만 식당을 넣고,
    각 식당 바로 뒤에는 (남은 카페가 있다면) 카페를 붙인다.
    """
    all_restaurants = [p for p in route if p.type == "restaurant"]
    cafes = [p for p in route if p.type == "cafe"]
    new_route = [p for p in route if p.type not in ("restaurant", "cafe")]

    if not all_restaurants:
        return route

    restaurants = select_restaurants_for_day(all_restaurants)

    lunch_candidates = [r for r in restaurants if r.meal_slot == "lunch"]
    dinner_candidates = [r for r in restaurants if r.meal_slot == "dinner"]

    lunch = lunch_candidates[0] if lunch_candidates else None

    # 저녁은 여러 후보 중 횟집/돼지고기 계열을 우선한다.
    dinner = None
    if dinner_candidates:
        preferred = [
            r for r in dinner_candidates
            if is_preferred_dinner_place(r, dinner_keywords)
        ]
        dinner = preferred[0] if preferred else dinner_candidates[0]

    others = [
        r for r in restaurants
        if r is not lunch and r is not dinner
    ]

    remaining_cafes = cafes[:]

    def take_cafe() -> Place | None:
        return remaining_cafes.pop(0) if remaining_cafes else None

    def insert_meal(place: Place, window: tuple[int, int] | None) -> None:
        idx = _best_insert_index(new_route, place, matrix, start_place, start_hour, window)
        new_route.insert(idx, place)
        cafe = take_cafe()
        if cafe:
            new_route.insert(idx + 1, cafe)

    if lunch:
        insert_meal(lunch, LUNCH_WINDOW)

    if dinner:
        insert_meal(dinner, DINNER_WINDOW)

    for r in others:
        insert_meal(r, None)

    for cafe in remaining_cafes[:]:
        idx = _best_insert_index(new_route, cafe, matrix, start_place, start_hour, None)
        new_route.insert(idx, cafe)

    return new_route


def build_day_route(
    day: int,
    day_places: List[Place],
    start_place: Place | None,
    end_place: Place | None,
    start_hour: int,
    dinner_keywords: list[str],
) -> DayRoute:
    """
    하루 route 생성. 실제 도로 거리/시간(NCP Directions)을 기준으로 짠다.
    preferred_time이 지정된 장소는 nearest-neighbor/2-opt 대상에서 빼고,
    그 시간대(±30분) 근처 위치에 따로 끼워 넣는다.
    """
    anchor_points = [p for p in [start_place, end_place] if p is not None]
    matrix = DistanceMatrix(anchor_points + day_places)

    timed_places = sorted(
        (p for p in day_places if p.preferred_time),
        key=lambda p: _parse_time_to_minutes(p.preferred_time),
    )
    untimed_places = [p for p in day_places if not p.preferred_time]

    route = nearest_neighbor_route(start_place, untimed_places, matrix)
    route = two_opt(route, matrix, start=start_place, end=end_place)
    route = insert_meal_places(route, matrix, start_place, start_hour, dinner_keywords)

    for p in timed_places:
        target = _parse_time_to_minutes(p.preferred_time)
        window = (target - 30, target + 30)
        idx = _best_insert_index(route, p, matrix, start_place, start_hour, window)
        route.insert(idx, p)

    return finalize_day_route(day, route, start_place, end_place, start_hour, matrix)


def insert_place_into_day(
    day: int,
    ordered_places: List[Place],
    new_place: Place,
    start_place: Place | None,
    end_place: Place | None,
    start_hour: int,
) -> DayRoute:
    """
    이미 만들어진 하루 route(ordered_places)에 새 장소 하나만 거리 증가가
    가장 적은 위치로 끼워 넣는다. 기존 순서는 그대로 유지하고, 다른
    날짜에는 전혀 영향을 주지 않는다.
    """
    anchor_points = [p for p in [start_place, end_place] if p is not None]
    matrix = DistanceMatrix(anchor_points + ordered_places + [new_place])

    idx = _best_insert_index(ordered_places, new_place, matrix, start_place, start_hour)
    new_route = ordered_places[:]
    new_route.insert(idx, new_place)

    return finalize_day_route(day, new_route, start_place, end_place, start_hour, matrix)


def build_day_route_from_order(
    day: int,
    ordered_places: List[Place],
    start_place: Place | None,
    end_place: Place | None,
    start_hour: int,
) -> DayRoute:
    """
    사용자가 지도/목록에서 드래그로 직접 정한 순서를 그대로 써서 route를 만든다.
    nearest-neighbor/2-opt로 다시 정렬하지 않고, 그 순서 기준으로
    거리/시간/실제 도로 path만 새로 계산한다.
    """
    anchor_points = [p for p in [start_place, end_place] if p is not None]
    matrix = DistanceMatrix(anchor_points + ordered_places)

    return finalize_day_route(day, ordered_places, start_place, end_place, start_hour, matrix)


def finalize_day_route(
    day: int,
    route: List[Place],
    start_place: Place | None,
    end_place: Place | None,
    start_hour: int,
    matrix: "DistanceMatrix",
) -> DayRoute:
    """
    이미 순서가 정해진 route(방문 순서)를 받아 도착 시각/거리/실제 도로
    path를 계산해서 DayRoute로 조립한다. 순서를 정하는 로직(2-opt 등)과
    조립하는 로직을 분리해서, 자동 최적화 경로와 사용자가 수동으로 정한
    경로 둘 다 같은 방식으로 조립되게 한다.
    """
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

    ordered_places = (
        ([start_place] if start_place else []) + route + ([end_place] if end_place else [])
    )
    path = build_full_path(ordered_places, matrix)

    return DayRoute(
        day=day,
        stops=stops,
        total_distance_km=round(total_distance, 2),
        total_duration_min=current_min,
        path=[LatLng(lat=lat, lng=lng) for lat, lng in path],
        start_place=start_place,
        end_place=end_place,
    )


def build_full_path(
    ordered_places: List[Place], matrix: DistanceMatrix
) -> list[tuple[float, float]]:
    """
    방문 순서대로 구간(leg)별 실제 도로 path를 이어붙여 하루 전체 경로를
    만든다. 특정 구간만 도로 API가 실패했으면 그 구간만 직선으로 잇고,
    나머지 구간은 그대로 실제 도로를 따라가게 한다.
    """
    full_path: list[tuple[float, float]] = []

    for a, b in zip(ordered_places, ordered_places[1:]):
        leg = matrix.path(a, b) or [(a.lat, a.lng), (b.lat, b.lng)]

        if full_path and leg[0] == full_path[-1]:
            full_path.extend(leg[1:])
        else:
            full_path.extend(leg)

    return full_path


def optimize_trip(
    places: List[Place],
    num_days: int,
    start_hour: int = 9,
    end_hour: int = 21,
    accommodation_by_day: dict[int, str] | None = None,
    must_place_by_day: dict[int, List[str]] | None = None,
    airport_id: str | None = None,
    region: RegionId = "jeju",
) -> List[DayRoute]:
    cfg = get_region_config(region)

    assigned = assign_places_to_days(
        places=places,
        num_days=num_days,
        must_place_by_day=must_place_by_day,
        region_seeds=cfg.region_seeds,
    )

    airport = None
    if airport_id:
        airport = next((p for p in places if p.id == airport_id), None)

    routes = []

    for day in range(1, num_days + 1):
        # accommodation_by_day[d]는 "d일차 밤에 묵는 숙소"를 뜻한다.
        # 그래서 d일차의 시작은 전날 밤 숙소(d-1)여야 하고, d일차의 끝은
        # 그날 밤 숙소(d)여야 한다. 즉 하루의 끝이 다음날의 시작으로
        # 자연스럽게 이어진다. (마지막날은 숙소를 지정할 필요가 없어서
        # accommodation_by_day에 값이 없고, 그 경우 전날 숙소를 그대로 씀)
        tonight_accommodation = choose_accommodation_for_day(
            places=places,
            day=day,
            accommodation_by_day=accommodation_by_day,
        )
        last_night_accommodation = (
            choose_accommodation_for_day(
                places=places,
                day=day - 1,
                accommodation_by_day=accommodation_by_day,
            )
            if day > 1
            else None
        )

        # 1일차는 공항에서 출발, 마지막날은 공항에서 여행이 끝난다.
        # 그 외에는 전날 밤 숙소에서 출발해서 그날 밤 숙소에서 끝난다.
        start_place = (
            airport if (day == 1 and airport)
            else (last_night_accommodation or tonight_accommodation)
        )
        end_place = airport if (day == num_days and airport) else tonight_accommodation

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
            dinner_keywords=cfg.dinner_keywords,
        )

        routes.append(route)

    return routes
