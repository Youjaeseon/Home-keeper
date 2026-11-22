/** 업체 목록: GET /providers (특화 분야 필터 + 별점순). 실제 후보가 없으면 서버가 is_sample 후보를 돌려줍니다. */
import { realVendorsFor, usesRealVendors } from '@/data/yongin-vendors';
import { getProviders, getWorkTypes, type ProviderSummary, type WorkType } from '@/lib/api';
import { DEMO_VENDORS } from '@/data/demo';
import type { Vendor } from '@/types';

const LABELS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';

export function toVendor(p: ProviderSummary, index: number): Vendor {
  return {
    id: p.provider_id,
    label: LABELS[index] ?? String(index + 1),
    name: p.name,
    description: p.description ?? '',
    // TODO(integration-gap): GAP-018 전화번호가 없는 업체(샘플 포함)는 '연락처 없음'으로 표시합니다.
    phone: p.phone ?? '연락처 없음',
    specialties: p.specialty_work_types.map((w) => w.name),
    specialtyIds: p.specialty_work_types.map((w) => w.work_type_id),
    rating: p.rating,
    reviewCount: p.review_count,
    chatAvailable: p.chat_available,
    isSample: p.is_sample,
  };
}

/**
 * 실제 업체 뒤에 시연용 가상 업체(data/demo.ts)를 붙입니다.
 * 서버가 실제 후보 없이 채팅 불가 샘플만 돌려주면, 채팅까지 해 볼 수 있는 가상 업체로 바꿔 보여 줍니다.
 */
export async function fetchVendors(regionId: string, workTypeId?: string | null, regionName?: string | null) {
  // 경기도 용인시는 실제 업체 데이터셋만 보여 줍니다(테스트·가상 업체 숨김). 다른 지역은 기존 그대로.
  if (usesRealVendors(regionName)) {
    const types = await getWorkTypes().catch(() => [] as WorkType[]);
    const ids = Object.fromEntries(types.map((t) => [t.name, t.work_type_id]));
    return { vendors: realVendorsFor(ids), isSample: false };
  }
  const res = await getProviders({ regionId, workTypeId }).catch(() => null);
  const real = res && !res.is_sample ? res.providers.map(toVendor) : [];
  const demo = DEMO_VENDORS.map((v, i) => ({ ...v, label: LABELS[real.length + i] ?? v.label }));
  return { vendors: [...real, ...demo], isSample: real.length === 0 };
}
