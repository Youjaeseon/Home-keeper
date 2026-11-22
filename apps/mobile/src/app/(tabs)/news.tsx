import { router } from 'expo-router';
import { ChevronDown, ChevronUp, Pencil, ScanSearch } from 'lucide-react-native';
import { useState } from 'react';
import { Modal, Pressable, StyleSheet, View } from 'react-native';

import { Select } from '@/components/select';
import { AppBar, Banner, Button, Card, Hero, Screen, Txt } from '@/components/ui';
import { C, F, R, STROKE } from '@/constants/theme';
import { sortNewsFor } from '@/data/news';
import { HOUSINGS, REGIONS, regionLabel } from '@/data/options';
import { useApp } from '@/store/app-store';

const PAGE_SIZE = 3;

/** 스케치 4: 소식지 — 사용자 정보 맞춤 사업 및 지원 정보 */
export default function NewsScreen() {
  const { user, updateUser } = useApp();
  const [page, setPage] = useState(0);
  const [openId, setOpenId] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  if (!user) return null;

  const list = sortNewsFor(user.region, user.housing);
  const pageCount = Math.ceil(list.length / PAGE_SIZE);
  const visible = list.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

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
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="지역과 거주 형태 수정"
          hitSlop={10}
          onPress={() => setEditing(true)}
          style={({ pressed }) => [s.filter, pressed && { opacity: 0.6 }]}>
          <Txt variant="caption" muted>
            {regionLabel(user.region)} · {user.housing}
          </Txt>
          <Pencil size={14} color={C.sub} strokeWidth={STROKE} />
        </Pressable>
      </View>

      <Card style={{ padding: 8, gap: 0 }}>
        {visible.map(({ item }, i) => {
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
                    <Txt variant="caption" color={item.status === '마감' ? C.faint : C.text}>
                      {item.status}
                    </Txt>
                  </View>
                  <Txt variant="bodyStrong" numberOfLines={open ? undefined : 2}>
                    {item.title}
                  </Txt>
                  <Txt variant="caption" muted>
                    {item.org}
                  </Txt>
                </View>
                <Chevron size={18} color={C.sub} strokeWidth={STROKE} />
              </View>
              {open && (
                <Txt variant="sub" color={C.text}>
                  {item.summary}
                </Txt>
              )}
            </Pressable>
          );
        })}
      </Card>

      <View style={s.pager}>
        {Array.from({ length: pageCount }, (_, i) => {
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
      </View>

      {/* 지역 · 거주 형태 수정 */}
      <Modal visible={editing} transparent animationType="fade" onRequestClose={() => setEditing(false)}>
        <Pressable style={s.backdrop} onPress={() => setEditing(false)}>
          <Pressable style={s.sheet} onPress={() => {}}>
            <Txt variant="h2">내 조건 수정</Txt>
            <Select
              label="거주지역"
              value={user.region}
              options={REGIONS}
              onChange={(region) => {
                updateUser({ region });
                setPage(0);
              }}
            />
            <Select
              label="거주형태"
              value={user.housing}
              options={HOUSINGS}
              onChange={(housing) => {
                updateUser({ housing });
                setPage(0);
              }}
            />
            <Button title="완료" onPress={() => setEditing(false)} />
          </Pressable>
        </Pressable>
      </Modal>
    </Screen>
  );
}

const s = StyleSheet.create({
  sectionHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 },
  filter: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  backdrop: { flex: 1, backgroundColor: C.scrim, justifyContent: 'center', padding: 24 },
  sheet: {
    backgroundColor: C.card,
    borderRadius: R.card,
    padding: 22,
    gap: 16,
    width: '100%',
    maxWidth: 420,
    alignSelf: 'center',
  },
  status: {
    alignSelf: 'flex-start',
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 999,
    backgroundColor: C.accent,
  },
  item: { padding: 16, gap: 10, borderRadius: 20 },
  itemTop: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
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
