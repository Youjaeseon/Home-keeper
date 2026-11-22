import type { Estimate, Message, Proposal, Vendor } from '@/types';

/**
 * 시연용 가상 데이터 (팀원 로컬 앱의 data/vendors.ts·samples.ts를 옮김).
 * 실제 사용자·업체·가격이 아니며 서버(Supabase·FastAPI)에는 저장하지 않습니다.
 * 모든 id는 'demo-'로 시작하고, 이 항목에 대한 동작(채팅·수락·제안·삭제)은 앱 안에서만 처리합니다.
 */
export const isDemo = (id: string | null | undefined) => !!id && id.startsWith('demo-');
export const demoRoomId = (vendorId: string) => `demo-room-${vendorId}`;

const HOUR = 3600_000;
const ago = (h: number) => Date.now() - h * HOUR;

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
  chatAvailable: true,
  isSample: true,
});

export const DEMO_VENDORS: Vendor[] = [
  vendor('a', 'A', '(가상) 클린홈 곰팡이케어', '욕실·주방 곰팡이 제거, 실리콘 재시공', '02-0000-0001', ['곰팡이 제거'], 4.8, 32),
  vendor('b', 'B', '(가상) 튼튼 균열보수', '벽면 균열 보수, 퍼티·도배 마감', '02-0000-0002', ['균열 보수', '벽지·도장 보수'], 4.6, 21),
  vendor('c', 'C', '(가상) 바로 누수탐지', '누수 위치 탐지, 배관·방수 보수', '02-0000-0003', ['원인 점검'], 4.5, 17),
  vendor('d', 'D', '(가상) 우리동네 집수리', '소규모 생활 하자 종합 보수', '02-0000-0004', ['곰팡이 제거', '균열 보수', '벽지·도장 보수', '원인 점검'], 4.3, 48),
];

const estimate = (
  n: number,
  photoAsset: number,
  e: Pick<Estimate, 'userNickname' | 'region' | 'defect' | 'risk' | 'location' | 'position' | 'memo'>,
  hoursAgo: number,
): Estimate => ({
  id: `demo-e${n}`,
  userId: `demo-user-${n}`,
  analysisId: `demo-a${n}`,
  photoUri: '',
  photoAsset,
  sample: true,
  status: 'open',
  createdAt: ago(hoursAgo),
  ...e,
});

export const DEMO_ESTIMATES: Estimate[] = [
  estimate(1, require('@/assets/images/samples/wall-mold.jpg'), {
    userNickname: '(예시) 자취3년차',
    region: '경기 용인',
    defect: '곰팡이',
    risk: 89,
    location: '안방',
    position: '모서리',
    memo: '서랍장 옆 벽 아래쪽부터 곰팡이가 번지고 벽지가 들떴어요. 평일 저녁 방문 가능합니다.',
  }, 2),
  estimate(2, require('@/assets/images/samples/floor-damage.jpg'), {
    userNickname: '(예시) 수지동세입자',
    region: '경기 용인',
    defect: '균열',
    risk: 42,
    location: '거실',
    position: '바닥',
    memo: '바닥재가 찍혀서 패였어요. 부분 보수가 되는지 궁금합니다.',
  }, 9),
  estimate(3, require('@/assets/images/samples/wall-peel.jpg'), {
    userNickname: '(예시) 1층살이',
    region: '경기 용인',
    defect: '벗겨짐',
    risk: 81,
    location: '거실',
    position: '벽면',
    memo: '벽이 젖으면서 페인트가 부풀어 떨어져요. 원인부터 확인하고 싶어요.',
  }, 26),
];

const proposal = (n: number, estimateN: number, vendorKey: string, priceMan: number, memo: string): Proposal => {
  const v = DEMO_VENDORS.find((x) => x.id === `demo-vendor-${vendorKey}`)!;
  return {
    id: `demo-p${n}`,
    estimateId: `demo-e${estimateN}`,
    vendorId: v.id,
    vendorName: v.name,
    vendorIntro: v.description,
    vendorRegion: '경기 용인',
    price: priceMan * 10000,
    priceMax: priceMan * 10000,
    memo,
    createdAt: ago(estimateN),
  };
};

