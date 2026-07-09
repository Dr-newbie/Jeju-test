import { useState } from "react";
import axios from "axios";
import dynamic from "next/dynamic";

const NaverMap = dynamic(() => import("../components/NaverMap"), {
  ssr: false,
});

type Place = {
  id: string;
  name: string;
  address?: string;
  lat: number;
  lng: number;
  type: string;
  naver_category?: string;
  priority?: number;
  must_visit?: boolean;
  preferred_day?: number | null;
  duration_min?: number;
  meal_slot?: "breakfast" | "lunch" | "dinner" | null;
  food_category?: string | null;
};

type DayRoute = {
  day: number;
  stops: {
    order: number;
    place: Place;
    arrival_min_from_day_start: number;
    note?: string;
  }[];
  total_distance_km: number;
  total_duration_min: number;
};

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

const samplePlaces: Place[] = [
  {
    id: "hotel_1",
    name: "제주시 숙소",
    lat: 33.4996,
    lng: 126.5312,
    type: "accommodation",
    duration_min: 0,
  },
  {
    id: "p1",
    name: "성산일출봉",
    lat: 33.4581,
    lng: 126.9425,
    type: "tourist_spot",
    priority: 5,
    must_visit: true,
    preferred_day: 2,
    duration_min: 90,
  },
  {
    id: "p2",
    name: "우도",
    lat: 33.5065,
    lng: 126.9556,
    type: "tourist_spot",
    priority: 5,
    duration_min: 180,
  },
  {
    id: "p3",
    name: "협재해수욕장",
    lat: 33.3946,
    lng: 126.2397,
    type: "tourist_spot",
    priority: 4,
    duration_min: 90,
  },
  {
    id: "p4",
    name: "카페 후보",
    lat: 33.4507,
    lng: 126.9142,
    type: "cafe",
    duration_min: 60,
  },
  {
    id: "r1",
    name: "점심 식당 후보",
    lat: 33.512,
    lng: 126.529,
    type: "restaurant",
    meal_slot: "lunch",
    food_category: "한식",
    duration_min: 60,
  },
  {
    id: "r2",
    name: "저녁 식당 후보",
    lat: 33.247,
    lng: 126.56,
    type: "restaurant",
    meal_slot: "dinner",
    food_category: "흑돼지",
    duration_min: 80,
  },
];

export default function Home() {
  const [places, setPlaces] = useState<Place[]>(samplePlaces);
  const [numDays, setNumDays] = useState(3);
  const [routes, setRoutes] = useState<DayRoute[]>([]);
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);

  const optimize = async () => {
    const res = await axios.post(`${BACKEND_URL}/api/optimize`, {
      places,
      num_days: numDays,
      start_hour: 9,
      end_hour: 21,
      accommodation_by_day: {
        1: "hotel_1",
        2: "hotel_1",
        3: "hotel_1",
      },
      must_place_by_day: {
        2: ["p1"],
      },
    });

    setRoutes(res.data.routes);
  };

  const searchPlace = async () => {
    if (!query.trim()) return;

    const res = await axios.get(`${BACKEND_URL}/api/search-place`, {
      params: { query },
    });

    setSearchResults(res.data.items);
  };

  const addSearchResult = async (item: any) => {
    if (!item.address) {
      alert("주소가 없는 장소입니다.");
      return;
    }

    const geo = await axios.get(`${BACKEND_URL}/api/geocode`, {
      params: { query: item.address },
    });

    const newPlace: Place = {
      id: `place_${Date.now()}`,
      name: item.name,
      address: geo.data.address,
      lat: geo.data.lat,
      lng: geo.data.lng,
      type: "etc",
      naver_category: item.category,
      priority: 3,
      must_visit: false,
      preferred_day: null,
      duration_min: 60,
    };

    setPlaces((prev) => [...prev, newPlace]);
  };

  const removePlace = (id: string) => {
    setPlaces((prev) => prev.filter((p) => p.id !== id));
  };

  const updatePlaceDay = (id: string, day: number | null) => {
    setPlaces((prev) =>
      prev.map((p) => (p.id === id ? { ...p, preferred_day: day } : p))
    );
  };

  return (
    <main className="page">
      <h1 className="title">Jeju Travel Test</h1>

      <section className="section">
        <h2>1. 장소 검색</h2>
        <div className="search-row">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="장소명 검색 ex. 성산일출봉"
          />
          <button onClick={searchPlace}>검색</button>
        </div>

        <div style={{ marginTop: 12 }}>
          {searchResults.map((item, idx) => (
            <div key={idx} className="result-card">
              <b>{item.name}</b>
              <div className="meta">{item.category}</div>
              <div className="meta">{item.address}</div>
              <button onClick={() => addSearchResult(item)}>
                이 장소 추가
              </button>
            </div>
          ))}
        </div>
      </section>

      <section className="section">
        <h2>2. 여행 설정</h2>
        <div className="trip-settings">
          <label>
            여행 일수:
            <input
              type="number"
              value={numDays}
              min={1}
              onChange={(e) => setNumDays(Number(e.target.value))}
            />
          </label>
          <button onClick={optimize}>루트 생성</button>
        </div>
      </section>

      <section className="section">
        <h2>3. 저장된 장소</h2>
        {places.map((p) => (
          <div key={p.id} className="place-row">
            <span className="place-info">
              {p.name} / {p.type} / {p.naver_category ?? "-"}
            </span>

            <select
              value={p.preferred_day ?? ""}
              onChange={(e) =>
                updatePlaceDay(
                  p.id,
                  e.target.value === "" ? null : Number(e.target.value)
                )
              }
            >
              <option value="">날짜 미지정</option>
              {Array.from({ length: numDays }, (_, i) => i + 1).map((day) => (
                <option key={day} value={day}>
                  {day}일차 고정
                </option>
              ))}
            </select>

            <button onClick={() => removePlace(p.id)}>삭제</button>
          </div>
        ))}
      </section>

      <section className="section">
        <h2>4. 지도</h2>
        <div className="map-wrap">
          <NaverMap routes={routes} />
        </div>
      </section>

      <section>
        <h2>5. 날짜별 루트</h2>
        {routes.map((route) => (
          <div key={route.day} className="route-card">
            <h3>{route.day}일차</h3>
            <p>
              총 거리: {route.total_distance_km}km / 총 소요시간:{" "}
              {route.total_duration_min}분
            </p>

            <ol>
              {route.stops.map((stop) => (
                <li key={stop.order}>
                  <b>{stop.place.name}</b> - {stop.place.type} - {stop.note}
                </li>
              ))}
            </ol>
          </div>
        ))}
      </section>
    </main>
  );
}
