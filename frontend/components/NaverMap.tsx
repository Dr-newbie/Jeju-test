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
  onHoverDay?: (day: number | null) => void;
};

type MarkerEntry = {
  day: number;
  marker: any;
  infoWindow: any;
  isAnchor: boolean;
  place: Place;
  color: string;
  order?: number;
};

type PolylineEntry = {
  day: number;
  polyline: any;
  color: string;
};

export default function NaverMap({ routes, hoveredDay = null, onHoverDay }: Props) {
  const mapRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<any>(null);
  const markerEntriesRef = useRef<MarkerEntry[]>([]);
  const polylineEntriesRef = useRef<PolylineEntry[]>([]);
  const routesRef = useRef<DayRoute[]>(routes);
  const hoveredDayRef = useRef<number | null>(hoveredDay);
  const onHoverDayRef = useRef<Props["onHoverDay"]>(onHoverDay);

  routesRef.current = routes;
  hoveredDayRef.current = hoveredDay;
  onHoverDayRef.current = onHoverDay;

  // 마커/폴리라인 객체를 새로 만들지 않고 아이콘/색상/zIndex만 갱신한다.
  // 객체를 다시 만들면 그 위에 붙어있던 mouseover/mouseout 리스너가 끊겨서
  // 지도 위에서 커서를 올려 강조하는 상호작용이 깨지기 때문이다.
  const applyHoverStyles = (day: number | null) => {
    markerEntriesRef.current.forEach((entry) => {
      const isDimmed = day != null && day !== entry.day;
      const color = isDimmed ? DIMMED_COLOR : entry.color;

      entry.marker.setIcon(
        entry.isAnchor
          ? anchorIconContent(color, entry.place)
          : stopIconContent(color, entry.order ?? 0)
      );
      entry.marker.setZIndex(isDimmed ? 0 : 100);
    });

    polylineEntriesRef.current.forEach((entry) => {
      const isDimmed = day != null && day !== entry.day;

      entry.polyline.setOptions({
        strokeColor: isDimmed ? DIMMED_COLOR : entry.color,
        strokeOpacity: isDimmed ? 0.6 : 0.85,
        strokeWeight: isDimmed ? 3 : 4,
        zIndex: isDimmed ? 0 : 100,
      });
    });
  };

  const clearOverlays = () => {
    markerEntriesRef.current.forEach((entry) => entry.marker.setMap(null));
    polylineEntriesRef.current.forEach((entry) => entry.polyline.setMap(null));
    markerEntriesRef.current = [];
    polylineEntriesRef.current = [];
  };

  const buildOverlays = () => {
    const map = mapInstanceRef.current;
    if (!map || !window.naver || !window.naver.maps) return;

    clearOverlays();

    drawRoutes(
      map,
      routesRef.current,
      markerEntriesRef.current,
      polylineEntriesRef.current,
      (day) => onHoverDayRef.current?.(day)
    );

    applyHoverStyles(hoveredDayRef.current);
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
      buildOverlays();
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

  // routes가 새로 생기면 그 범위에 맞춰 지도를 재중심/재줌하고 마커/경로를 새로 그린다.
  useEffect(() => {
    fitToRoutes();
    buildOverlays();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routes]);

  // hoveredDay만 바뀔 때는 지도 시점/객체는 그대로 두고 강조 스타일만 갱신한다.
  useEffect(() => {
    applyHoverStyles(hoveredDay);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hoveredDay]);

  return <div ref={mapRef} style={{ width: "100%", height: "100%" }} />;
}

function drawRoutes(
  map: any,
  routes: DayRoute[],
  markerEntries: MarkerEntry[],
  polylineEntries: PolylineEntry[],
  onHover: (day: number | null) => void
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
        zIndex: 100,
        icon: stopIconContent(color, stop.order),
      });

      const infoWindow = new window.naver.maps.InfoWindow({
        content: `
          <div style="padding:8px;min-width:180px;">
            <b>${route.day}일차 ${stop.order}. ${stop.place.name}</b><br/>
            <span>${stop.place.type}</span><br/>
            <span>${stop.note ?? ""}</span>
          </div>
        `,
      });

      // 커서를 올리면 그날 경로만 강조하고 정보창을 띄우고, 벗어나면 원상복구한다.
      window.naver.maps.Event.addListener(marker, "mouseover", () => {
        onHover(route.day);
        infoWindow.open(map, marker);
      });
      window.naver.maps.Event.addListener(marker, "mouseout", () => {
        onHover(null);
        infoWindow.close();
      });

      markerEntries.push({
        day: route.day,
        marker,
        infoWindow,
        isAnchor: false,
        place: stop.place,
        color,
        order: stop.order,
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
        route.day,
        markerEntries,
        onHover
      );
    });

    if (path.length >= 2) {
      const polyline = new window.naver.maps.Polyline({
        map,
        path,
        strokeColor: color,
        strokeOpacity: 0.85,
        strokeWeight: 4,
        zIndex: 100,
      });

      window.naver.maps.Event.addListener(polyline, "mouseover", () =>
        onHover(route.day)
      );
      window.naver.maps.Event.addListener(polyline, "mouseout", () =>
        onHover(null)
      );

      polylineEntries.push({ day: route.day, polyline, color });
    }
  });
}

function addAnchorMarker(
  map: any,
  place: Place,
  title: string,
  color: string,
  day: number,
  markerEntries: MarkerEntry[],
  onHover: (day: number | null) => void
) {
  const marker = new window.naver.maps.Marker({
    position: new window.naver.maps.LatLng(place.lat, place.lng),
    map,
    title,
    zIndex: 100,
    icon: anchorIconContent(color, place),
  });

  const infoWindow = new window.naver.maps.InfoWindow({
    content: `
      <div style="padding:8px;min-width:160px;">
        <b>${title}</b><br/>
        <span>${place.name}</span>
      </div>
    `,
  });

  window.naver.maps.Event.addListener(marker, "mouseover", () => {
    onHover(day);
    infoWindow.open(map, marker);
  });
  window.naver.maps.Event.addListener(marker, "mouseout", () => {
    onHover(null);
    infoWindow.close();
  });

  markerEntries.push({ day, marker, infoWindow, isAnchor: true, place, color });
}

function stopIconContent(color: string, order: number) {
  return {
    content: `
      <div style="
        width:24px;height:24px;border-radius:50%;
        background:${color};border:2px solid #fff;
        display:flex;align-items:center;justify-content:center;
        color:#fff;font-size:12px;font-weight:700;
        box-shadow:0 1px 3px rgba(0,0,0,0.3);
      ">${order}</div>
    `,
    anchor: new window.naver.maps.Point(12, 12),
  };
}

function anchorIconContent(color: string, place: Place) {
  return {
    content: `
      <div style="
        width:30px;height:30px;border-radius:50%;
        background:${color};border:2px solid #fff;
        display:flex;align-items:center;justify-content:center;
        font-size:15px;box-shadow:0 2px 6px rgba(0,0,0,0.35);
      ">${placeIcon(place.type)}</div>
    `,
    anchor: new window.naver.maps.Point(15, 15),
  };
}