export const DEMO_PROPOSALS: Proposal[] = [
  proposal(1, 1, 'a', 7, '벽면 곰팡이 제거와 방지 코팅까지 포함한 금액입니다. 토요일 오전 방문 가능해요.'),
  proposal(2, 1, 'd', 5, '제거 작업만 진행합니다. 환기 상태 점검은 무료로 해 드려요.'),
  proposal(3, 1, 'c', 9, '벽 속 누수 여부 점검을 포함합니다. 누수가 원인이면 재발을 막을 수 있어요.'),
  proposal(4, 2, 'd', 5, '메움제로 채우고 색을 맞추는 부분 보수 기준입니다. 30분 정도 걸려요.'),
  proposal(5, 2, 'b', 8, '패인 판 한 장을 교체하는 금액입니다. 같은 무늬 자재가 있는지 먼저 확인할게요.'),
  proposal(6, 3, 'c', 10, '탐지 장비로 누수 위치를 먼저 찾습니다. 보수 비용은 원인을 확인한 뒤 따로 안내해 드려요.'),
  proposal(7, 3, 'd', 7, '들뜬 페인트 제거와 방습 처리 기준 금액입니다.'),
];

const msg = (n: number, vendorKey: string, from: Message['from'], text: string, hoursAgo: number): Message => {
  const vendorId = `demo-vendor-${vendorKey}`;
  return { id: `demo-m${n}`, roomId: demoRoomId(vendorId), vendorId, from, text, at: ago(hoursAgo) };
};

/** 채팅 목록에 보이는 예시 대화 */
export const DEMO_MESSAGES: Message[] = [
  msg(1, 'a', 'me', '안녕하세요, 안방 모서리에 곰팡이가 번져서 견적 문의드려요.', 3),
  msg(2, 'a', 'vendor', '(가상) 클린홈 곰팡이케어입니다. 사진 확인했어요. 제거와 방지 코팅까지 7만원 정도 예상합니다.', 2.9),
  msg(3, 'a', 'me', '토요일 오전에 방문 가능하실까요?', 2.5),
  msg(4, 'a', 'vendor', '네, 토요일 오전 10시에 방문드릴게요.\n※ 가상 업체 예시 대화입니다.', 2.4),
  msg(5, 'b', 'me', '거실 바닥이 패였는데 부분 보수도 되나요?', 10),
  msg(6, 'b', 'vendor', '(가상) 튼튼 균열보수입니다. 같은 무늬 자재가 있으면 부분 교체가 가능해요.', 9.5),
];

export const demoAutoReply = (vendorName: string) =>
  `${vendorName}입니다. 문의 감사합니다. 사진을 확인한 뒤 예상 견적과 방문 가능 일정을 안내해 드릴게요.\n※ 가상 업체 자동 응답입니다.`;

/**
 * 실제 견적 요청서에도 시연용 가상 업체 제안서를 붙여 줍니다(앱 안에서만, 서버 저장 없음).
 * 실제 업체 계정이 없는 지역에서도 제안서 비교·수락·채팅 흐름을 보여 주기 위한 것입니다.
 */
export function demoProposalsFor(estimateId: string, defect: string, createdAt: number): Proposal[] {
  const picks: [string, number, string][] =
    defect === '곰팡이'
      ? [['a', 7, '곰팡이 제거와 방지 코팅까지 포함한 금액입니다. 주말 방문 가능해요.'], ['d', 5, '제거 작업만 진행합니다. 환기 상태 점검은 무료로 해 드려요.']]
      : defect === '균열'
        ? [['b', 8, '균열 부위를 메우고 도장까지 마감하는 금액입니다.'], ['d', 6, '부분 보수 기준 금액입니다. 30분 정도 걸려요.']]
        : [['b', 7, '들뜬 마감재를 걷어 내고 다시 도장하는 금액입니다.'], ['c', 9, '습기 원인부터 점검하고 보수 범위를 안내해 드려요.']];
  return picks.map(([key, man, memo], i) => {
    const v = DEMO_VENDORS.find((x) => x.id === `demo-vendor-${key}`)!;
    return {
      id: `demo-auto-${estimateId}-${key}`,
      estimateId,
      vendorId: v.id,
      vendorName: v.name,
      vendorIntro: v.description,
      vendorRegion: '경기 용인',
      price: man * 10000,
      priceMax: man * 10000,
      memo,
      createdAt: createdAt + (i + 1) * 60_000,
    };
  });
}
