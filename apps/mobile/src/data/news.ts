import type { Housing, NewsItem } from '@/types';

/**
 * 예시 데이터입니다. 실제 공고 내용과 다를 수 있으므로
 * 공개 API(예: 공공데이터포털) 연동 전까지는 화면에 "예시"로 표시합니다.
 */
export const NEWS: NewsItem[] = [
  {
    id: 'n1',
    title: '[예시] 청년 월세 지원 사업',
    org: '국토교통부 (예시)',
    summary: '무주택 청년의 월세 부담을 덜기 위한 지원 사업 예시입니다. 실제 자격과 금액은 공식 공고에서 확인하세요.',
    regions: ['전국'],
    housings: ['월세'],
    status: '접수중',
  },
  {
    id: 'n2',
    title: '[예시] LH 청년 매입임대 주택 입주자 모집',
    org: 'LH (예시)',
    summary: '시세보다 낮은 임대료로 거주할 수 있는 청년 주택 모집 예시입니다.',
    regions: ['전국'],
    housings: ['월세', '전세', '기타'],
    status: '마감',
  },
  {
    id: 'n3',
    title: '[예시] 청년 전세보증금 반환보증 보증료 지원',
    org: '주택도시보증공사 (예시)',
    summary: '전세사기 피해 예방을 위한 보증료 지원 예시입니다.',
    regions: ['전국'],
    housings: ['전세'],
    status: '접수중',
  },
  {
    id: 'n4',
    title: '[예시] 서울 청년 주거 안심 집수리 지원',
    org: '서울시 (예시)',
    summary: '노후 주택에 사는 청년 가구의 소규모 수선비 지원 예시입니다.',
    regions: ['서울'],
    housings: ['월세', '전세'],
    status: '접수중',
  },
  {
    id: 'n5',
    title: '[예시] 경기 청년 이사비·중개수수료 지원',
    org: '경기도 (예시)',
    summary: '경기도 거주 청년의 이사비와 중개수수료 지원 예시입니다.',
    regions: ['경기 수원', '경기 용인', '경기 성남'],
    housings: ['월세', '전세'],
    status: '접수중',
  },
  {
    id: 'n6',
    title: '[예시] 주택 임대차 분쟁조정 무료 상담',
    org: '주택임대차분쟁조정위원회 (예시)',
    summary: '수선 의무, 보증금 반환 등 임대차 분쟁 상담 안내 예시입니다.',
    regions: ['전국'],
    housings: ['월세', '전세'],
    status: '접수중',
  },
  {
    id: 'n7',
    title: '[예시] 에너지 효율 개선(단열·창호) 지원',
    org: '한국에너지재단 (예시)',
    summary: '결로·곰팡이 원인이 되는 단열 문제 개선 지원 예시입니다.',
    regions: ['전국'],
    housings: ['자가', '기타'],
    status: '마감',
  },
  {
    id: 'n8',
    title: '[예시] 인천 청년 주거비 부담 경감 사업',
    org: '인천시 (예시)',
    summary: '인천 거주 청년의 주거비 지원 예시입니다.',
    regions: ['인천'],
    housings: ['월세', '전세'],
    status: '접수중',
  },
  {
    id: 'n9',
    title: '[예시] 부산 청년 기쁨두배통장 (주거 연계)',
    org: '부산시 (예시)',
    summary: '부산 거주 청년 자산 형성 지원 예시입니다.',
    regions: ['부산'],
    housings: ['월세', '전세', '자가', '기타'],
    status: '접수중',
  },
];

/** 사용자 거주 지역·형태에 맞는 소식을 먼저 보여 줍니다. */
export function sortNewsFor(region: string, housing: Housing) {
  const score = (n: NewsItem) =>
    (n.regions.includes(region) ? 2 : n.regions.includes('전국') ? 1 : 0) +
    (n.housings.includes(housing) ? 2 : 0);
  return [...NEWS]
    .map((n) => ({ item: n, matched: score(n) >= 3 }))
    .sort((a, b) => score(b.item) - score(a.item));
}
