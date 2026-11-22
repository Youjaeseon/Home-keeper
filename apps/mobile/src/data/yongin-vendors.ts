import type { Vendor } from '@/types';

/**
 * 경기도 용인시 실제 업체 데이터셋 (공개 페이지에서 확인한 정보만, 앱 안에만 저장).
 * - 업체명·대표 전화·주소·하는 일은 출처 페이지에 적힌 그대로이며, 평점은 확인할 수 없어 넣지 않습니다.
 * - 앱 계정이 없어 채팅·견적 요청서는 안 되고 전화 문의만 안내합니다.
 * - 개인 휴대전화(010)는 넣지 않고 업체 대표번호만 씁니다.
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

/** 카카오 로컬 API(2026-11-22)로 가져와 Hyeok이 확인한 16곳. 010 번호 업체는 제외. */
export const YONGIN_VENDORS: RealVendorEntry[] = [
  {
    id: 'yongin-kakao-1608739869',
    name: "마스터 클린",
    phone: "0507-1368-4382",
    address: "경기 용인시 기흥구 강남서로 105",
    description: "카카오맵 분류: 청소대행",
    specialties: ["곰팡이 제거"],
    sourceUrl: "http://place.map.kakao.com/1608739869",
    checkedAt: '2026-11-22',
  },
  {
    id: 'yongin-kakao-1653729399',
    name: "대륙누수방수공사",
    phone: "070-8891-2383",
    address: "경기 용인시 기흥구 새천년로16번길 3-16",
    description: "카카오맵 분류: 배관,누수시공",
    specialties: ["원인 점검", "균열 보수"],
    sourceUrl: "http://place.map.kakao.com/1653729399",
    checkedAt: '2026-11-22',
  },
  {
    id: 'yongin-kakao-2007346864',
    name: "한국누수방수공사 동천동점",
    phone: "070-4906-9568",
    address: "경기 용인시 수지구 손곡로 100",
    description: "카카오맵 분류: 배관,누수시공",
    specialties: ["원인 점검", "균열 보수"],
    sourceUrl: "http://place.map.kakao.com/2007346864",
    checkedAt: '2026-11-22',
  },
  {
    id: 'yongin-kakao-2083839146',
    name: "한국누수방수공사 상하동점",
    phone: "070-4906-9555",
    address: "경기 용인시 기흥구 중부대로788번길 3",
    description: "카카오맵 분류: 배관,누수시공",
    specialties: ["원인 점검", "균열 보수"],
    sourceUrl: "http://place.map.kakao.com/2083839146",
    checkedAt: '2026-11-22',
  },
  {
    id: 'yongin-kakao-1567073086',
    name: "JP누수",
    phone: "1599-3983",
    address: "경기 용인시 기흥구 죽현로 8-22",
    description: "카카오맵 분류: 배관,누수시공",
    specialties: ["원인 점검"],
    sourceUrl: "http://place.map.kakao.com/1567073086",
    checkedAt: '2026-11-22',
  },
  {
    id: 'yongin-kakao-1168873602',
    name: "누수명가설비",
    phone: "070-4940-8439",
    address: "경기 용인시 기흥구 금화로11번길 42",
    description: "카카오맵 분류: 배관,누수시공",
    specialties: ["원인 점검"],
    sourceUrl: "http://place.map.kakao.com/1168873602",
    checkedAt: '2026-11-22',
  },
  {
    id: 'yongin-kakao-1131385735',
    name: "신용누수탐지",
    phone: "031-332-1865",
    address: "경기 용인시 처인구 포곡읍 포곡로 289-1",
    description: "카카오맵 분류: 배관,누수시공",
    specialties: ["원인 점검"],
    sourceUrl: "http://place.map.kakao.com/1131385735",
    checkedAt: '2026-11-22',
  },
  {
    id: 'yongin-kakao-154537229',
    name: "용인119",
    phone: "070-8811-8293",
    address: "경기 용인시 기흥구 마북로 159",
    description: "카카오맵 분류: 배관,누수시공",
    specialties: ["원인 점검"],
    sourceUrl: "http://place.map.kakao.com/154537229",
    checkedAt: '2026-11-22',
  },
  {
    id: 'yongin-kakao-950727111',
    name: "원스톱누수인테리어",
    phone: "1668-5445",
    address: "경기 용인시 기흥구 흥덕중앙로 55",
    description: "카카오맵 분류: 배관,누수시공",
    specialties: ["원인 점검"],
    sourceUrl: "http://place.map.kakao.com/950727111",
    checkedAt: '2026-11-22',
  },
  {
    id: 'yongin-kakao-1485042679',
    name: "꼼꼼도배",
    phone: "031-285-9992",
    address: "경기 용인시 기흥구 사은로 58",
    description: "카카오맵 분류: 인테리어",
    specialties: ["벽지·도장 보수"],
    sourceUrl: "http://place.map.kakao.com/1485042679",
    checkedAt: '2026-11-22',
  },
  {
    id: 'yongin-kakao-26542428',
    name: "대성벽지",
    phone: "031-274-3535",
    address: "경기 용인시 기흥구 동백5로 22",
    description: "카카오맵 분류: 인테리어",
    specialties: ["벽지·도장 보수"],
    sourceUrl: "http://place.map.kakao.com/26542428",
    checkedAt: '2026-11-22',
  },
  {
    id: 'yongin-kakao-761680036',
    name: "도배365 수지1직영점",
    phone: "1577-4167",
    address: "경기 용인시 수지구 동천로99번길 43",
    description: "카카오맵 분류: 시공업체",
    specialties: ["벽지·도장 보수"],
    sourceUrl: "http://place.map.kakao.com/761680036",
    checkedAt: '2026-11-22',
  },
  {
    id: 'yongin-kakao-2066621035',
    name: "우리도배장판",
    phone: "031-334-4737",
    address: "경기 용인시 처인구 포곡읍 전대로 78",
    description: "카카오맵 분류: 시공업체",
    specialties: ["벽지·도장 보수"],
    sourceUrl: "http://place.map.kakao.com/2066621035",
    checkedAt: '2026-11-22',
  },
  {
    id: 'yongin-kakao-842498699',
    name: "미도도배장판",
    phone: "031-264-6804",
    address: "경기 용인시 수지구 수풍로117번길 2-4",
    description: "카카오맵 분류: 인테리어장식판매",
    specialties: ["벽지·도장 보수"],
    sourceUrl: "http://place.map.kakao.com/842498699",
    checkedAt: '2026-11-22',
  },
  {
    id: 'yongin-kakao-1515064183',
    name: "모모인테리어",
    phone: "031-285-3933",
    address: "경기 용인시 기흥구 평촌1로8번길 5-9",
    description: "카카오맵 분류: 인테리어",
    specialties: ["벽지·도장 보수"],
    sourceUrl: "http://place.map.kakao.com/1515064183",
    checkedAt: '2026-11-22',
  },
  {
    id: 'yongin-kakao-799290615',
    name: "공간이야기",
    phone: "031-889-8504",
    address: "경기 용인시 수지구 현암로 164",
    description: "카카오맵 분류: 인테리어",
    specialties: ["벽지·도장 보수"],
    sourceUrl: "http://place.map.kakao.com/799290615",
    checkedAt: '2026-11-22',
  },
];

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
