import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import axios from "axios";
import dynamic from "next/dynamic";
import type { DayRoute } from "../../types";
import { DAY_COLORS, placeIcon } from "../../constants";

const NaverMap = dynamic(() => import("../../components/NaverMap"), {
  ssr: false,
});

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5001";

export default function SharedRoute() {
  const router = useRouter();
  const { id } = router.query;

  const [routes, setRoutes] = useState<DayRoute[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hoveredDay, setHoveredDay] = useState<number | null>(null);

  useEffect(() => {
    if (!id || typeof id !== "string") return;

    axios
      .get(`${BACKEND_URL}/api/routes/share/${id}`)
      .then((res) => setRoutes(res.data.routes))
      .catch(() => setError("공유된 경로를 찾을 수 없습니다."));
  }, [id]);

  if (error) {
    return (
      <main className="page">
        <div className="app-header">
          <div className="title">🍊 제주 여행 루트 플래너</div>
        </div>
        <div className="card">
          <p style={{ margin: 0 }}>{error}</p>
        </div>
      </main>
    );
  }

  if (!routes) {
    return (
      <main className="page">
        <div className="app-header">
          <div className="title">🍊 제주 여행 루트 플래너</div>
        </div>
        <div className="card">
          <p style={{ margin: 0 }}>불러오는 중...</p>
        </div>
      </main>
    );
  }

  return (
    <main className="page">
      <div className="app-header">
        <div className="title">🍊 공유된 여행 루트</div>
        <div className="subtitle">다른 사람이 만든 제주 여행 코스예요</div>
      </div>

      <section className="card">
        <div className="map-wrap">
          <NaverMap
            routes={routes}
            hoveredDay={hoveredDay}
            onHoverDay={setHoveredDay}
          />
        </div>
      </section>

      <section>
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
                {route.stops.map((stop) => (
                  <li key={stop.order} className="stop-item">
                    <span className="stop-order">{stop.order}</span>
                    <span>
                      {placeIcon(stop.place.type)} <b>{stop.place.name}</b>
                      <span className="stop-meta">{stop.note}</span>
                    </span>
                  </li>
                ))}
              </ol>
            </div>
          );
        })}
      </section>
    </main>
  );
}
