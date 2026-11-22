import type { Vendor } from '@/types';

/** 가상 업체 데이터 (시뮬레이션용). 실제 업체·번호가 아닙니다. */
export const VENDORS: Vendor[] = [
  {
    id: 'a',
    label: 'A',
    name: '(가상) 클린홈 곰팡이케어',
    description: '욕실·주방 곰팡이 제거, 실리콘 재시공',
    phone: '02-0000-0001',
    specialties: ['곰팡이', '결로'],
  },
  {
    id: 'b',
    label: 'B',
    name: '(가상) 튼튼 균열보수',
    description: '벽면 균열 보수, 퍼티·도배 마감',
    phone: '02-0000-0002',
    specialties: ['균열'],
  },
  {
    id: 'c',
    label: 'C',
    name: '(가상) 바로 누수탐지',
    description: '누수 위치 탐지, 배관·방수 보수',
    phone: '02-0000-0003',
    specialties: ['누수', '결로'],
  },
  {
    id: 'd',
    label: 'D',
    name: '(가상) 우리동네 집수리',
    description: '소규모 생활 하자 종합 보수',
    phone: '02-0000-0004',
    specialties: ['곰팡이', '균열', '누수', '결로'],
  },
];

export const getVendor = (id: string) => VENDORS.find((v) => v.id === id);
