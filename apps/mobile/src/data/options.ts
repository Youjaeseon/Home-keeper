import type { Housing } from '@/types';

// 가입 화면은 공개 GET /regions 목록을 쓰고, 이 값은 서버에 닿지 못할 때의 기본값입니다. (GAP-004)
export const REGIONS = ['경기 용인'];

export const HOUSINGS: Housing[] = ['월세', '전세', '반전세', '자가', '기타'];

export const LOCATIONS = ['안방', '화장실', '주방', '거실', '베란다', '천장', '기타'];

/** 하자 표면 재질 (백엔드 analyze 필수 입력 material) */
export const MATERIALS = ['벽지', '타일', '실리콘', '도장면(페인트)', '콘크리트', '석고보드', '창틀', '바닥재', '기타'];

/** 손상이 생긴 자리 */
export const POSITIONS = ['모서리', '벽면', '천장', '바닥', '창틀', '기타'];

const METRO = ['서울', '인천', '부산', '대구', '대전', '광주'];
/** 화면 표시용 지역 이름: '서울' → '서울시' */
export const regionLabel = (region: string) => (METRO.includes(region) ? `${region}시` : region);
