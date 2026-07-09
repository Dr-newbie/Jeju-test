import { useEffect, useRef } from "react";
import type { DayRoute, Place } from "../types";
import { DAY_COLORS, placeIcon } from "../constants";

declare global {
  interface Window {
    naver: any;
  }
}

const DIMMED_COLOR = "#c7ccd1";

type Props = {
  routes: DayRoute[];
  hoveredDay?: number | null;
};

export default function NaverMap({ routes, hoveredDay = null }: Props) {
  const mapRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<any>(null);
  const markersRef = useRef<any[]>([]);
  const polylinesRef = useRef<any[]>([]);
  const routesRef = useRef<DayRoute[]>(routes);
  const hoveredDayRef = useRef<number | null>(hoveredDay);

  routesRef.current = routes;
  hoveredDayRef.current = hoveredDay;

  const redraw = () => {
    const map = mapInstanceRef.current;
    if (!map || !window.naver || !window.naver.maps) return;

    markersRef.current.forEach((m) => m.setMap(null));
    polylinesRef.current.forEach((p) => p.setMap(null));
    markersRef.current = [];
    polylinesRef.current = [];

    drawRoutes(
      map,
      routesRef.current,
      hoveredDayRef.current,
      markersRef.current,
      polylinesRef.current
    );
  };

  const fitToRoutes = () => {
    const map = mapInstanceRef.current;
    if (!map || !window.naver || !window.naver.maps) return;

    const bounds = new window.naver.maps.LatLngBounds();
    let hasPoint = false;

    routesRef.current.forEach((route) => {
      [route.start_place, route.end_place, ...route.stops.map((s) => s.place)]
        .filter((p): p is NonNullable<typeof p> => !!p)
        .forEach((p) => {
          bounds.extend(new window.naver.maps.LatLng(p.lat, p.lng));
          hasPoint = true;
        });
    });

    if (hasPoint) {
      map.fitBounds(bounds);
    }
  };

  // 지도(Map 인스턴스)는 최초 한 번만 만든다. routes/hoveredDay가 바뀔 때마다
  // 새로 만들면 사용자가 옮겨둔 시점/줌이 매번 초기화되어 버린다.
  useEffect(() => {
    const clientId = process.env.NEXT_PUBLIC_NAVER_MAP_CLIENT_ID;

    if (!clientId) {
      console.error("NEXT_PUBLIC_NAVER_MAP_CLIENT_ID is missing");
      return;
    }

    const scriptId = "naver-map-script";

    const initMap = () => {
      if (!mapRef.current) {
        console.error("mapRef is missing");
        return;
      }

      if (!window.naver || !window.naver.maps) {
        console.error(
          "Naver Maps SDK is not loaded. Check API key, service URL, and script loading."
        );
        return;
      }

      if (!mapInstanceRef.current) {
        const firstStop = routesRef.current?.[0]?.stops?.[0]?.place;

        const center = firstStop
          ? new window.naver.maps.LatLng(firstStop.lat, firstStop.lng)
          : new window.naver.maps.LatLng(37.5665, 126.978);

        mapInstanceRef.current = new window.naver.maps.Map(mapRef.current, {
          center,
          zoom: 11,
        });
      }

      fitToRoutes();
      redraw();
    };

    const existingScript = document.getElementById(scriptId);

    if (existingScript) {
      if (window.naver && window.naver.maps) {
        initMap();
      } else {
        existingScript.addEventListener("load", initMap);
      }
      return;
    }

    const script = document.createElement("script");
    script.id = scriptId;
    script.src = `https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId=${clientId}`;
    script.async = true;

    script.onload = initMap;

    script.onerror = () => {
      console.error("Failed to load Naver Maps SDK script");
    };

    document.head.appendChild(script);

    return () => {
      script.removeEventListener("load", initMap);
    };
  }, []);

  // routes가 새로 생기면 그 범위에 맞춰 지도를 재중심/재줌한다.
  useEffect(() => {
    fitToRoutes();
    redraw();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routes]);

  // hoveredDay만 바뀔 때는 지도 시점은 그대로 두고 강조 스타일만 다시 그린다.
  useEffect(() => {
    redraw();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hoveredDay]);

  return <div ref={mapRef} style={{ width: "100%", height: "100%" }} />;
}

