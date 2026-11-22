/** 소식지: GET /support-programs (프로필 지역·거주 형태 기준 서버 정렬, 페이지네이션) */
import { getSupportPrograms } from '@/lib/api';
import type { NewsItem } from '@/types';

export async function fetchNews(page: number, pageSize: number) {
  const res = await getSupportPrograms({ status: 'all', limit: pageSize, offset: page * pageSize });
  const items: (NewsItem & { url: string; matched: boolean })[] = res.items.map((p) => ({
    id: p.id,
    title: p.title,
    org: p.organization_name,
    summary: p.summary,
    regions: [p.region_name],
    housings: [],
    status: p.is_closed ? '마감' : '접수중',
    url: p.detail_url,
    matched: p.housing_type_matched,
  }));
  return { items, total: res.total, hasMore: res.has_more };
}
