import { router } from 'expo-router';
import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp, ScanSearch } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Linking, Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { AppBar, Banner, Card, Chip, Hero, Screen, Txt } from '@/components/ui';
import { C, F, STROKE } from '@/constants/theme';
import { CATEGORY_LABELS, regionLabel } from '@/data/options';
import { messageOf, type SupportCategory } from '@/lib/api';
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
  const { user } = useApp();
  const [page, setPage] = useState(0);
  const [openId, setOpenId] = useState<string | null>(null);
  const [visible, setVisible] = useState<NewsFeedItem[]>([]);
  const [total, setTotal] = useState(0);
  const [category, setCategory] = useState<SupportCategory | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 서버가 프로필 지역·거주 형태에 맞춰 정렬하므로 조건이 바뀌면 다시 불러옵니다.
  const signedIn = !!user;
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
    <Screen safeTop>
      <AppBar title="소식지" />
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
              onPress={() => setOpenId(open ? null : item.id)}
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

const s = StyleSheet.create({
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
