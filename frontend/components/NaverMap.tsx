import { useEffect, useRef } from "react";
import type { DayRoute, Place } from "../types";
import { DAY_COLORS, placeIcon } from "../constants";

declare global {
  interface Window {
    naver: any;
  }
}

type Props = {
  routes: DayRoute[];
};

export default function NaverMap({ routes }: Props) {
  const mapRef = useRef<HTMLDivElement | null>(null);
  const markersRef = useRef<any[]>([]);
  const polylinesRef = useRef<any[]>([]);

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

      markersRef.current.forEach((m) => m.setMap(null));
      polylinesRef.current.forEach((p) => p.setMap(null));
      markersRef.current = [];
      polylinesRef.current = [];

      const firstStop = routes?.[0]?.stops?.[0]?.place;

      const center = firstStop
        ? new window.naver.maps.LatLng(firstStop.lat, firstStop.lng)
        : new window.naver.maps.LatLng(37.5665, 126.978);

      const map = new window.naver.maps.Map(mapRef.current, {
        center,
        zoom: 11,
      });

      drawRoutes(map, routes, markersRef.current, polylinesRef.current);
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
  }, [routes]);

  return <div ref={mapRef} style={{ width: "100%", height: "100%" }} />;
}

function drawRoutes(
  map: any,
  routes: DayRoute[],
  markers: any[],
  polylines: any[]
) {
  if (!window.naver || !window.naver.maps || !routes?.length) return;

  routes.forEach((route, idx) => {
    const color = DAY_COLORS[idx % DAY_COLORS.length];

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
      addAnchorMarker(map, place, `${route.day}일차 ${label}`, color, markers);
    });

    if (path.length >= 2) {
      const polyline = new window.naver.maps.Polyline({
        map,
        path,
        strokeColor: color,
        strokeOpacity: 0.85,
        strokeWeight: 4,
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
  markers: any[]
) {
  const marker = new window.naver.maps.Marker({
    position: new window.naver.maps.LatLng(place.lat, place.lng),
    map,
    title,
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