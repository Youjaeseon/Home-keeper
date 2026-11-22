/**
 * AI 하자 분석 서비스.
 *
 * 지금은 화면 흐름 확인용 mock입니다. 실제 연결 시 이 파일의 analyzeDefect만 교체합니다.
 *   1단계 YOLO: 하자 탐지 (유형 + bbox)
 *   2단계 SAM 3: 필요 시 손상 영역 분할
 *   3단계 OpenAI GPT vision: 원인 해석, 대응 가이드 생성
 *
 * 규칙:
 *   - API key는 앱에 넣지 않습니다. 앱은 팀 backend(EXPO_PUBLIC_API_URL)만 호출하고 key는 backend에만 둡니다.
 *   - 업로드 전 EXIF(위치 등) 제거, 실제 개인정보 전송 금지 (대회 규정).
 */
import type { AnalysisInput, AnalysisResult, DefectType, Guide, Housing } from '@/types';
import { josa, sleep, uid } from '@/utils';

export const ANALYSIS_STEPS = ['YOLO 하자 탐지', 'SAM 3 손상 영역 분할', 'GPT 원인 해석·대응 가이드'];

type Profile = Pick<
  AnalysisResult,
  'defect' | 'risk' | 'confidence' | 'region' | 'cause' | 'solutions' | 'prevention'
>;

// 장소별 mock 결과. 실제 모델 연결 후 삭제합니다.
const MOCK: Record<string, Profile> = {
  화장실: {
    defect: '곰팡이',
    risk: 89,
    confidence: 0.91,
    region: { x: 0.55, y: 0.45, r: 0.22 },
    cause: '환기 부족으로 습기가 오래 머물러 실리콘과 타일 줄눈에 곰팡이가 번식한 것으로 보입니다.',
    solutions: [
      '락스 희석액(물 10 : 락스 1)을 뿌리고 10분 뒤 닦아냅니다. 창문을 열고 장갑·마스크를 착용하세요.',
      '실리콘 속까지 검게 변했다면 기존 실리콘을 제거하고 새로 시공합니다.',
    ],
    prevention: ['샤워 후 30분 이상 환풍기를 켭니다.', '벽과 바닥의 물기를 스퀴지로 제거합니다.'],
  },
  주방: {
    defect: '곰팡이',
    risk: 72,
    confidence: 0.84,
    region: { x: 0.4, y: 0.6, r: 0.2 },
    cause: '싱크대 하부 배수구 주변에 습기가 고여 곰팡이가 생긴 것으로 보입니다.',
    solutions: [
      '하부장 물기를 말리고 곰팡이 제거제로 닦아냅니다.',
      '배수 호스 연결부에서 물이 새는지 휴지를 대어 확인합니다.',
    ],
    prevention: ['하부장 문을 하루 한 번 열어 환기합니다.'],
  },
  안방: {
    defect: '균열',
    risk: 64,
    confidence: 0.87,
    region: { x: 0.5, y: 0.4, r: 0.25 },
    cause: '벽지 아래 미장층이 건조·수축하면서 생긴 실금으로 보입니다.',
    solutions: [
      '균열 폭을 자로 재고 날짜와 함께 사진을 남깁니다.',
      '실금은 퍼티로 메운 뒤 도배로 마감할 수 있습니다.',
    ],
    prevention: ['2~4주 간격으로 같은 위치를 촬영해 길이·폭 변화를 비교합니다.'],
  },
  거실: {
    defect: '균열',
    risk: 58,
    confidence: 0.82,
    region: { x: 0.45, y: 0.35, r: 0.22 },
    cause: '창틀 모서리에서 시작된 사선 균열로, 온도 변화에 따른 수축·팽창이 원인일 수 있습니다.',
    solutions: ['폭이 0.3mm 이상이거나 계속 길어지면 전문가 점검을 받습니다.'],
    prevention: ['균열 끝부분에 날짜를 표시해 진행 여부를 확인합니다.'],
  },
  베란다: {
    defect: '결로',
    risk: 76,
    confidence: 0.88,
    region: { x: 0.5, y: 0.3, r: 0.24 },
    cause: '실내외 온도 차로 창틀과 외벽에 물방울이 맺히고, 곰팡이로 번지기 시작한 단계입니다.',
    solutions: ['물기를 바로 닦고 곰팡이 제거제로 처리합니다.', '창틀에 결로 방지 테이프를 붙입니다.'],
    prevention: ['하루 2번, 10분 이상 맞통풍 환기를 합니다.', '실내 습도를 60% 이하로 유지합니다.'],
  },
  천장: {
    defect: '누수',
    risk: 93,
    confidence: 0.9,
    region: { x: 0.5, y: 0.5, r: 0.28 },
    cause: '얼룩이 동심원 형태로 번지는 것으로 보아 위층 배관이나 방수층 누수 가능성이 있습니다.',
    solutions: [
      '얼룩 아래 전기 기구 사용을 멈추고 물받이를 둡니다.',
      '관리사무소나 위층 세대에 바로 알립니다.',
    ],
    prevention: ['얼룩 경계를 표시하고 매일 사진으로 번짐 여부를 확인합니다.'],
  },
};

