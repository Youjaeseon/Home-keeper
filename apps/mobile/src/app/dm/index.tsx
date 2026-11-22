import { Image } from 'expo-image';
import { router, useLocalSearchParams } from 'expo-router';
import { ChevronRight, Send } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Animated, Pressable, StyleSheet, View } from 'react-native';

import { Button, Card, Chip, DeleteButton, Field, Hero, Screen, Txt } from '@/components/ui';
import { C, F, STROKE } from '@/constants/theme';
import { useApp } from '@/store/app-store';
import type { Estimate, Proposal } from '@/types';
import { showAlert } from '@/lib/alert';

type Tab = 'messages' | 'quotes';
/** 제안 금액 표시·입력 (원 단위) */
const won = (n: number) => `${n.toLocaleString('ko-KR')}원`;
/** 숫자만 남겨 원 단위 정수로 읽습니다. 비어 있으면 null. */
const parseWon = (text: string) => {
  const digits = text.replace(/[^0-9]/g, '');
  return digits ? Number(digits) : null;
};

/** 채팅 목록 — 상단 탭: 메시지 | 업체 제안서(유저) 또는 견적 요청서(업체) */
export default function DmListScreen() {
  const params = useLocalSearchParams<{ tab?: string }>();
  const { user } = useApp();
  const [tab, setTab] = useState<Tab>(params.tab === 'quotes' ? 'quotes' : 'messages');
  const TABS: { key: Tab; label: string }[] = [
    { key: 'messages', label: '메시지' },
    { key: 'quotes', label: user?.role === '업체' ? '견적 요청서' : '업체 제안서' },
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

/** 메시지 탭: GET /chat/rooms (상대 이름, 최근 메시지, 미읽음 수) */
function Messages() {
  const { threads, refreshThreads, user } = useApp();
  useEffect(() => {
    void refreshThreads().catch(() => null);
  }, [refreshThreads]);
  return (
    <>
      <Hero
        title="메시지"
        subtitle={user?.role === '업체' ? '요청인과 나눈 대화를 모아 볼 수 있어요.' : '업체와 나눈 대화를 모아 볼 수 있어요.'}
      />
      <Card style={{ padding: 8, gap: 0 }}>
        {threads.length === 0 && (
          <Txt variant="sub" muted style={{ padding: 14 }}>
            아직 대화가 없어요. 업체 목록이나 분석 결과에서 업체에 문의해 보세요.
          </Txt>
        )}
        {threads.map((t, i) => {
          return (
            <Pressable
              key={t.roomId}
              accessibilityRole="button"
              accessibilityLabel={`${t.name} 대화 열기`}
              onPress={() =>
                router.push({ pathname: '/dm/[vendorId]', params: { vendorId: t.vendorId, roomId: t.roomId, name: t.name } })
              }
              style={({ pressed }) => [s.row, i > 0 && s.divider, pressed && { opacity: 0.7 }]}>
              <View style={s.avatar}>
                <Txt variant="h2">{t.name.slice(0, 1)}</Txt>
              </View>
              <View style={{ flex: 1, gap: 2 }}>
                <Txt variant="bodyStrong">{t.name}</Txt>
                <Txt variant="sub" muted numberOfLines={1}>
                  {t.last ?? '아직 대화가 없어요'}
                </Txt>
              </View>
              {t.unread > 0 ? (
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

/** 유저: 받은 업체 제안서 (견적 요청서별로 묶음) / 업체: 받은 견적 요청서와 보낸 업체 제안서. (GET /quote-requests, GET /quote-requests/{id}) */
function Quotes() {
  const {
    user,
    session,
    estimates,
    proposals,
    hidden,
    refreshQuotes,
    removeEstimate,
    removeProposal,
    accepted,
    acceptProposal,
  } = useApp();
  useEffect(() => {
    void refreshQuotes().catch(() => null);
  }, [refreshQuotes]);
  if (!user) return null;
  const me = session?.user.id ?? '';
  const vendor = user.role === '업체';
  const own = vendor ? estimates.filter((e) => e.userId !== me) : estimates.filter((e) => e.userId === me);
  const list = own.filter((e) => !hidden.includes(e.id) && e.status !== 'cancelled');
  const all = proposals.filter((p) => !hidden.includes(p.id));
  const alertIf = (err: string | null) => err && showAlert('처리하지 못했습니다', err);

  return (
    <>
      <Hero
        title={vendor ? '받은 견적 요청서' : '받은 업체 제안서'}
        subtitle={vendor ? '견적 요청서를 확인하고 업체 제안서를 보내 보세요.' : '받은 업체 제안서를 비교해 보세요.'}
      />
      {!vendor && own.length === 0 && (
        <Txt variant="sub" muted>
          분석 결과 화면에서 견적 요청서를 보내면 여기에 업체 제안서가 도착해요.
        </Txt>
      )}
      {list.map((e) => {
        const mine = proposals.find((p) => p.estimateId === e.id && p.vendorId === me);
        const related = all.filter((p) => p.estimateId === e.id).sort((a, b) => a.price - b.price);
        return (
          <Card key={e.id}>
            <EstimateSummary e={e} showSender={vendor} onDelete={() => void removeEstimate(e.id).then(alertIf)} />
            {vendor ? (
              mine ? (
                <ProposalBox p={mine} title="보낸 업체 제안서" onDelete={() => removeProposal(mine.id)} />
              ) : (
                <ProposalForm estimateId={e.id} />
              )
            ) : related.length === 0 ? (
              <Txt variant="sub" muted>
                아직 받은 업체 제안서가 없어요.
              </Txt>
            ) : (
              <>
                <Txt variant="label" muted>
                  업체 제안서 {related.length}건
                </Txt>
                {related.map((p) => (
                  <ProposalBox
                    key={p.id}
                    p={p}
                    chat
                    onDelete={() => removeProposal(p.id)}
                    accept={!accepted[e.id] ? 'open' : accepted[e.id] === p.id ? 'accepted' : 'closed'}
                    onAccept={() => void acceptProposal(e.id, p.id).then(alertIf)}
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
            <Chip label={`심각도 ${e.risk}%`} />
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
          <DeleteButton label="견적 요청서" onDelete={onDelete} />
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
}: {
  p: Proposal;
  title?: string;
  chat?: boolean;
  onDelete: () => void;
  /** 유저가 받은 업체 제안서일 때: 수락 전 / 이 업체 제안서를 수락함 / 다른 업체 제안서를 수락해서 마감됨 */
  accept?: AcceptState;
  onAccept?: () => void;
}) {
  const [asking, setAsking] = useState(false);
  const closed = accept === 'closed';
  // 다른 업체 제안서를 수락하면 서서히 흐려집니다.
  const [fade] = useState(() => new Animated.Value(closed ? 0.3 : 1));
  useEffect(() => {
    Animated.timing(fade, { toValue: closed ? 0.3 : 1, duration: 450, useNativeDriver: true }).start();
  }, [closed, fade]);

  // 받은 업체 제안서를 누르면 그 업체와의 채팅으로 이동합니다(수락 전에도 POST /chat/rooms로 채팅 가능).
  const openChat = () => {
    router.push({ pathname: '/dm/[vendorId]', params: { vendorId: p.vendorId, name: p.vendorName } });
  };
  return (
    <Animated.View style={{ opacity: fade }} pointerEvents={closed ? 'none' : 'auto'}>
      {/* 카드 안에 삭제·수락 버튼이 있어 카드 자체는 button 역할을 주지 않습니다(웹 중첩 <button> 방지).
          화면 읽기 사용자는 아래 '채팅으로 문의하기' 버튼을 씁니다. */}
      <Pressable
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
            {p.priceMax && p.priceMax !== p.price ? `${won(p.price)}~${won(p.priceMax)}` : won(p.price)}
          </Txt>
          <DeleteButton label="업체 제안서" onDelete={onDelete} />
        </View>
        {p.memo !== '' && (
          <Txt variant="sub" color={C.text}>
            {p.memo}
          </Txt>
        )}
        {asking && (
          <View style={s.ask}>
            <Txt variant="sub" color={C.text} style={{ fontFamily: F.semibold }}>
              수락하면 다른 업체 제안서는 받을 수 없어요.
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
              // 수락은 최종이라 취소할 수 없습니다(adr/0003, GAP-014). 상태만 표시합니다.
              <View accessibilityLabel={`${p.vendorName} 제안 수락됨`} style={[s.pill, s.pillGreen]}>
                <Txt variant="label" color={C.onPrimary} style={{ fontFamily: F.bold }}>
                  수락됨
                </Txt>
              </View>
            ) : (
              <View />
            )}
            {chat && (
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={`${p.vendorName}와 채팅하기`}
                hitSlop={6}
                onPress={openChat}
                style={s.chatHint}>
                <Txt variant="caption" color={C.primary}>
                  채팅으로 문의하기
                </Txt>
                <ChevronRight size={14} color={C.primary} strokeWidth={STROKE} />
              </Pressable>
            )}
          </View>
        )}
      </Pressable>
    </Animated.View>
  );
}

/** 업체용: 업체 제안서 작성 (업체 정보는 MY에서 자동으로, 원 단위 최소~최대 금액, 추가 메모) (GAP-023) */
function ProposalForm({ estimateId }: { estimateId: string }) {
  const { user, sendProposal } = useApp();
  const [minText, setMinText] = useState('');
  const [maxText, setMaxText] = useState('');
  const [memo, setMemo] = useState('');
  const [busy, setBusy] = useState(false);
  if (!user) return null;
  const onSend = async () => {
    const min = parseWon(minText);
    // 최대 금액을 비우면 단일 가격(최소 = 최대)으로 보냅니다.
    const max = parseWon(maxText) ?? min;
    if (min === null || max === null) {
      showAlert('금액을 입력해 주세요', '최소 금액은 꼭 입력해 주세요. 단일 가격이면 최대 금액은 비워 두세요.');
      return;
    }
    if (max < min) {
      showAlert('금액을 확인해 주세요', '최대 금액은 최소 금액보다 크거나 같아야 해요.');
      return;
    }
    setBusy(true);
    const err = await sendProposal(estimateId, min, max, memo.trim());
    setBusy(false);
    if (err) showAlert('업체 제안서를 보내지 못했습니다', err);
  };

  return (
    <View style={s.proposal}>
      <Txt variant="label" color={C.primary}>
        업체 제안서 작성
      </Txt>
      <View style={{ gap: 2 }}>
        <Txt variant="bodyStrong">{user.nickname}</Txt>
        <Txt variant="caption" muted>
          {[user.region, user.intro].filter(Boolean).join(' · ')}
        </Txt>
      </View>
      <View style={s.prices}>
        <View style={{ flex: 1 }}>
          <Field label="최소 금액(원)" value={minText} onChangeText={setMinText} keyboardType="number-pad" placeholder="예: 50000" />
        </View>
        <View style={{ flex: 1 }}>
          <Field label="최대 금액(원)" value={maxText} onChangeText={setMaxText} keyboardType="number-pad" placeholder="비우면 단일 가격" />
        </View>
      </View>
      <Field
        label="추가 메모"
        value={memo}
        onChangeText={setMemo}
        placeholder="예: 이번 주 토요일 방문 가능합니다"
        multiline
        style={{ minHeight: 76, paddingTop: 14, textAlignVertical: 'top' }}
      />
      <Button title="업체 제안서 보내기" icon={Send} onPress={onSend} loading={busy} />
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
  prices: { flexDirection: 'row', gap: 8 },
});
