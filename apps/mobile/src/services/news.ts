/** 소식지: GET /support-programs (프로필 지역·거주 형태 기준 서버 정렬, 페이지네이션) */
import { getSupportPrograms } from '@/lib/api';
import type { SupportCategory, SupportProgramListItem } from '@/lib/api';
import type { NewsItem } from '@/types';

export type NewsFeedItem = NewsItem & { url: string; matched: boolean };

export type NewsFeedPage = {
  items: NewsFeedItem[];
  total: number;
  hasMore: boolean;
};

function statusOf(program: SupportProgramListItem): NewsItem['status'] {
  if (program.is_closed) return '마감';
  if (program.deadline_kind === 'fixed') return '접수중';
  if (program.deadline_kind === 'always_open') return '상시';
  return '기한 미확인';
}

export async function fetchNews(
  page: number,
  pageSize: number,
  category?: SupportCategory | null,
): Promise<NewsFeedPage> {
  const res = await getSupportPrograms({
    status: 'all',
    category: category ?? undefined,
    limit: pageSize,
    offset: page * pageSize,
  });
  const items: NewsFeedItem[] = res.items.map((p) => ({
    id: p.id,
    title: p.title,
    org: p.organization_name,
    summary: p.summary,
    regions: [p.region_name],
    housings: [],
    categories: p.categories,
    status: statusOf(p),
    url: p.detail_url,
    matched: p.housing_type_matched,
  }));
  return { items, total: res.total, hasMore: res.has_more };
}
