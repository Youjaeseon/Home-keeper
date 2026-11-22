/**
 * AI 하자 분석 서비스 — 팀 백엔드 연동.
 *   POST /records → POST /records/{id}/analyze (multipart: 사진 1장 overview, location, material, symptoms, region_id, external_analysis_consent)
 *   → GET /records/{id}로 저장 결과(단기 Signed URL 포함)를 다시 읽어 화면 타입으로 변환합니다.
 *
 * 규칙:
 *   - API key는 앱에 넣지 않습니다. 앱은 팀 backend(EXPO_PUBLIC_API_URL)만 호출합니다.
 *   - 업로드 전 EXIF(위치 등)는 받지 않습니다(ImagePicker exif: false).
 */
import { analyzeRecord, createRecord, getRecord, type DiagnosisResult, type RecordDetail } from '@/lib/api';
import type { AnalysisInput, AnalysisResult, DefectType, Guide, Housing } from '@/types';
import { josa } from '@/utils';

/** 화면의 진행 단계 표시. 서버는 한 번의 요청으로 처리하므로 단계는 요청 전후로만 바뀝니다. */
export const ANALYSIS_STEPS = ['사진 업로드', 'AI 하자 탐지·진단', '결과 저장'];

/** 팀원 UI의 장소·위치 두 칸을 백엔드 location 한 칸으로 합칩니다. */
const LOCATION_SEP = ' · ';
export const joinLocation = (location: string, position: string) =>
  position ? `${location}${LOCATION_SEP}${position}` : location;
export function splitLocation(value: string | null): { location: string; position: string } {
  const [location, ...rest] = (value ?? '').split(LOCATION_SEP);
  return { location: location || '위치 미입력', position: rest.join(LOCATION_SEP) };
}

const KNOWN: DefectType[] = ['곰팡이', '균열', '벗겨짐', '누수', '결로'];
export function toDefect(suspected: string[], undetermined: boolean): DefectType {
  if (undetermined) return '판단 보류';
  return (KNOWN.find((d) => suspected.includes(d)) ?? (suspected[0] as DefectType | undefined)) ?? '판단 보류';
}

function guessMime(uri: string) {
  const ext = uri.split('?')[0].split('.').pop()?.toLowerCase();
  if (ext === 'png') return { type: 'image/png', name: 'photo.png' };
  if (ext === 'heic' || ext === 'heif') return { type: `image/${ext}`, name: `photo.${ext}` };
  return { type: 'image/jpeg', name: 'photo.jpg' };
}

/** 저장된 기록 상세 → 화면 결과 타입 */
export function toAnalysisResult(
  detail: RecordDetail,
  meta: { housing: Housing; occurredAt: string; createdAt: number; photoUri?: string; landlordDraft?: string | null },
): AnalysisResult | null {
  const d: DiagnosisResult | undefined = detail.diagnosis?.diagnosis;
  if (!d) return null;
  const { location, position } = splitLocation(detail.location);
  const undetermined = d.severity_level === 'undetermined' || d.severity_score === null;
  const defect = toDefect(d.suspected_types, undetermined);
  const risk = d.severity_score ?? 0;
  const photo = detail.photos.find((p) => p.role === 'overview') ?? detail.photos[0];
  const base = { defect, risk, needsRetake: undetermined };
  return {
    id: detail.record_id,
    photoId: detail.record_id,
    // Signed URL은 5분 뒤 만료되므로 화면에 들어올 때마다 GET /records/{id}로 새로 받습니다.
    photoUri: photo?.url ?? meta.photoUri ?? '',
    location,
    position,
    occurredAt: meta.occurredAt,
    housing: meta.housing,
    defect,
    risk,
    confidence: null,
    region: null,
    cause: undetermined
      ? [d.reason, ...d.unknowns].filter(Boolean).join('\n')
      : [...d.causes, d.reason].filter(Boolean).join('\n'),
    solutions: d.care_steps,
    prevention: d.prevention_tips,
    guide: buildGuide(meta.housing, base, location, meta.occurredAt, meta.landlordDraft),
    needsRetake: undetermined,
    createdAt: meta.createdAt,
    workTypeId: d.work_type_id,
    estimationNotice: d.estimation_notice,
    source: d.source,
  };
}

export function buildGuide(
  housing: Housing,
  p: Pick<AnalysisResult, 'defect' | 'risk' | 'needsRetake'>,
  location: string,
  occurredAt: string,
  landlordDraft?: string | null,
): Guide {
  if (p.needsRetake) {
    return {
      title: '다시 촬영해 주세요',
      body: '하자 부위가 화면 가운데 오도록, 밝은 곳에서 30cm 정도 거리에서 찍어 주세요. 장소를 구체적으로 고르면 정확도가 올라갑니다.',
    };
  }

  if (housing === '월세' || housing === '전세' || housing === '반전세') {
    return {
      title: `${housing} 세입자 대응 가이드`,
      body: '',
      // TODO(integration-gap): GAP-012 대응 순서(steps)는 팀원 하드코딩 안내입니다. 백엔드에는 대응 순서 API가 없습니다.
      steps: [
        { title: '기록하기', desc: '날짜가 보이게 사진을 남기세요.' },
        { title: '원인 살피기', desc: '건물 문제인지, 환기·관리 같은 생활 습관 때문인지 확인하세요.' },
        { title: '집주인에게 알리기', desc: '원인이 무엇이든 문자로 먼저 알리세요.' },
        { title: '수리 협의하기', desc: '건물 문제는 집주인, 사용 중 생긴 문제는 세입자가 부담하는 것이 보통이에요.' },
      ],
      // 집주인 문자는 백엔드 임대인 요청문(POST /records/{id}/drafts/landlord 또는 template)을 씁니다.
      message:
        landlordDraft ??
        `안녕하세요, ○○호 세입자입니다. ${occurredAt}에 ${location}에서 ${josa(p.defect, '이', '가')} 발견되어 사진과 함께 알려 드립니다. 확인 후 수리 일정을 안내해 주시면 감사하겠습니다.`,
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
  onStep?.(0);
  const { record_id } = await createRecord();
  onStep?.(1);
  // TODO(integration-gap): GAP-009 팀원 UI는 사진 1장만 받습니다. 백엔드는 1~2장(overview/closeup)을 지원합니다.
  await analyzeRecord(record_id, {
    photos: [{ uri: input.photo.uri, ...guessMime(input.photo.uri), role: 'overview' }],
    location: joinLocation(input.location, input.position),
    material: input.material,
    symptoms: input.memo,
    region_id: input.regionId,
    externalAnalysisConsent: input.consent,
  });
  onStep?.(2);
  const detail = await getRecord(record_id);
  const result = toAnalysisResult(detail, {
    housing: input.housing,
    occurredAt: input.occurredAt,
    createdAt: Date.now(),
    photoUri: input.photo.uri,
  });
  if (!result) throw new Error('진단 결과가 저장되지 않았습니다. 다시 시도해 주세요.');
  return result;
}

export const isDefect = (d: DefectType) => d !== '판단 보류';
