/**
 * 백엔드 계약(snake_case, 코드값) ↔ 팀원 UI 타입(한국어 라벨) 변환 계층.
 * 화면은 이 파일과 store만 거쳐 백엔드 값을 받습니다.
 */
import type { HousingType, Profile, Region } from '@/lib/api';
import type { Housing, Role, User } from '@/types';

const HOUSING_TO_API: Record<Housing, HousingType> = {
  월세: 'monthly_rent',
  전세: 'jeonse',
  반전세: 'semi_jeonse',
  자가: 'owned',
  기타: 'other',
};

const HOUSING_FROM_API: Record<HousingType, Housing> = {
  monthly_rent: '월세',
  jeonse: '전세',
  semi_jeonse: '반전세',
  owned: '자가',
  other: '기타',
};

export const toApiHousing = (h: Housing): HousingType => HOUSING_TO_API[h];
export const fromApiHousing = (h: HousingType): Housing => HOUSING_FROM_API[h] ?? '기타';

export const fromApiRole = (role: Profile['role']): Role => (role === 'provider' ? '업체' : '유저');

/** 화면 표시용 지역 이름 */
export const regionName = (r: Region) => r.display_name;

/**
 * 가입 화면의 지역 라벨('경기 용인')과 서버 지역 표시명('경기도 용인시')을 비교하기 위한 정규화.
 * 행정구역 접미사(도·시·특별시·광역시)와 공백만 제거하며, 일치하지 않으면 매칭하지 않습니다.
 */
function normalizeRegion(label: string) {
  return label
    .trim()
    .split(/\s+/)
    .map((t) => t.replace(/(특별자치도|특별자치시|특별시|광역시|도|시)$/, ''))
    .join('');
}

// TODO(integration-gap): GAP-004 가입 화면은 로그인 전이라 GET /regions(인증 필요)를 부를 수 없어 팀원 하드코딩 지역 목록을 씁니다.
export function matchRegion(label: string, regions: Region[]): Region | null {
  const key = normalizeRegion(label);
  return regions.find((r) => normalizeRegion(r.display_name) === key) ?? null;
}

export function toUser(profile: Profile, email: string, regions: Region[]): User {
  const region = regions.find((r) => r.region_id === profile.region_id);
  return {
    nickname: profile.nickname,
    role: fromApiRole(profile.role),
    loginId: email,
    region: region ? regionName(region) : '',
    regionId: profile.region_id,
    housing: fromApiHousing(profile.housing_type),
    providerId: profile.provider_id,
    address: profile.address,
  };
}
