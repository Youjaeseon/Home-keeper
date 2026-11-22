import type { Vendor } from '@/types';

/**
 * 경기도 용인시 실제 업체 데이터셋 (공개 페이지에서 확인한 정보만, 앱 안에만 저장).
 * - 업체명·대표 전화·주소·하는 일은 출처 페이지에 적힌 그대로이며, 평점은 확인할 수 없어 넣지 않습니다.
 * - 앱 계정이 없어 채팅·견적 요청서는 안 되고 전화 문의만 안내합니다.
 * - 개인 휴대전화(010)는 넣지 않고 업체 대표번호만 씁니다.
 * Hyeok 확인 후 채웁니다.
 */
export type RealVendorEntry = {
  id: string;
  name: string;
  phone: string;
  address: string | null;
  description: string;
  /** 하는 일(작업 종류 이름: 곰팡이 제거, 균열 보수, 벽지·도장 보수, 원인 점검) */
  specialties: string[];
  sourceUrl: string;
  /** 출처 확인 날짜 YYYY-MM-DD */
  checkedAt: string;
};

export const YONGIN_VENDORS: RealVendorEntry[] = [];

/**
 * 이 지역에 실제 업체 데이터셋을 쓰는지 (지금은 경기도 용인시만).
 * 데이터가 비어 있으면 기존처럼 테스트·가상 업체를 그대로 보여 줍니다.
 */
export const usesRealVendors = (regionName: string | null | undefined) =>
  YONGIN_VENDORS.length > 0 && !!regionName && regionName.includes('용인');

/** workTypeIds: 작업 종류 이름 → 서버 work_type_id (분석 결과의 '추천' 표시에 씀) */
export function realVendorsFor(workTypeIds: Record<string, string> = {}): Vendor[] {
  const LABELS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  return YONGIN_VENDORS.map((v, i) => ({
    id: v.id,
    label: LABELS[i] ?? String(i + 1),
    name: v.name,
    description: [v.description, v.address].filter(Boolean).join(' · '),
    phone: v.phone,
    specialties: v.specialties,
    specialtyIds: v.specialties.map((s) => workTypeIds[s] ?? s),
    rating: 0,
    reviewCount: 0,
    chatAvailable: false,
    isSample: false,
    realListing: { sourceUrl: v.sourceUrl, checkedAt: v.checkedAt },
  }));
}
