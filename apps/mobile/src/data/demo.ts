import type { Message, Vendor } from '@/types';

/**
 * 시연용 가상 데이터 (팀원 로컬 앱의 data/vendors.ts를 옮김). 예시 견적서·제안서는 실제 주고받기 시험을 위해 지웠습니다(Hyeok 결정).
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
