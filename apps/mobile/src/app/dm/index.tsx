import { Image } from 'expo-image';
import { router, useLocalSearchParams } from 'expo-router';
import { ChevronRight, Send } from 'lucide-react-native';
import { useEffect, useRef, useState } from 'react';
import { Animated, Pressable, StyleSheet, View } from 'react-native';

import { Button, Card, Chip, DeleteButton, Field, Hero, Screen, Txt } from '@/components/ui';
import { C, F, STROKE } from '@/constants/theme';
import { SAMPLE_ESTIMATES, SAMPLE_PROPOSALS } from '@/data/samples';
import { VENDORS } from '@/data/vendors';
import { useApp } from '@/store/app-store';
import type { Estimate, Proposal } from '@/types';

type Tab = 'messages' | 'quotes';
/** 제안 가격 선택지 (만원) */
const PRICES = [5, 6, 7, 8, 9, 10];

/** 채팅 목록 — 상단 탭: 메시지 | 제안서(유저) 또는 견적서(업체) */
export default function DmListScreen() {
  const params = useLocalSearchParams<{ tab?: string }>();
  const { user } = useApp();
  const [tab, setTab] = useState<Tab>(params.tab === 'quotes' ? 'quotes' : 'messages');
  const TABS: { key: Tab; label: string }[] = [
    { key: 'messages', label: '메시지' },
    { key: 'quotes', label: user?.role === '업체' ? '견적서' : '제안서' },
  ];

  return (
    <Screen>
      <View style={s.tabs}>
        {TABS.map((t) => {
          const on = t.key === tab;
          return (
            <Pressable
              key={t.key}
              accessibilityRole="tab"
              accessibilityState={{ selected: on }}
              onPress={() => setTab(t.key)}
              style={[s.tab, on && s.tabOn]}>
              <Txt variant="label" color={on ? C.onPrimary : C.sub} style={{ fontFamily: F.bold, fontSize: 14 }}>
                {t.label}
              </Txt>
            </Pressable>
          );
        })}
      </View>
      {tab === 'messages' ? <Messages /> : <Quotes />}
    </Screen>
  );
}

function Messages() {
  const { messages } = useApp();
  return (
    <>
      <Hero title="메시지" subtitle="업체와 나눈 대화를 모아 볼 수 있어요." />
      <Card style={{ padding: 8, gap: 0 }}>
        {VENDORS.map((v, i) => {
          const thread = messages.filter((m) => m.vendorId === v.id);
          const last = thread[thread.length - 1];
          return (
            <Pressable
              key={v.id}
              accessibilityRole="button"
              accessibilityLabel={`${v.name} 대화 열기`}
              onPress={() => router.push({ pathname: '/dm/[vendorId]', params: { vendorId: v.id } })}
              style={({ pressed }) => [s.row, i > 0 && s.divider, pressed && { opacity: 0.7 }]}>
              <View style={s.avatar}>
                <Txt variant="h2">{v.label}</Txt>
              </View>
              <View style={{ flex: 1, gap: 2 }}>
                <Txt variant="bodyStrong">{v.name}</Txt>
                <Txt variant="sub" muted numberOfLines={1}>
                  {last ? last.text : '아직 대화가 없어요'}
                </Txt>
              </View>
              {last && last.from === 'vendor' ? (
                <View style={s.unread} />
              ) : (
                <ChevronRight size={18} color={C.faint} strokeWidth={STROKE} />
              )}
            </Pressable>
          );
        })}
      </Card>
    </>
  );
}

/** 유저: 받은 제안서 (견적서별로 묶음) / 업체: 받은 견적서와 보낸 제안서. 예시 데이터를 함께 보여 줍니다. */
function Quotes() {
  const { user, estimates, proposals, hidden, removeEstimate, removeProposal, accepted, acceptProposal, cancelAccept } = useApp();
  if (!user) return null;
  const vendor = user.role === '업체';
  const own = vendor ? estimates.filter((e) => e.userId !== user.loginId) : estimates.filter((e) => e.userId === user.loginId);
  const list = [...own, ...SAMPLE_ESTIMATES].filter((e) => !hidden.includes(e.id));
  const all = [...proposals, ...SAMPLE_PROPOSALS].filter((p) => !hidden.includes(p.id));

  return (
    <>
      <Hero
        title={vendor ? '받은 견적서' : '받은 제안서'}
        subtitle={vendor ? '견적서를 확인하고 제안서를 보내 보세요.' : '업체가 보낸 제안서를 비교해 보세요.'}
      />
      {!vendor && own.length === 0 && (
        <Txt variant="sub" muted>
          분석 결과 화면에서 견적서를 보내면 여기에 제안서가 도착해요.
        </Txt>
      )}
      {list.map((e) => {
        const mine = proposals.find((p) => p.estimateId === e.id && p.vendorId === user.loginId);
        const related = all.filter((p) => p.estimateId === e.id).sort((a, b) => a.price - b.price);
        return (
          <Card key={e.id}>
            <EstimateSummary e={e} showSender={vendor} onDelete={() => removeEstimate(e.id)} />
            {vendor ? (
              mine ? (
                <ProposalBox p={mine} title="보낸 제안서" onDelete={() => removeProposal(mine.id)} />
              ) : (
                <ProposalForm estimateId={e.id} />
              )
            ) : related.length === 0 ? (
              <Txt variant="sub" muted>
                아직 받은 제안서가 없어요.
              </Txt>
            ) : (
              <>
                <Txt variant="label" muted>
                  제안서 {related.length}건
                </Txt>
                {related.map((p) => (
                  <ProposalBox
                    key={p.id}
                    p={p}
                    chat
                    onDelete={() => removeProposal(p.id)}
                    accept={!accepted[e.id] ? 'open' : accepted[e.id] === p.id ? 'accepted' : 'closed'}
                    onAccept={() => acceptProposal(e.id, p.id)}
                    onCancelAccept={() => cancelAccept(e.id)}
                  />
                ))}
              </>
            )}
          </Card>
        );
      })}
    </>
  );
}

