export type Place = {
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

export type RouteStop = {
  order: number;
  place: Place;
  arrival_min_from_day_start: number;
  note?: string;
};

export type DayRoute = {
  day: number;
  stops: RouteStop[];
  total_distance_km: number;
  total_duration_min: number;
};
