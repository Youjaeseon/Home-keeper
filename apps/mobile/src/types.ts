import type { SupportCategory } from '@/lib/api';

export type Housing = '월세' | '전세' | '반전세' | '자가' | '기타';

/** 회원 유형: 일반 유저 / 견적을 받는 업체 */
export type Role = '유저' | '업체';

export type User = {
  /** 유저는 별명, 업체는 업체명 */
  nickname: string;
  role: Role;
  /** 업체 소개 (업체 회원만) */
  intro?: string;
  /** 로그인 ID. Supabase Auth 이메일입니다. */
  loginId: string;
  /** 화면 표시용 지역 이름 (GET /regions의 display_name) */
  region: string;
  /** 백엔드 지역 UUID */
  regionId: string;
  housing: Housing;
  /** 업체 계정이면 연결된 업체 UUID */
  providerId: string | null;
  address: string | null;
  avatarUri?: string;
};

/** 회원가입 입력값 */
export type Account = {
  role: Role;
  nickname: string;
  loginId: string;
  password: string;
  region: string;
  housing: Housing;
  intro?: string;
  /** 업체 가입 시 연락처 */
  phone?: string;
};

export type Photo = { id: string; uri: string; createdAt: number };

/**
 * 백엔드 진단 유형(`diagnosis.py`) 3종 + 판단 보류입니다. (GAP-007)
 * 샘플·LLM 진단이 다른 이름(예: '표면 이상')을 주면 서버 값을 그대로 보여 줍니다.
 */
export type DefectType = '곰팡이' | '균열' | '벗겨짐' | '판단 보류' | (string & {});

export type AnalysisInput = {
  photo: Photo;
  location: string;
  /** 손상 위치 (벽면, 천장 등) */
  position: string;
  /** 표면 재질 (백엔드 필수 입력) */
  material: string;
  occurredAt: string; // YYYY.MM.DD
  memo: string;
  housing: Housing;
  /** 분석 지역 UUID (프로필 지역) */
  regionId: string | null;
  /** 외부 AI(SAM·비전 LLM) 사진 전송 동의 */
  consent: boolean;
};

/** 손상 위치. 사진 크기 대비 0~1 비율 (원의 중심 x, y와 반지름 r) */
export type DefectRegion = { x: number; y: number; r: number };

export type Guide = {
  title: string;
  body: string;
  /** 세입자용 집주인 통지 문자 예시 */
  message?: string;
  /** 대응 순서 */
  steps?: { title: string; desc: string }[];
};

export type AnalysisResult = {
  id: string;
  photoId: string;
  photoUri: string;
  location: string;
  position: string;
  occurredAt: string;
  housing: Housing;
  defect: DefectType;
  /** 위험도 0~100 */
  risk: number;
  region: DefectRegion | null;
  cause: string;
  solutions: string[];
  prevention: string[];
  guide: Guide;
  needsRetake: boolean;
  createdAt: number;
  /** 추천 작업 종류 (업체 추천·견적 요청서에 사용) */
  workTypeId?: string | null;
  /** 결과가 추정임을 알리는 서버 안내 문구 */
  estimationNotice?: string;
  /** 서버 진단 출처: llm 또는 sample */
  source?: 'llm' | 'sample';
  /** 권장 대응: 직접 관리 / 점검 / 업체 상담 (GAP-025) */
  recommendedAction?: 'self_care' | 'inspection' | 'provider_consult';
};

export type Vendor = {
  id: string;
  label: string;
  name: string;
  description: string;
  phone: string;
  /** 특화 분야(작업 종류) 이름 */
  specialties: string[];
  specialtyIds: string[];
  rating: number;
  reviewCount: number;
  /** 앱 내 채팅 가능 여부 (샘플 업체는 false) */
  chatAvailable: boolean;
  /** 실제 후보가 없어 서버가 돌려준 시연용 샘플인지 */
  isSample: boolean;
  /** 공개 페이지에서 확인한 실제 업체(앱 계정 없음, 전화 문의만) */
  realListing?: { sourceUrl: string; checkedAt: string };
};

export type Message = {
  id: string;
  roomId: string;
  vendorId: string;
  from: 'me' | 'vendor';
  text: string;
  at: number;
};

export type NewsItem = {
  id: string;
  title: string;
  org: string;
  summary: string;
  regions: string[]; // '전국' 포함
  housings: Housing[];
  categories: SupportCategory[];
  status: '접수중' | '마감' | '상시' | '기한 미확인';
};

/** 유저가 주변 업체에 보내는 견적서 */
export type Estimate = {
  id: string;
  userId: string;
  userNickname: string;
  region: string;
  analysisId: string;
  photoUri: string;
  /** 앱에 들어 있는 예시 사진 (require 값). 있으면 photoUri 대신 씁니다. */
  photoAsset?: number;
  /** 예시 데이터 여부 */
  sample?: boolean;
  defect: string;
  risk: number;
  location: string;
  position: string;
  memo: string;
  createdAt: number;
  status?: 'open' | 'accepted' | 'cancelled' | 'completed';
  acceptedProposalId?: string | null;
};

/** 업체가 견적서를 보낸 유저에게 보내는 제안서 */
export type Proposal = {
  id: string;
  estimateId: string;
  vendorId: string;
  vendorName: string;
  vendorIntro: string;
  vendorRegion: string;
  /** 최소 금액(원) */
  price: number;
  /** 최대 금액(원). 최소와 같으면 단일 가격입니다. */
  priceMax?: number;
  memo: string;
  createdAt: number;
};

/** 채팅 목록 한 줄 (GET /chat/rooms) */
export type ChatThread = {
  roomId: string;
  /** 업체 UUID */
  vendorId: string;
  name: string;
  last: string | null;
  unread: number;
};
