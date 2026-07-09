export const DAY_COLORS = [
  "#ff8a3d",
  "#1b8f9e",
  "#e6534b",
  "#4c9a5b",
  "#8a5cf6",
  "#c9822f",
];

export const PLACE_TYPE_META: Record<string, { label: string; icon: string }> = {
  etc: { label: "미분류", icon: "📍" },
  tourist_spot: { label: "관광지", icon: "🏖️" },
  restaurant: { label: "식당", icon: "🍽️" },
  cafe: { label: "카페", icon: "☕" },
  shopping: { label: "쇼핑", icon: "🛍️" },
  accommodation: { label: "숙소", icon: "🏨" },
  airport: { label: "공항", icon: "✈️" },
};

export function placeIcon(type: string): string {
  return PLACE_TYPE_META[type]?.icon ?? "📍";
}
