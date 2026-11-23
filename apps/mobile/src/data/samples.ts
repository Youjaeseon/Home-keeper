/**
 * 분석 탭의 샘플 사진(심사·데모용). 평가자가 하자 사진을 직접 찾지 않아도 바로 분석해 볼 수 있습니다.
 * 장소·위치·재질은 사진에 맞게 미리 채우고, 동의와 '분석 요청'은 사용자가 직접 누릅니다.
 */
export type SamplePhoto = {
  key: string;
  label: string;
  image: number;
  location: string;
  position: string;
  material: string;
};

export const SAMPLE_PHOTOS: SamplePhoto[] = [
  {
    key: 'mold',
    label: '샘플 · 곰팡이',
    image: require('@/assets/images/samples/sample-mold-bathroom.jpg'),
    location: '화장실',
    position: '모서리',
    material: '타일',
  },
  {
    key: 'peel',
    label: '샘플 · 벗겨짐',
    image: require('@/assets/images/samples/sample-peel-ceiling.jpg'),
    location: '화장실',
    position: '천장',
    material: '도장면(페인트)',
  },
];
