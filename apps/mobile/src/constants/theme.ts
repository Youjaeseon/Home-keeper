/**
 * 집사 디자인 시스템 (캐릭터 톤)
 * 마스코트 이미지에서 뽑은 3색이 기본입니다.
 *   크림 #F8E6D1 (배경) · 초록 #4F8457 (캐릭터 몸, 주요 버튼) · 갈색 #68412E (눈·콧수염·스패너, 글씨)
 * 그림자 없이 납작하게, 모서리는 크게 둥글게 씁니다.
 * 위험도 3색은 분석 결과의 위험도 게이지에만 씁니다.
 */
export const C = {
  bg: '#F8E6D1', // 전체 배경 (캐릭터 배경 크림)
  card: '#FFF7EE', // 카드·콘텐츠 영역 (밝은 크림)
  text: '#68412E', // 주요 아이콘·본문 (콧수염 갈색)
  sub: '#8E6B57', // 보조 글씨
  faint: '#BC9F89', // 흐린 글씨·비활성 아이콘
  primary: '#4F8457', // 선택된 메뉴·주요 버튼 (캐릭터 초록)
  onPrimary: '#FFF7EE', // 초록 위 글씨·아이콘
  accent: '#D6E3C5', // 강조 영역·일러스트 배경 (연초록)
  accentSoft: '#E9EFDC', // 칩·아이콘 배경
  accentCircle: 'rgba(255,247,238,0.7)', // 연초록 영역 안 원형
  border: '#EFD7BD',
  field: '#FBEEDF',
  scrim: 'rgba(104,65,46,0.42)', // 모달 뒤 어둡게
  // 위험도 게이지 전용
  riskLow: '#4F8457',
  riskMid: '#D8962C',
  riskHigh: '#C4533A',
  // 오류·주의 문구
  danger: '#C4533A',
  warnSoft: '#F9DFBC',
  warnText: '#7A4A1F',
};

export const F = {
  light: 'Pretendard-Light',
  regular: 'Pretendard-Regular',
  medium: 'Pretendard-Medium',
  semibold: 'Pretendard-SemiBold',
  bold: 'Pretendard-Bold',
  extrabold: 'Pretendard-ExtraBold',
};

/** 모서리: 캐릭터처럼 크게 둥글게. 버튼·칩은 완전한 알약 모양 */
export const R = { card: 28, field: 18, button: 999, tile: 24, pill: 999, sheet: 32, badge: 14 };

/** 선 아이콘 굵기 (캐릭터의 두툼한 선에 맞춤, 끝은 둥글게) */
export const STROKE = 2.2;

/** 웹에서 볼 때 모바일 폭으로 고정 */
export const MAX_W = 520;

/** 위험도 구간은 백엔드 severity_level 기준(low < 40 ≤ medium < 70 ≤ high)과 맞춥니다. */
export function riskColor(risk: number) {
  return risk >= 70 ? C.riskHigh : risk >= 40 ? C.riskMid : C.riskLow;
}

export function riskLabel(risk: number) {
  return risk >= 70 ? '높음' : risk >= 40 ? '주의' : '낮음';
}
