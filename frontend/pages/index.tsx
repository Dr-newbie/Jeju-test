import { useState } from "react";
import axios from "axios";
import dynamic from "next/dynamic";
import type { Place, DayRoute } from "../types";
import { DAY_COLORS, placeIcon } from "../constants";
import { REGION_CONFIGS, DEFAULT_REGION, type RegionId } from "../regions";

const NaverMap = dynamic(() => import("../components/NaverMap"), {
  ssr: false,
});

const RECOMMEND_CATEGORIES = ["맛집", "카페", "관광지"];

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5001";

const BASE_PLACE_TYPES: { value: string; label: string }[] = [
  { value: "etc", label: "미분류" },
  { value: "tourist_spot", label: "관광지" },
  { value: "restaurant", label: "식당" },
  { value: "cafe", label: "카페" },
  { value: "shopping", label: "쇼핑" },
  { value: "accommodation", label: "숙소" },
  { value: "airport", label: "공항" },
];

function getPlaceTypes(anchorLabel: string) {
  return BASE_PLACE_TYPES.map((t) =>
    t.value === "airport" ? { ...t, label: anchorLabel } : t
  );
}

export default function Home() {
  const [region, setRegion] = useState<RegionId>(DEFAULT_REGION);
  const regionConfig = REGION_CONFIGS[region];
  const PLACE_TYPES = getPlaceTypes(regionConfig.anchorLabel);

  const [places, setPlaces] = useState<Place[]>(
    REGION_CONFIGS[DEFAULT_REGION].samplePlaces
  );
  const [numDays, setNumDays] = useState(3);
  const [routes, setRoutes] = useState<DayRoute[]>([]);
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [airportId, setAirportId] = useState<string>(
    REGION_CONFIGS[DEFAULT_REGION].defaultAnchorId
  );
  const [accommodationByDay, setAccommodationByDay] = useState<
    Record<number, string>
  >({
    1: REGION_CONFIGS[DEFAULT_REGION].defaultAccommodationId,
    2: REGION_CONFIGS[DEFAULT_REGION].defaultAccommodationId,
  });
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [sharing, setSharing] = useState(false);
  const [recommendations, setRecommendations] = useState<
    Record<number, Record<string, any[]>>
  >({});
  const [recommendLoading, setRecommendLoading] = useState<number | null>(
    null
  );
  const [dayAdvice, setDayAdvice] = useState<
    Record<
      number,
      {
        summary: string;
        recommendations: {
          place_name: string;
          reason: string;
          insert_after_order: number;
        }[];
      }
    >
  >({});
  const [adviceLoading, setAdviceLoading] = useState<number | null>(null);
  const [optimizing, setOptimizing] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [hoveredDay, setHoveredDay] = useState<number | null>(null);
  const [naverShareUrl, setNaverShareUrl] = useState("");
  const [importing, setImporting] = useState(false);

  const accommodations = places.filter((p) => p.type === "accommodation");
  const placesByType = PLACE_TYPES.map((t) => ({
    ...t,
    items: places.filter((p) => p.type === t.value),
  })).filter((group) => group.items.length > 0);

  const showToast = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(null), 2200);
  };

  const handleRegionChange = (newRegion: RegionId) => {
    const cfg = REGION_CONFIGS[newRegion];
    setRegion(newRegion);
    setPlaces(cfg.samplePlaces);
    setAirportId(cfg.defaultAnchorId);
    setAccommodationByDay(
      Object.fromEntries(
        Array.from({ length: Math.max(0, numDays - 1) }, (_, i) => i + 1).map(
          (day) => [day, cfg.defaultAccommodationId]
        )
      )
    );
    setRoutes([]);
    setSearchResults([]);
    setQuery("");
    setShareUrl(null);
    setRecommendations({});
    setRecommendLoading(null);
    setDayAdvice({});
    setAdviceLoading(null);
    setHoveredDay(null);
  };

  const optimize = async (placesOverride?: Place[]) => {
    setOptimizing(true);
    try {
      const res = await axios.post(`${BACKEND_URL}/api/optimize`, {
        places: placesOverride ?? places,
        num_days: numDays,
        start_hour: 9,
        end_hour: 21,
        accommodation_by_day: Object.fromEntries(
          Object.entries(accommodationByDay).filter(
            ([day, id]) => Number(day) <= numDays && id
          )
        ),
        airport_id: airportId || undefined,
        region,
      });

      setRoutes(res.data.routes);
    } finally {
      setOptimizing(false);
    }
  };

  const searchPlace = async () => {
    if (!query.trim()) return;

    const res = await axios.get(`${BACKEND_URL}/api/search-place`, {
      params: { query, region },
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
    setSearchResults([]);
    showToast(`"${newPlace.name}" 추가했어요`);
  };

  const importNaverFavorites = async () => {
    if (!naverShareUrl.trim()) return;

    setImporting(true);
    try {
      const res = await axios.post(`${BACKEND_URL}/api/import/naver-favorites`, {
        url: naverShareUrl.trim(),
      });

      const existingIds = new Set(places.map((p) => p.id));
      const imported: Place[] = res.data.filter(
        (p: Place) => !existingIds.has(p.id)
      );

      setPlaces((prev) => [...prev, ...imported]);
      setNaverShareUrl("");
      showToast(
        imported.length > 0
          ? `${imported.length}개 장소를 가져왔어요`
          : "이미 가져온 장소들이에요"
      );
    } catch (e) {
      alert("가져오기에 실패했습니다. 공유 링크를 확인해주세요.");
    } finally {
      setImporting(false);
    }
  };

  const removePlace = (id: string) => {
    setPlaces((prev) => prev.filter((p) => p.id !== id));
  };

  const updatePlaceDay = (id: string, day: number | null) => {
    setPlaces((prev) =>
      prev.map((p) => (p.id === id ? { ...p, preferred_day: day } : p))
    );
  };

  const updatePlaceType = (id: string, type: string) => {
    setPlaces((prev) =>
      prev.map((p) => (p.id === id ? { ...p, type } : p))
    );
  };

  const updatePlaceMealSlot = (
    id: string,
    mealSlot: "breakfast" | "lunch" | "dinner" | null
  ) => {
    setPlaces((prev) =>
      prev.map((p) => (p.id === id ? { ...p, meal_slot: mealSlot } : p))
    );
  };

  const updatePlaceTime = (id: string, time: string | null) => {
    setPlaces((prev) =>
      prev.map((p) => (p.id === id ? { ...p, preferred_time: time } : p))
    );
  };

  const shareRoute = async () => {
    setSharing(true);
    try {
      const res = await axios.post(`${BACKEND_URL}/api/routes/share`, {
        places,
        num_days: numDays,
        routes,
        region,
      });
      setShareUrl(`${window.location.origin}/shared/${res.data.id}`);
    } finally {
      setSharing(false);
    }
  };

  const loadRecommendations = async (route: DayRoute) => {
    setRecommendLoading(route.day);

    const lat =
      route.stops.reduce((sum, s) => sum + s.place.lat, 0) /
      route.stops.length;
    const lng =
      route.stops.reduce((sum, s) => sum + s.place.lng, 0) /
      route.stops.length;

    try {
      const results = await Promise.all(
        RECOMMEND_CATEGORIES.map((category) =>
          axios
            .get(`${BACKEND_URL}/api/recommend`, {
              params: { lat, lng, category, display: 5 },
            })
            .then((res) => [category, res.data.items] as const)
        )
      );

      setRecommendations((prev) => ({
        ...prev,
        [route.day]: Object.fromEntries(results),
      }));
    } finally {
      setRecommendLoading(null);
    }
  };

  const loadDayAdvice = async (route: DayRoute) => {
    setAdviceLoading(route.day);

    try {
      let recs = recommendations[route.day];

      if (!recs) {
        const lat =
          route.stops.reduce((sum, s) => sum + s.place.lat, 0) /
          route.stops.length;
        const lng =
          route.stops.reduce((sum, s) => sum + s.place.lng, 0) /
          route.stops.length;

        const [restaurantRes, cafeRes] = await Promise.all([
          axios.get(`${BACKEND_URL}/api/recommend`, {
            params: { lat, lng, category: "맛집", display: 5 },
          }),
          axios.get(`${BACKEND_URL}/api/recommend`, {
            params: { lat, lng, category: "카페", display: 5 },
          }),
        ]);

        recs = { 맛집: restaurantRes.data.items, 카페: cafeRes.data.items };
        setRecommendations((prev) => ({ ...prev, [route.day]: recs! }));
      }

      const res = await axios.post(`${BACKEND_URL}/api/day-advice`, {
        route,
        restaurant_candidates: recs["맛집"] ?? [],
        cafe_candidates: recs["카페"] ?? [],
        region,
      });

      setDayAdvice((prev) => ({ ...prev, [route.day]: res.data }));
    } finally {
      setAdviceLoading(null);
    }
  };

  const reorderStops = async (
    route: DayRoute,
    fromIndex: number,
    toIndex: number
  ) => {
    if (fromIndex === toIndex) return;

    const newStops = [...route.stops];
    const [moved] = newStops.splice(fromIndex, 1);
    newStops.splice(toIndex, 0, moved);

    const orderedPlaces = newStops.map((s) => s.place);

    try {
      const res = await axios.post(`${BACKEND_URL}/api/reorder-day`, {
        day: route.day,
        places: orderedPlaces,
        start_place: route.start_place ?? null,
        end_place: route.end_place ?? null,
        start_hour: 9,
      });

      setRoutes((prev) =>
        prev.map((r) => (r.day === route.day ? res.data : r))
      );
      showToast(`${route.day}일차 동선을 반영했어요`);
    } catch {
      showToast("순서 변경에 실패했어요");
    }
  };

  const applyAdviceRecommendation = (day: number, placeName: string) => {
    const recs = recommendations[day];
    if (!recs) return;

    const candidate = [...(recs["맛집"] ?? []), ...(recs["카페"] ?? [])].find(
      (item) => item.name === placeName
    );
    if (!candidate) return;

    addRecommendedPlace(candidate, day);
  };

  const addRecommendedPlace = (item: any, day: number) => {
    if (item.lat == null || item.lng == null) return;

    const newPlace: Place = {
      id: `place_${Date.now()}`,
      name: item.name,
      address: item.address,
      lat: item.lat,
      lng: item.lng,
      type: "etc",
      naver_category: item.category,
      priority: 3,
      must_visit: false,
      preferred_day: day,
      duration_min: 60,
    };

    const updatedPlaces = [...places, newPlace];
    setPlaces(updatedPlaces);
    setRecommendations((prev) => {
      const next = { ...prev };
      delete next[day];
      return next;
    });
    showToast(`"${newPlace.name}" 추가하고 경로에 반영했어요`);
    optimize(updatedPlaces);
  };

  return (
    <main className="page">
      <div className="region-bar">
        <label>
          지역
          <select
            value={region}
            onChange={(e) => handleRegionChange(e.target.value as RegionId)}
            disabled={optimizing}
          >
            {Object.values(REGION_CONFIGS).map((cfg) => (
              <option key={cfg.id} value={cfg.id}>
                {cfg.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="app-header">
        <div className="title">{regionConfig.titleCopy}</div>
        <div className="subtitle">{regionConfig.subtitleCopy}</div>
      </div>

      <section className="card">
        <div className="section-title">
          <span className="step">1</span>장소 검색
        </div>
        <div className="search-row">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="장소명 검색 ex. 성산일출봉"
          />
          <button className="btn-primary" onClick={searchPlace}>
            검색
          </button>
        </div>

        {searchResults.length > 0 && (
          <div style={{ marginTop: 12 }}>
            {searchResults.map((item, idx) => (
              <div key={idx} className="result-card">
                <b>{item.name}</b>
                <div className="meta">{item.category}</div>
                <div className="meta">{item.address}</div>
                <button
                  className="btn-sm"
                  onClick={() => addSearchResult(item)}
                >
                  이 장소 추가
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="import-naver">
          <div className="section-title" style={{ fontSize: 14 }}>
            네이버 지도 즐겨찾기 가져오기
          </div>
          <p className="hint">
            네이버 지도 앱에서 저장 리스트를 공유 링크로 만든 뒤, 그 링크를
            아래에 붙여넣으세요.
          </p>
          <div className="search-row">
            <input
              value={naverShareUrl}
              onChange={(e) => setNaverShareUrl(e.target.value)}
              placeholder="https://naver.me/... 공유 링크"
            />
            <button
              className="btn-primary"
              onClick={importNaverFavorites}
              disabled={importing}
            >
              {importing ? "가져오는 중..." : "가져오기"}
            </button>
          </div>
        </div>
      </section>

      <section className="card">
        <div className="section-title">
          <span className="step">2</span>여행 설정
        </div>
        <div className="trip-settings">
          <label>
            여행 일수
            <input
              type="number"
              value={numDays}
              min={1}
              onChange={(e) => setNumDays(Number(e.target.value))}
            />
          </label>

          <label>
            {regionConfig.anchorLabel}
            <select
              value={airportId}
              onChange={(e) => setAirportId(e.target.value)}
            >
              <option value="">미지정</option>
              {places.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>

          <button
            className="btn-primary"
            onClick={() => optimize()}
            disabled={optimizing}
          >
            {optimizing ? "루트 생성 중..." : "루트 생성"}
          </button>
        </div>
        <p className="hint">
          1일차는 {regionConfig.anchorLabel}에서 출발하고, 마지막날은{" "}
          {regionConfig.anchorLabel}에서 여행이 끝나요. 실제 도로 거리를
          계산하느라 장소가 많으면 몇 초 걸릴 수 있어요.
        </p>

        <p className="hint" style={{ marginTop: 0 }}>
          마지막날은 {regionConfig.anchorLabel}에서 마무리되니 숙소가 필요
          없어요.
        </p>

        <div className="day-accommodation-list">
          {Array.from({ length: Math.max(0, numDays - 1) }, (_, i) => i + 1).map((day) => (
            <label key={day}>
              {day}일차 숙소
              <select
                value={accommodationByDay[day] ?? ""}
                onChange={(e) =>
                  setAccommodationByDay((prev) => ({
                    ...prev,
                    [day]: e.target.value,
                  }))
                }
              >
                <option value="">미지정</option>
                {accommodations.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </label>
          ))}
          {accommodations.length === 0 && (
            <p className="hint">
              숙소로 지정된 장소가 없습니다. 아래 "저장된 장소"에서 장소
              타입을 "숙소"로 바꿔주세요.
            </p>
          )}
        </div>
      </section>

      <section className="card">
        <div className="section-title">
          <span className="step">3</span>저장된 장소
        </div>
        <p className="hint" style={{ marginTop: -4 }}>
          시간 아이콘에 방문 희망 시간을 넣으면 루트 생성 시 그 시간대
          근처에 배치돼요.
        </p>
        {placesByType.map((group) => (
          <div key={group.value} className="place-group">
            <div className="place-group-title">
              {placeIcon(group.value)} {group.label}
              <span className="place-group-count">{group.items.length}</span>
            </div>

            {group.items.map((p) => (
              <div key={p.id} className="place-row">
                <span className="place-icon">{placeIcon(p.type)}</span>
                <div className="place-body">
                  <span className="place-info">
                    {p.name}{" "}
                    <span className="meta-inline">
                      {p.naver_category ? `· ${p.naver_category}` : ""}
                    </span>
                  </span>

                  <div className="place-controls">
                    <select
                      value={p.type}
                      onChange={(e) => updatePlaceType(p.id, e.target.value)}
                    >
                      {PLACE_TYPES.map((t) => (
                        <option key={t.value} value={t.value}>
                          {t.label}
                        </option>
                      ))}
                    </select>

                    {p.type === "restaurant" && (
                      <select
                        value={p.meal_slot ?? ""}
                        onChange={(e) =>
                          updatePlaceMealSlot(
                            p.id,
                            (e.target.value || null) as
                              | "breakfast"
                              | "lunch"
                              | "dinner"
                              | null
                          )
                        }
                      >
                        <option value="">식사 미지정</option>
                        <option value="breakfast">아침</option>
                        <option value="lunch">점심</option>
                        <option value="dinner">저녁</option>
                      </select>
                    )}

                    <input
                      type="time"
                      value={p.preferred_time ?? ""}
                      title="희망 방문 시간 (선택)"
                      onChange={(e) =>
                        updatePlaceTime(p.id, e.target.value || null)
                      }
                    />

                    <button
                      className="btn-danger btn-sm"
                      onClick={() => removePlace(p.id)}
                    >
                      삭제
                    </button>
                  </div>

                  <div className="day-toggle-group">
                    {Array.from({ length: numDays }, (_, i) => i + 1).map(
                      (day) => {
                        const active = p.preferred_day === day;
                        return (
                          <button
                            key={day}
                            type="button"
                            className={`day-toggle${active ? " active" : ""}`}
                            style={
                              active
                                ? {
                                    [
                                      "--day-color" as any
                                    ]: DAY_COLORS[
                                      (day - 1) % DAY_COLORS.length
                                    ],
                                  }
                                : undefined
                            }
                            onClick={() =>
                              updatePlaceDay(p.id, active ? null : day)
                            }
                          >
                            {day}일차
                          </button>
                        );
                      }
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ))}
        {placesByType.length === 0 && (
          <p className="hint">아직 저장된 장소가 없습니다.</p>
        )}
      </section>

      <section className="card">
        <div className="section-title">
          <span className="step">4</span>지도
        </div>
        <div className="map-wrap">
          <NaverMap
            routes={routes}
            hoveredDay={hoveredDay}
            onHoverDay={setHoveredDay}
          />
        </div>
      </section>

      <section>
        <div className="section-title" style={{ padding: "0 4px" }}>
          <span className="step">5</span>날짜별 루트
        </div>
        {routes.length > 0 && (
          <p className="hint" style={{ padding: "0 4px", marginTop: -8 }}>
            날짜 동그라미에 마우스를 올리면 지도에서 그날 경로만 강조돼요.
          </p>
        )}

        {routes.length > 0 && (
          <div className="card">
            <button
              className="btn-primary"
              onClick={shareRoute}
              disabled={sharing}
            >
              {sharing ? "공유 링크 생성 중..." : "🔗 공유 링크 만들기"}
            </button>
            {shareUrl && (
              <div className="search-row" style={{ marginTop: 10 }}>
                <input value={shareUrl} readOnly />
                <button
                  className="btn-sm"
                  onClick={() => navigator.clipboard.writeText(shareUrl)}
                >
                  복사
                </button>
              </div>
            )}
          </div>
        )}

        {routes.map((route, idx) => {
          const dayColor = DAY_COLORS[idx % DAY_COLORS.length];

          return (
            <div
              key={route.day}
              className="route-card"
              style={{ ["--day-color" as any]: dayColor }}
            >
              <div className="route-card-header">
                <span
                  className="day-badge"
                  onMouseEnter={() => setHoveredDay(route.day)}
                  onMouseLeave={() => setHoveredDay(null)}
                >
                  {route.day}
                </span>
                <h3>{route.day}일차</h3>
              </div>

              <div className="stat-row">
                <span className="stat-pill">
                  🚗 {route.total_distance_km}km
                </span>
                <span className="stat-pill">
                  ⏱ {route.total_duration_min}분
                </span>
              </div>

              <ol className="stop-list">
                {route.stops.map((stop, idx) => (
                  <li
                    key={stop.order}
                    className="stop-item"
                    draggable
                    title="드래그해서 순서 변경"
                    style={{ cursor: "grab" }}
                    onDragStart={(e) => {
                      e.dataTransfer.effectAllowed = "move";
                      e.dataTransfer.setData(
                        "text/plain",
                        `${route.day}:${idx}`
                      );
                    }}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      const [dayStr, fromIdxStr] = e.dataTransfer
                        .getData("text/plain")
                        .split(":");
                      if (Number(dayStr) !== route.day) return;
                      reorderStops(route, Number(fromIdxStr), idx);
                    }}
                  >
                    <span className="stop-order">{stop.order}</span>
                    <span>
                      {placeIcon(stop.place.type)} <b>{stop.place.name}</b>
                      <span className="stop-meta">{stop.note}</span>
                    </span>
                  </li>
                ))}
              </ol>

              <button
                className="btn-sm"
                style={{ marginTop: 14 }}
                onClick={() => loadRecommendations(route)}
                disabled={recommendLoading === route.day}
              >
                {recommendLoading === route.day
                  ? "추천 불러오는 중..."
                  : "이 날 주변 추천 보기"}
              </button>

              <button
                className="btn-sm"
                style={{ marginTop: 8 }}
                onClick={() => loadDayAdvice(route)}
                disabled={adviceLoading === route.day}
              >
                {adviceLoading === route.day
                  ? "AI 분석 중..."
                  : "🤖 AI 추천 받기"}
              </button>

              {dayAdvice[route.day] && (
                <div style={{ marginTop: 10 }}>
                  <p className="hint" style={{ marginTop: 0 }}>
                    {dayAdvice[route.day].summary}
                  </p>
                  {dayAdvice[route.day].recommendations.length === 0 ? (
                    <p className="hint">추가로 추천할 만한 곳이 없어요.</p>
                  ) : (
                    dayAdvice[route.day].recommendations.map((rec, idx) => (
                      <div key={idx} className="result-card">
                        <b>{rec.place_name}</b>
                        <div className="meta">{rec.reason}</div>
                        <button
                          className="btn-sm"
                          onClick={() =>
                            applyAdviceRecommendation(
                              route.day,
                              rec.place_name
                            )
                          }
                        >
                          이 장소 추가
                        </button>
                      </div>
                    ))
                  )}
                </div>
              )}

              {recommendations[route.day] && (
                <div>
                  {RECOMMEND_CATEGORIES.map((category) => (
                    <div key={category} className="recommend-group">
                      <b>{category}</b>
                      {(recommendations[route.day][category] ?? []).map(
                        (item, idx) => (
                          <div key={idx} className="result-card">
                            <b>{item.name}</b>
                            <div className="meta">{item.category}</div>
                            <div className="meta">{item.address}</div>
                            <button
                              className="btn-sm"
                              onClick={() =>
                                addRecommendedPlace(item, route.day)
                              }
                            >
                              이 장소 추가
                            </button>
                          </div>
                        )
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </section>

      {toast && <div className="toast">{toast}</div>}
    </main>
  );
}
