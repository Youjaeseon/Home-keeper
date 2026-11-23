import { router } from 'expo-router';
import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp, ScanSearch } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Linking, Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { AppBar, Banner, Card, Chip, Hero, Screen, Txt } from '@/components/ui';
import { C, F, R, STROKE } from '@/constants/theme';
import { CATEGORY_LABELS, regionLabel } from '@/data/options';
import { getSupportProgram, messageOf, type SupportCategory, type SupportProgramDetail } from '@/lib/api';
import { fetchNews, type NewsFeedItem } from '@/services/news';
import { useApp } from '@/store/app-store';
import { pageWindow } from '@/utils';

const PAGE_SIZE = 5;

const CATEGORY_FILTERS: { value: SupportCategory | null; label: string }[] = [
  { value: null, label: '전체' },
  { value: 'monthly_rent_support', label: CATEGORY_LABELS.monthly_rent_support },
  { value: 'deposit_loan', label: CATEGORY_LABELS.deposit_loan },
  { value: 'housing_cost', label: CATEGORY_LABELS.housing_cost },
  { value: 'repair', label: CATEGORY_LABELS.repair },
  { value: 'brokerage_fee', label: CATEGORY_LABELS.brokerage_fee },
  { value: 'supply', label: CATEGORY_LABELS.supply },
  { value: 'other', label: CATEGORY_LABELS.other },
];

/** 스케치 4: 소식지 — 사용자 정보 맞춤 사업 및 지원 정보 */
export default function NewsScreen() {
  const { user, isGuest, enterAuthScreen } = useApp();
  const [page, setPage] = useState(0);
  const [openId, setOpenId] = useState<string | null>(null);
  const [visible, setVisible] = useState<NewsFeedItem[]>([]);
  const [total, setTotal] = useState(0);
  const [category, setCategory] = useState<SupportCategory | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // 펼친 공고의 상세(GET /support-programs/{id})를 한 번만 불러 둡니다. (GAP-030)
  const [details, setDetails] = useState<Record<string, SupportProgramDetail | string>>({});

  const toggle = (id: string, open: boolean) => {
    setOpenId(open ? null : id);
    if (open || details[id]) return;
    getSupportProgram(id)
      .then((d) => setDetails((prev) => ({ ...prev, [id]: d })))
      .catch((e) => setDetails((prev) => ({ ...prev, [id]: messageOf(e) })));
  };

  // 서버가 프로필 지역·거주 형태에 맞춰 정렬하므로 조건이 바뀌면 다시 불러옵니다.
  const signedIn = !!user;
  const load = () =>
    fetchNews(page, PAGE_SIZE, category)
      .then((res) => {
        setVisible(res.items);
        setTotal(res.total);
        setError(null);
        setLoaded(true);
      })
      .catch((e) => {
        setError(messageOf(e));
        setLoaded(true);
      });
  useEffect(() => {
    if (!signedIn) return;
    fetchNews(page, PAGE_SIZE, category)
      .then((res) => {
        setVisible(res.items);
        setTotal(res.total);
        setError(null);
        setLoaded(true);
      })
      .catch((e) => {
        setError(messageOf(e));
        setLoaded(true);
      });
  }, [page, signedIn, user?.regionId, user?.housing, category]);

  if (!user) return null;
  const pageCount = Math.ceil(total / PAGE_SIZE);
  const pages = pageWindow(page, pageCount);
  const windowStart = pages[0] ?? 0;
  const hasPrevious = windowStart > 0;
  const hasNext = pages.length > 0 && windowStart + pages.length < pageCount;

  return (
    <Screen safeTop onRefresh={load}>
      <AppBar title="소식지" />
      {isGuest && (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="체험 중 안내, 로그인 또는 회원가입으로 전환"
          onPress={async () => {
            await enterAuthScreen();
            router.replace('/');
          }}
          style={({ pressed }) => [s.guestBar, pressed && { opacity: 0.8 }]}>
          <View style={s.guestBadge}>
            <Txt variant="caption" color={C.onPrimary} style={{ fontFamily: F.bold }}>
              체험 중
            </Txt>
          </View>
          <Txt variant="caption" color={C.text} style={{ flex: 1 }}>
            로그인 없이 모든 기능을 체험하고 있어요
          </Txt>
          <View style={s.guestAction}>
            <Txt variant="caption" color={C.primary} style={{ fontFamily: F.bold }}>
              로그인
            </Txt>
            <ChevronRight size={14} color={C.primary} strokeWidth={STROKE} />
          </View>
        </Pressable>
      )}
      <Hero title={`${user.nickname}님을 위한,\n맞춤 소식이에요.`} />

      <Banner
        title="사진 한 장으로 하자 진단"
        subtitle={'곰팡이 · 균열 처리방법\nAI가 알려 드려요'}
        icon={ScanSearch}
        onPress={() => router.push('/analyze')}
      />

      <View style={s.sectionHead}>
        <Txt variant="title">지원 소식</Txt>
        <Txt variant="caption" muted>
          {regionLabel(user.region)} · {user.housing}
        </Txt>
      </View>

      <View style={s.filterGroup}>
        <Txt variant="caption" muted>
          분류
        </Txt>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={s.filters}>
          {CATEGORY_FILTERS.map(({ value, label }) => (
            <Chip
              key={label}
              label={label}
              active={category === value}
              onPress={() => {
                setCategory(value);
                setPage(0);
              }}
            />
          ))}
        </ScrollView>
      </View>

      <Card style={{ padding: 8, gap: 0 }}>
        {error && (
          <Txt variant="sub" color={C.danger} style={{ padding: 16 }}>
            {error}
          </Txt>
        )}
        {!error && loaded && visible.length === 0 && (
          <Txt variant="sub" muted style={{ padding: 16 }}>
            선택한 조건의 지원 소식이 없어요.
          </Txt>
        )}
        {visible.map((item, i) => {
          const open = openId === item.id;
          const Chevron = open ? ChevronUp : ChevronDown;
          return (
            <Pressable
              key={item.id}
              accessibilityRole="button"
              accessibilityState={{ expanded: open }}
              onPress={() => toggle(item.id, open)}
              style={({ pressed }) => [s.item, i > 0 && s.divider, pressed && { opacity: 0.7 }]}>
              <View style={s.itemTop}>
                <View style={{ flex: 1, gap: 6 }}>
                  <View style={s.status}>
                    <Txt
                      variant="caption"
                      color={
                        item.status === '마감'
                          ? C.faint
                          : item.status === '기한 미확인'
                            ? C.sub
                            : C.text
                      }>
                      {item.status}
                    </Txt>
                  </View>
                  <Txt variant="bodyStrong" numberOfLines={open ? undefined : 2}>
                    {item.title}
                  </Txt>
                  <Txt variant="caption" muted>
                    {item.regions[0]} · {item.org}
                  </Txt>
                  <View style={s.chips}>
                    {item.categories.map((category) => (
                      <Chip key={category} label={CATEGORY_LABELS[category]} />
                    ))}
                  </View>
                </View>
                <Chevron size={18} color={C.sub} strokeWidth={STROKE} />
              </View>
              {open && (
                <Txt variant="sub" color={C.text}>
                  {item.summary}
                </Txt>
              )}
              {open && <ProgramDetail detail={details[item.id]} />}
              {open && !!item.url && (
                <Txt variant="caption" color={C.primary} onPress={() => Linking.openURL(item.url)}>
                  공고 원문 보기
                </Txt>
              )}
            </Pressable>
          );
        })}
      </Card>

      <View style={s.pager}>
        {hasPrevious && (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="이전 페이지"
            onPress={() => setPage(windowStart - 1)}
            style={s.dot}>
            <ChevronLeft size={18} color={C.text} strokeWidth={STROKE} />
          </Pressable>
        )}
        {pages.map((i) => {
          const active = i === page;
          return (
            <Pressable
              key={i}
              accessibilityRole="button"
              accessibilityLabel={`${i + 1}페이지`}
              onPress={() => setPage(i)}
              style={[s.dot, active && s.dotActive]}>
              <Txt variant="label" color={active ? C.onPrimary : C.text} style={{ fontFamily: F.bold }}>
                {i + 1}
              </Txt>
            </Pressable>
          );
        })}
        {hasNext && (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="다음 페이지"
            onPress={() => setPage(windowStart + pages.length)}
            style={s.dot}>
            <ChevronRight size={18} color={C.text} strokeWidth={STROKE} />
          </Pressable>
        )}
      </View>
    </Screen>
  );
}

