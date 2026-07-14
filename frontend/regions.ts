import type { Place } from "./types";

export type RegionId = "jeju" | "gangwon";

export type RegionConfig = {
  id: RegionId;
  label: string;
  titleCopy: string;
  subtitleCopy: string;
  sharedTitleCopy: string;
  sharedSubtitleCopy: string;
  anchorLabel: string;
  anchorIcon: string;
  defaultAnchorId: string;
  defaultAccommodationId: string;
  samplePlaces: Place[];
};

export const DEFAULT_REGION: RegionId = "jeju";

export const REGION_CONFIGS: Record<RegionId, RegionConfig> = {
  jeju: {
    id: "jeju",
    label: "제주",
    titleCopy: "🍊 제주 여행 루트 플래너",
    subtitleCopy: "장소를 담고, 며칠 여행할지 정하면 동선을 알아서 짜드려요",
    sharedTitleCopy: "🍊 공유된 제주 여행 루트",
    sharedSubtitleCopy: "다른 사람이 만든 제주 여행 코스예요",
    anchorLabel: "공항",
    anchorIcon: "✈️",
    defaultAnchorId: "airport_1",
    defaultAccommodationId: "hotel_1",
    samplePlaces: [
      {
        id: "airport_1",
        name: "제주국제공항",
        lat: 33.5066,
        lng: 126.4931,
        type: "airport",
        duration_min: 0,
      },
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
    ],
  },
  gangwon: {
    id: "gangwon",
    label: "강원도",
    titleCopy: "🏔️ 강원 여행 루트 플래너",
    subtitleCopy: "장소를 담고, 며칠 여행할지 정하면 동선을 알아서 짜드려요",
    sharedTitleCopy: "🏔️ 공유된 강원 여행 루트",
    sharedSubtitleCopy: "다른 사람이 만든 강원 여행 코스예요",
    anchorLabel: "출발/도착 기준지",
    anchorIcon: "🚙",
    defaultAnchorId: "airport_1",
    defaultAccommodationId: "hotel_1",
    samplePlaces: [
      {
        id: "airport_1",
        name: "강원 진입 기준점 (홍천IC)",
        lat: 37.6892,
        lng: 127.8973,
        type: "airport",
        duration_min: 0,
      },
      {
        id: "hotel_1",
        name: "강릉 숙소",
        lat: 37.7519,
        lng: 128.8761,
        type: "accommodation",
        duration_min: 0,
      },
      {
        id: "p1",
        name: "남이섬",
        lat: 37.7907,
        lng: 127.5279,
        type: "tourist_spot",
        priority: 5,
        must_visit: true,
        preferred_day: 1,
        duration_min: 120,
      },
      {
        id: "p2",
        name: "정동진",
        lat: 37.6907,
        lng: 129.0347,
        type: "tourist_spot",
        priority: 5,
        duration_min: 90,
      },
      {
        id: "p3",
        name: "설악산 소공원",
        lat: 38.167,
        lng: 128.4959,
        type: "tourist_spot",
        priority: 4,
        duration_min: 150,
      },
      {
        id: "p4",
        name: "카페 후보",
        lat: 37.7746,
        lng: 128.943,
        type: "cafe",
        duration_min: 60,
      },
      {
        id: "r1",
        name: "점심 식당 후보",
        lat: 37.8721,
        lng: 127.7357,
        type: "restaurant",
        meal_slot: "lunch",
        food_category: "닭갈비",
        duration_min: 60,
      },
      {
        id: "r2",
        name: "저녁 식당 후보",
        lat: 37.7626,
        lng: 128.9209,
        type: "restaurant",
        meal_slot: "dinner",
        food_category: "순두부",
        duration_min: 80,
      },
    ],
  },
};
