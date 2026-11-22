import type { SupportCategory } from '@/lib/api';
import type { Housing } from '@/types';

export const CATEGORY_LABELS: Record<SupportCategory, string> = {
  monthly_rent_support: '월세',
  deposit_loan: '보증금·대출',
  housing_cost: '주거비',
  repair: '수리·개선',
  brokerage_fee: '중개비',
  supply: '입주·공급',
  other: '기타',
};

// TODO(integration-gap): GAP-004 로그인 전 가입 화면 전용 목록입니다. 로그인 후에는 GET /regions 결과를 씁니다.
export const REGIONS = [
  '서울',
  '인천',
  '경기 수원',
  '경기 용인',
  '경기 성남',
  '부산',
  '대구',
  '대전',
  '광주',
  '기타',
];

export const HOUSINGS: Housing[] = ['월세', '전세', '반전세', '자가', '기타'];

export const LOCATIONS = ['안방', '화장실', '주방', '거실', '베란다', '천장', '기타'];

/** 하자 표면 재질 (백엔드 analyze 필수 입력 material) */
export const MATERIALS = ['벽지', '타일', '실리콘', '도장면(페인트)', '콘크리트', '석고보드', '창틀', '바닥재', '기타'];

/** 손상이 생긴 자리 */
export const POSITIONS = ['모서리', '벽면', '천장', '바닥', '창틀', '기타'];

const METRO = ['서울', '인천', '부산', '대구', '대전', '광주'];
/** 화면 표시용 지역 이름: '서울' → '서울시' */
export const regionLabel = (region: string) => (METRO.includes(region) ? `${region}시` : region);
