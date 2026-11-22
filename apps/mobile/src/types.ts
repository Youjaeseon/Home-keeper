export type Housing = '월세' | '전세' | '자가' | '기타';

/** 회원 유형: 일반 유저 / 견적을 받는 업체 */
export type Role = '유저' | '업체';

export type User = {
  /** 유저는 별명, 업체는 업체명 */
  nickname: string;
  role: Role;
  /** 업체 소개 (업체 회원만) */
  intro?: string;
  loginId: string;
  region: string;
  housing: Housing;
  avatarUri?: string;
};

export type Account = User & { password: string };

export type Photo = { id: string; uri: string; createdAt: number };

export type DefectType = '곰팡이' | '균열' | '누수' | '결로' | '판단 보류';

export type AnalysisInput = {
  photo: Photo;
  location: string;
  /** 손상 위치 (벽면, 천장 등) */
  position: string;
  occurredAt: string; // YYYY.MM.DD
  memo: string;
  housing: Housing;
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
  /** 모델 신뢰도 0~1 */
  confidence: number;
  region: DefectRegion | null;
  cause: string;
  solutions: string[];
  prevention: string[];
  guide: Guide;
  needsRetake: boolean;
  createdAt: number;
};

export type Vendor = {
  id: string;
  label: string;
  name: string;
  description: string;
  phone: string;
  specialties: DefectType[];
};

export type Message = {
  id: string;
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
  status: '접수중' | '마감';
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
  defect: DefectType;
  risk: number;
  location: string;
  position: string;
  memo: string;
  createdAt: number;
};

/** 업체가 견적서를 보낸 유저에게 보내는 제안서 */
export type Proposal = {
  id: string;
  estimateId: string;
  vendorId: string;
  vendorName: string;
  vendorIntro: string;
  vendorRegion: string;
  /** 만원 단위 (5~10) */
  price: number;
  memo: string;
  createdAt: number;
};
