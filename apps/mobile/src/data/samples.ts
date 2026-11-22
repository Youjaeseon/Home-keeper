import type { Estimate, Proposal } from '@/types';

/**
 * 견적서·제안서 예시 데이터 (시뮬레이션용). 실제 사용자·업체·가격이 아닙니다.
 */
const HOUR = 3600_000;
const ago = (h: number) => Date.now() - h * HOUR;

const estimate = (
  n: number,
  photoAsset: number,
  e: Pick<Estimate, 'userNickname' | 'region' | 'defect' | 'risk' | 'location' | 'position' | 'memo'>,
  hoursAgo: number,
): Estimate => ({
  id: `sample-e${n}`,
  userId: `sample-user-${n}`,
  analysisId: `sample-a${n}`,
  photoUri: '',
  photoAsset,
  sample: true,
  createdAt: ago(hoursAgo),
  ...e,
});

export const SAMPLE_ESTIMATES: Estimate[] = [
  estimate(1, require('@/assets/images/samples/wall-mold.jpg'), {
    userNickname: '(예시) 자취3년차',
    region: '서울',
    defect: '곰팡이',
    risk: 89,
    location: '방',
    position: '모서리',
    memo: '서랍장 옆 벽 아래쪽부터 곰팡이가 번지고 벽지가 들떴어요. 평일 저녁 방문 가능합니다.',
  }, 2),
  estimate(2, require('@/assets/images/samples/floor-damage.jpg'), {
    userNickname: '(예시) 망원동세입자',
    region: '서울',
    defect: '균열',
    risk: 42,
    location: '거실',
    position: '바닥',
    memo: '바닥재가 찍혀서 패였어요. 부분 보수가 되는지 궁금합니다.',
  }, 9),
  estimate(3, require('@/assets/images/samples/wall-peel.jpg'), {
    userNickname: '(예시) 1층살이',
    region: '부산',
    defect: '누수',
    risk: 81,
    location: '거실',
    position: '벽면',
    memo: '벽이 젖으면서 페인트가 부풀어 떨어져요. 원인부터 확인하고 싶어요.',
  }, 26),
];

const proposal = (n: number, estimateN: number, p: Pick<Proposal, 'vendorName' | 'vendorIntro' | 'vendorRegion' | 'price' | 'memo'>): Proposal => ({
  id: `sample-p${n}`,
  estimateId: `sample-e${estimateN}`,
  vendorId: `sample-vendor-${n}`,
  createdAt: ago(estimateN),
  ...p,
});

export const SAMPLE_PROPOSALS: Proposal[] = [
  proposal(1, 1, {
    vendorName: '(가상) 클린홈 곰팡이케어',
    vendorIntro: '욕실·주방 곰팡이 제거, 실리콘 재시공',
    vendorRegion: '서울',
    price: 7,
    memo: '벽면 곰팡이 제거와 방지 코팅까지 포함한 금액입니다. 토요일 오전 방문 가능해요.',
  }),
  proposal(2, 1, {
    vendorName: '(가상) 우리동네 집수리',
    vendorIntro: '소규모 생활 하자 종합 보수',
    vendorRegion: '서울',
    price: 5,
    memo: '제거 작업만 진행합니다. 환기 상태 점검은 무료로 해 드려요.',
  }),
  proposal(3, 1, {
    vendorName: '(가상) 바로 누수탐지',
    vendorIntro: '누수 위치 탐지, 배관·방수 보수',
    vendorRegion: '서울',
    price: 9,
    memo: '벽 속 누수 여부 점검을 포함합니다. 누수가 원인이면 재발을 막을 수 있어요.',
  }),
  proposal(4, 2, {
    vendorName: '(가상) 우리동네 집수리',
    vendorIntro: '소규모 생활 하자 종합 보수',
    vendorRegion: '서울',
    price: 5,
    memo: '메움제로 채우고 색을 맞추는 부분 보수 기준입니다. 30분 정도 걸려요.',
  }),
  proposal(5, 2, {
    vendorName: '(가상) 튼튼 균열보수',
    vendorIntro: '벽면 균열 보수, 퍼티·도배 마감',
    vendorRegion: '서울',
    price: 8,
    memo: '패인 판 한 장을 교체하는 금액입니다. 같은 무늬 자재가 있는지 먼저 확인할게요.',
  }),
  proposal(6, 3, {
    vendorName: '(가상) 바로 누수탐지',
    vendorIntro: '누수 위치 탐지, 배관·방수 보수',
    vendorRegion: '부산',
    price: 10,
    memo: '탐지 장비로 누수 위치를 먼저 찾습니다. 보수 비용은 원인을 확인한 뒤 따로 안내해 드려요.',
  }),
  proposal(7, 3, {
    vendorName: '(가상) 우리동네 집수리',
    vendorIntro: '소규모 생활 하자 종합 보수',
    vendorRegion: '부산',
    price: 7,
    memo: '들뜬 페인트 제거와 방습 처리 기준 금액입니다.',
  }),
];