function drawRoutes(
  map: any,
  routes: DayRoute[],
  hoveredDay: number | null,
  markers: any[],
  polylines: any[]
) {
  if (!window.naver || !window.naver.maps || !routes?.length) return;

  routes.forEach((route, idx) => {
    const isDimmed = hoveredDay != null && hoveredDay !== route.day;
    const color = isDimmed ? DIMMED_COLOR : DAY_COLORS[idx % DAY_COLORS.length];
    const zIndex = isDimmed ? 0 : 100;

    // 실제 도로를 따라가는 path가 있으면 그걸 쓰고, 없으면(예: 옛 공유 링크)
    // 방문지를 직선으로 이은 경로로 대체한다.
    const path =
      route.path && route.path.length >= 2
        ? route.path.map(
            (p) => new window.naver.maps.LatLng(p.lat, p.lng)
          )
        : route.stops.map(
            (stop) =>
              new window.naver.maps.LatLng(stop.place.lat, stop.place.lng)
          );

    route.stops.forEach((stop) => {
      const position = new window.naver.maps.LatLng(
        stop.place.lat,
        stop.place.lng
      );

      const marker = new window.naver.maps.Marker({
        position,
        map,
        title: `${route.day}일차 ${stop.order}. ${stop.place.name}`,
        zIndex,
        icon: isDimmed
          ? {
              content: `
                <div style="
                  width:22px;height:22px;border-radius:50%;
                  background:${DIMMED_COLOR};border:2px solid #fff;
                  box-shadow:0 1px 3px rgba(0,0,0,0.25);
                "></div>
              `,
              anchor: new window.naver.maps.Point(11, 11),
            }
          : undefined,
      });

      markers.push(marker);

      const infoWindow = new window.naver.maps.InfoWindow({
        content: `
          <div style="padding:8px;min-width:180px;">
            <b>${route.day}일차 ${stop.order}. ${stop.place.name}</b><br/>
            <span>${stop.place.type}</span><br/>
            <span>${stop.note ?? ""}</span>
          </div>
        `,
      });

      window.naver.maps.Event.addListener(marker, "click", () => {
        infoWindow.open(map, marker);
      });
    });

    // 숙소/공항(하루의 시작·끝 지점)은 방문지 번호 마커와 구분되는
    // 별도 아이콘으로 표시한다.
    [
      { place: route.start_place, label: "출발" },
      { place: route.end_place, label: "도착" },
    ].forEach(({ place, label }) => {
      if (!place) return;
      addAnchorMarker(
        map,
        place,
        `${route.day}일차 ${label}`,
        color,
        zIndex,
        markers
      );
    });

    if (path.length >= 2) {
      const polyline = new window.naver.maps.Polyline({
        map,
        path,
        strokeColor: color,
        strokeOpacity: isDimmed ? 0.6 : 0.85,
        strokeWeight: isDimmed ? 3 : 4,
        zIndex,
      });

      polylines.push(polyline);
    }
  });
}

function addAnchorMarker(
  map: any,
  place: Place,
  title: string,
  color: string,
  zIndex: number,
  markers: any[]
) {
  const marker = new window.naver.maps.Marker({
    position: new window.naver.maps.LatLng(place.lat, place.lng),
    map,
    title,
    zIndex,
    icon: {
      content: `
        <div style="
          width:30px;height:30px;border-radius:50%;
          background:${color};border:2px solid #fff;
          display:flex;align-items:center;justify-content:center;
          font-size:15px;box-shadow:0 2px 6px rgba(0,0,0,0.35);
        ">${placeIcon(place.type)}</div>
      `,
      anchor: new window.naver.maps.Point(15, 15),
    },
  });

  markers.push(marker);

  const infoWindow = new window.naver.maps.InfoWindow({
    content: `
      <div style="padding:8px;min-width:160px;">
        <b>${title}</b><br/>
        <span>${place.name}</span>
      </div>
    `,
  });

  window.naver.maps.Event.addListener(marker, "click", () => {
    infoWindow.open(map, marker);
  });
}