function EstimateSummary({ e, showSender, onDelete }: { e: Estimate; showSender: boolean; onDelete: () => void }) {
  return (
    <View style={{ gap: 12 }}>
      <View style={s.quote}>
        <Image source={e.photoAsset ?? { uri: e.photoUri }} style={s.quotePhoto} contentFit="cover" />
        <View style={{ flex: 1, gap: 6 }}>
          <View style={{ flexDirection: 'row', gap: 6 }}>
            <Chip label={e.defect} active />
            <Chip label={`위험도 ${e.risk}%`} />
          </View>
          <Txt variant="bodyStrong">
            {e.location} · {e.position}
          </Txt>
          {showSender && (
            <Txt variant="caption" muted>
              {e.userNickname} · {e.region}
            </Txt>
          )}
        </View>
        <View style={{ alignSelf: 'flex-start' }}>
          <DeleteButton label="견적서" onDelete={onDelete} />
        </View>
      </View>
      {e.memo !== '' && (
        <Txt variant="sub" color={C.text}>
          메모: {e.memo}
        </Txt>
      )}
    </View>
  );
}

type AcceptState = 'open' | 'accepted' | 'closed';

function ProposalBox({
  p,
  title,
  chat,
  onDelete,
  accept,
  onAccept,
  onCancelAccept,
}: {
  p: Proposal;
  title?: string;
  chat?: boolean;
  onDelete: () => void;
  /** 유저가 받은 제안서일 때: 수락 전 / 이 제안서를 수락함 / 다른 제안서를 수락해서 마감됨 */
  accept?: AcceptState;
  onAccept?: () => void;
  onCancelAccept?: () => void;
}) {
  const [asking, setAsking] = useState(false);
  const closed = accept === 'closed';
  // 다른 제안서를 수락하면 서서히 흐려집니다.
  const fade = useRef(new Animated.Value(closed ? 0.3 : 1)).current;
  useEffect(() => {
    Animated.timing(fade, { toValue: closed ? 0.3 : 1, duration: 450, useNativeDriver: true }).start();
  }, [closed, fade]);

  // 받은 제안서를 누르면 그 업체와의 채팅으로 이동합니다.
  const openChat = () => {
    const known = VENDORS.find((v) => v.name === p.vendorName);
    router.push({
      pathname: '/dm/[vendorId]',
      params: known ? { vendorId: known.id } : { vendorId: p.vendorId, name: p.vendorName },
    });
  };
  return (
    <Animated.View style={{ opacity: fade }} pointerEvents={closed ? 'none' : 'auto'}>
      <Pressable
        accessibilityRole={chat ? 'button' : undefined}
        accessibilityLabel={chat ? `${p.vendorName}와 채팅하기` : undefined}
        disabled={!chat || closed}
        onPress={openChat}
        style={({ pressed }) => [s.proposal, accept === 'accepted' && s.proposalAccepted, pressed && { opacity: 0.75 }]}>
        {title && (
          <Txt variant="label" color={C.primary}>
            {title}
          </Txt>
        )}
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
          <View style={{ flex: 1, gap: 2 }}>
            <Txt variant="bodyStrong">{p.vendorName}</Txt>
            <Txt variant="caption" muted>
              {[p.vendorRegion, p.vendorIntro].filter(Boolean).join(' · ')}
            </Txt>
          </View>
          <Txt variant="title" color={C.primary}>
            {p.price}만원
          </Txt>
          <DeleteButton label="제안서" onDelete={onDelete} />
        </View>
        {p.memo !== '' && (
          <Txt variant="sub" color={C.text}>
            {p.memo}
          </Txt>
        )}
        {asking && (
          <View style={s.ask}>
            <Txt variant="sub" color={C.text} style={{ fontFamily: F.semibold }}>
              수락하면 다른 제안서는 받을 수 없어요.
            </Txt>
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="수락 확정"
                onPress={() => {
                  setAsking(false);
                  onAccept?.();
                }}
                style={[s.pill, s.pillGreen]}>
                <Txt variant="label" color={C.onPrimary} style={{ fontFamily: F.bold }}>
                  수락 확정
                </Txt>
              </Pressable>
              <Pressable accessibilityRole="button" onPress={() => setAsking(false)} style={[s.pill, s.pillGhost]}>
                <Txt variant="label" color={C.sub}>
                  취소
                </Txt>
              </Pressable>
            </View>
          </View>
        )}
        {(chat || accept) && !asking && (
          <View style={s.boxFoot}>
            {accept === 'open' ? (
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={`${p.vendorName} 제안 수락`}
                hitSlop={6}
                onPress={() => setAsking(true)}
                style={[s.pill, s.pillGreen]}>
                <Txt variant="label" color={C.onPrimary} style={{ fontFamily: F.bold }}>
                  수락
                </Txt>
              </Pressable>
            ) : accept === 'accepted' ? (
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={`${p.vendorName} 수락 취소`}
                hitSlop={6}
                onPress={onCancelAccept}
                style={[s.pill, { backgroundColor: C.danger }]}>
                <Txt variant="label" color={C.onPrimary} style={{ fontFamily: F.bold }}>
                  수락 취소
                </Txt>
              </Pressable>
            ) : (
              <View />
            )}
            {chat && (
              <View style={s.chatHint}>
                <Txt variant="caption" color={C.primary}>
                  채팅으로 문의하기
                </Txt>
                <ChevronRight size={14} color={C.primary} strokeWidth={STROKE} />
              </View>
            )}
          </View>
        )}
      </Pressable>
    </Animated.View>
  );
}

