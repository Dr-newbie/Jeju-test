import { useEffect, useRef } from "react";

declare global {
  interface Window {
    naver: any;
  }
}

type Place = {
  id: string;
  name: string;
  lat: number;
  lng: number;
  type: string;
};

type RouteStop = {
  order: number;
  place: Place;
  arrival_min_from_day_start: number;
  note?: string;
};

type DayRoute = {
  day: number;
  stops: RouteStop[];
  total_distance_km: number;
  total_duration_min: number;
};

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

  const colors = [
    "#1976d2",
    "#d32f2f",
    "#388e3c",
    "#f57c00",
    "#7b1fa2",
    "#00796b",
  ];

  routes.forEach((route, idx) => {
    const color = colors[idx % colors.length];

    const path = route.stops.map((stop) => {
      return new window.naver.maps.LatLng(stop.place.lat, stop.place.lng);
    });

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