import type { Vendor } from '@/types';

/**
 * 업체 목록용 가상 업체 (팀원 로컬 앱의 data/vendors.ts를 옮김). 실제 업체가 아니며 서버에 저장하지 않습니다.
 * 견적서·제안서·대화 예시 데이터는 실제 주고받기 시험을 위해 지웠습니다(Hyeok 결정). 가상 업체와는 채팅하지 않습니다.
 */

const vendor = (key: string, label: string, name: string, description: string, phone: string, specialties: string[], rating: number, reviewCount: number): Vendor => ({
  id: `demo-vendor-${key}`,
  label,
  name,
  description,
  phone,
  specialties,
  specialtyIds: [],
  rating,
  reviewCount,
  chatAvailable: false,
  isSample: true,
});

export const DEMO_VENDORS: Vendor[] = [
  vendor('a', 'A', '(가상) 클린홈 곰팡이케어', '욕실·주방 곰팡이 제거, 실리콘 재시공', '02-0000-0001', ['곰팡이 제거'], 4.8, 32),
  vendor('b', 'B', '(가상) 튼튼 균열보수', '벽면 균열 보수, 퍼티·도배 마감', '02-0000-0002', ['균열 보수', '벽지·도장 보수'], 4.6, 21),
  vendor('c', 'C', '(가상) 바로 누수탐지', '누수 위치 탐지, 배관·방수 보수', '02-0000-0003', ['원인 점검'], 4.5, 17),
  vendor('d', 'D', '(가상) 우리동네 집수리', '소규모 생활 하자 종합 보수', '02-0000-0004', ['곰팡이 제거', '균열 보수', '벽지·도장 보수', '원인 점검'], 4.3, 48),
];