/** 업체용: 제안서 작성 (업체 정보는 MY에서 자동으로, 가격 5~10만원, 추가 메모) */
function ProposalForm({ estimateId }: { estimateId: string }) {
  const { user, sendProposal } = useApp();
  const [price, setPrice] = useState(PRICES[0]);
  const [memo, setMemo] = useState('');
  if (!user) return null;

  return (
    <View style={s.proposal}>
      <Txt variant="label" color={C.primary}>
        제안서 작성
      </Txt>
      <View style={{ gap: 2 }}>
        <Txt variant="bodyStrong">{user.nickname}</Txt>
        <Txt variant="caption" muted>
          {[user.region, user.intro].filter(Boolean).join(' · ')}
        </Txt>
      </View>
      <Txt variant="label" muted>
        가격
      </Txt>
      <View style={s.prices}>
        {PRICES.map((n) => {
          const on = n === price;
          return (
            <Pressable
              key={n}
              accessibilityRole="radio"
              accessibilityState={{ selected: on }}
              accessibilityLabel={`${n}만원`}
              onPress={() => setPrice(n)}
              style={[s.price, on && s.priceOn]}>
              <Txt variant="label" color={on ? C.onPrimary : C.text} style={{ fontFamily: F.bold }}>
                {n}만원
              </Txt>
            </Pressable>
          );
        })}
      </View>
      <Field
        label="추가 메모"
        value={memo}
        onChangeText={setMemo}
        placeholder="예: 이번 주 토요일 방문 가능합니다"
        multiline
        style={{ minHeight: 76, paddingTop: 14, textAlignVertical: 'top' }}
      />
      <Button title="제안서 보내기" icon={Send} onPress={() => sendProposal(estimateId, price, memo.trim())} />
    </View>
  );
}

const s = StyleSheet.create({
  tabs: { flexDirection: 'row', backgroundColor: C.card, borderRadius: 999, padding: 5, gap: 4 },
  tab: { flex: 1, minHeight: 42, borderRadius: 999, alignItems: 'center', justifyContent: 'center' },
  tabOn: { backgroundColor: C.primary },
  row: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 14 },
  divider: { borderTopWidth: 1, borderTopColor: C.border },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: C.accent,
    alignItems: 'center',
    justifyContent: 'center',
  },
  unread: { width: 9, height: 9, borderRadius: 5, backgroundColor: C.primary },
  quote: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  quotePhoto: { width: 76, height: 76, borderRadius: 20, backgroundColor: C.accent },
  proposal: { backgroundColor: C.accentSoft, borderRadius: 22, padding: 16, gap: 10 },
  chatHint: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  boxFoot: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  proposalAccepted: { borderWidth: 2, borderColor: C.primary },
  ask: { backgroundColor: C.card, borderRadius: 16, padding: 12, gap: 10 },
  pill: { minHeight: 34, paddingHorizontal: 16, borderRadius: 999, alignItems: 'center', justifyContent: 'center' },
  pillGreen: { backgroundColor: C.primary },
  pillGhost: { backgroundColor: C.accentSoft },
  prices: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  price: {
    paddingHorizontal: 14,
    minHeight: 38,
    borderRadius: 999,
    backgroundColor: C.card,
    alignItems: 'center',
    justifyContent: 'center',
  },
  priceOn: { backgroundColor: C.primary },
});