// 신뢰도가 낮을 때의 결과 (오류·한계 대응 시연용)
const LOW_CONFIDENCE: Profile = {
  defect: '판단 보류',
  risk: 0,
  confidence: 0.38,
  region: null,
  cause: '사진에서 하자를 확실하게 찾지 못했습니다. 너무 어둡거나, 멀거나, 하자가 화면 밖에 있을 수 있습니다.',
  solutions: [],
  prevention: [],
};

export const CONFIDENCE_THRESHOLD = 0.6;

function buildGuide(housing: Housing, p: Profile, location: string, occurredAt: string): Guide {
  if (p.confidence < CONFIDENCE_THRESHOLD) {
    return {
      title: '다시 촬영해 주세요',
      body: '하자 부위가 화면 가운데 오도록, 밝은 곳에서 30cm 정도 거리에서 찍어 주세요. 장소를 구체적으로 고르면 정확도가 올라갑니다.',
    };
  }

  if (housing === '월세' || housing === '전세') {
    return {
      title: `${housing} 세입자 대응 가이드`,
      body: '',
      steps: [
        { title: '기록하기', desc: '날짜가 보이게 사진을 남기세요.' },
        { title: '원인 살피기', desc: '건물 문제인지, 환기·관리 같은 생활 습관 때문인지 확인하세요.' },
        { title: '집주인에게 알리기', desc: '원인이 무엇이든 문자로 먼저 알리세요.' },
        { title: '수리 협의하기', desc: '건물 문제는 집주인, 사용 중 생긴 문제는 세입자가 부담하는 것이 보통이에요.' },
      ],
      message: `안녕하세요, ○○호 세입자입니다. ${occurredAt}에 ${location}에서 ${josa(p.defect, '이', '가')} 발견되어 사진과 함께 알려 드립니다. 확인 후 수리 일정을 안내해 주시면 감사하겠습니다.`,
    };
  }

  if (housing === '자가') {
    return {
      title: '자가라면: 직접 보수하거나 견적을 비교하세요',
      body:
        p.risk >= 80
          ? '위험도가 높아 전문 업체 점검을 권합니다. 여러 업체 견적을 비교해 보세요.'
          : '아래 해결 방안으로 직접 보수해 볼 수 있습니다. 2주 뒤에도 그대로면 업체 점검을 받으세요.',
    };
  }

  return {
    title: '거주 형태에 맞는 안내',
    body: '기숙사·고시원 등은 먼저 관리자에게 알리세요. 사진과 날짜를 남겨 두면 책임 범위를 따질 때 도움이 됩니다.',
  };
}

export async function analyzeDefect(
  input: AnalysisInput,
  onStep?: (index: number) => void,
): Promise<AnalysisResult> {
  for (let i = 0; i < ANALYSIS_STEPS.length; i++) {
    onStep?.(i);
    await sleep(900);
  }

  const profile = MOCK[input.location] ?? LOW_CONFIDENCE;
  return {
    id: uid(),
    photoId: input.photo.id,
    photoUri: input.photo.uri,
    location: input.location,
    position: input.position,
    occurredAt: input.occurredAt,
    housing: input.housing,
    ...profile,
    guide: buildGuide(input.housing, profile, input.location, input.occurredAt),
    needsRetake: profile.confidence < CONFIDENCE_THRESHOLD,
    createdAt: Date.now(),
  };
}

export const isDefect = (d: DefectType) => d !== '판단 보류';
