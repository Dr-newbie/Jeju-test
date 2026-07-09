import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import axios from "axios";
import dynamic from "next/dynamic";
import type { DayRoute } from "../../types";

const NaverMap = dynamic(() => import("../../components/NaverMap"), {
  ssr: false,
});

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export default function SharedRoute() {
  const router = useRouter();
  const { id } = router.query;

  const [routes, setRoutes] = useState<DayRoute[] | null>(null);
  const [error, setError] = useState<string | null>(null);

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
        <p>{error}</p>
      </main>
    );
  }

  if (!routes) {
    return (
      <main className="page">
        <p>불러오는 중...</p>
      </main>
    );
  }

  return (
    <main className="page">
      <h1 className="title">공유된 여행 루트</h1>

      <section className="section">
        <div className="map-wrap">
          <NaverMap routes={routes} />
        </div>
      </section>

      <section>
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
