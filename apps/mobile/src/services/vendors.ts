/** 업체 목록: GET /providers (특화 분야 필터 + 별점순). 실제 후보가 없으면 서버가 is_sample 후보를 돌려줍니다. */
import { getProviders, type ProviderSummary } from '@/lib/api';
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

export async function fetchVendors(regionId: string, workTypeId?: string | null) {
  const res = await getProviders({ regionId, workTypeId });
  return { vendors: res.providers.map(toVendor), isSample: res.is_sample };
}