function ProgramDetail({ detail }: { detail: SupportProgramDetail | string | undefined }) {
  if (detail === undefined) {
    return (
      <Txt variant="caption" muted>
        상세 정보를 불러오는 중...
      </Txt>
    );
  }
  if (typeof detail === 'string') {
    return (
      <Txt variant="caption" color={C.danger}>
        {detail}
      </Txt>
    );
  }
  const rows: [string, string | null][] = [
    ['지원 대상', detail.support_target],
    ['지원 내용', detail.support_content],
    ['선정 기준', detail.selection_criteria],
    ['신청 방법', detail.apply_method],
    ['마감', detail.deadline_text],
  ];
  return (
    <View style={{ gap: 8 }}>
      {rows
        .filter(([, v]) => !!v)
        .map(([k, v]) => (
          <View key={k} style={{ gap: 2 }}>
            <Txt variant="label" muted>
              {k}
            </Txt>
            <Txt variant="sub" color={C.text}>
              {v}
            </Txt>
          </View>
        ))}
      <Txt variant="caption" muted>
        출처: {detail.source_attribution} (확인 {detail.source_checked_at.slice(0, 10)})
      </Txt>
    </View>
  );
}

const s = StyleSheet.create({
  guestBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: C.accentSoft,
    borderRadius: R.field,
    paddingHorizontal: 14,
    paddingVertical: 11,
  },
  guestBadge: {
    backgroundColor: C.primary,
    borderRadius: R.pill,
    paddingHorizontal: 9,
    paddingVertical: 3,
  },
  guestAction: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
  },
  sectionHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 },
  filterGroup: { gap: 6 },
  filters: { gap: 8, paddingRight: 8 },
  status: {
    alignSelf: 'flex-start',
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 999,
    backgroundColor: C.accent,
  },
  item: { padding: 16, gap: 10, borderRadius: 20 },
  itemTop: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  divider: { borderTopWidth: 1, borderTopColor: C.border, borderRadius: 0 },
  pager: { flexDirection: 'row', justifyContent: 'center', gap: 10, paddingVertical: 4 },
  dot: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: C.card,
    borderWidth: 1.5,
    borderColor: C.border,
  },
  dotActive: { backgroundColor: C.primary, borderColor: C.primary },
});
