from dataclasses import dataclass
from typing import Literal

RegionId = Literal["jeju", "gangwon"]

DEFAULT_REGION: RegionId = "jeju"


@dataclass(frozen=True)
class RegionConfig:
    display_name: str
    search_keyword: str
    dinner_keywords: list[str]
    region_seeds: list[tuple[float, float]]


REGION_CONFIGS: dict[RegionId, RegionConfig] = {
    "jeju": RegionConfig(
        display_name="제주",
        search_keyword="제주",
        dinner_keywords=["회", "횟집", "물회", "돼지", "흑돼지", "제주삼겹"],
        region_seeds=[
            (33.4996, 126.5312),  # 제주시내
            (33.4633, 126.3306),  # 애월/한림
            (33.3016, 126.1650),  # 한경/고산 (서쪽 끝)
            (33.2496, 126.4132),  # 중문/서귀포
            (33.2809, 126.6389),  # 남원/표선
            (33.4581, 126.9425),  # 성산/우도
            (33.5427, 126.6668),  # 조천/함덕
        ],
    ),
    "gangwon": RegionConfig(
        display_name="강원도",
        search_keyword="강원",
        dinner_keywords=["막국수", "닭갈비", "곤드레", "황태", "순두부"],
        region_seeds=[
            (37.8813, 127.7298),  # 춘천
            (37.7519, 128.8761),  # 강릉
            (38.2070, 128.5918),  # 속초
            (37.3706, 128.3900),  # 평창
            (37.3806, 128.6608),  # 정선
            (37.3422, 127.9202),  # 원주
            (37.5247, 129.1143),  # 동해/삼척
            (37.6971, 127.8887),  # 홍천/인제
        ],
    ),
}


def get_region_config(region_id: RegionId) -> RegionConfig:
    return REGION_CONFIGS[region_id]
