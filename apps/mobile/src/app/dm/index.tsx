import { Image } from 'expo-image';
import { router, Stack, useLocalSearchParams } from 'expo-router';
import { ChevronLeft, ChevronRight, Send } from 'lucide-react-native';
import { useEffect, useRef, useState } from 'react';
import { Animated, Pressable, StyleSheet, View } from 'react-native';

import { Button, Card, Chip, DeleteButton, Field, Hero, Screen, Txt } from '@/components/ui';
import { C, F, STROKE } from '@/constants/theme';
import { useApp } from '@/store/app-store';
import type { Estimate, Proposal } from '@/types';
import { confirmAlert, showAlert } from '@/lib/alert';

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
    // 업체 회원에게는 같은 지역 유저들이 보낸 견적 요청서가 오는 칸입니다. (Hyeok 결정)
    { key: 'quotes', label: user?.role === '업체' ? '견적 요청서' : '업체 제안서' },
  ];

  // 채팅 탭(바로가기)이나 새로고침으로 들어오면 돌아갈 화면 기록이 없어 기본 뒤로 버튼이 사라집니다.
  // 그때만 같은 모양의 '뒤로' 버튼을 직접 달고, 누르면 소식지(홈)로 갑니다.
  const noHistory = !router.canGoBack();

  return (
    <Screen>
      {noHistory && (
        <Stack.Screen
          options={{
            headerLeft: () => (
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="뒤로"
                hitSlop={8}
                onPress={() => router.replace('/news')}
                style={({ pressed }) => [s.back, pressed && { opacity: 0.6 }]}>
                <ChevronLeft size={22} color={C.text} strokeWidth={STROKE} />
                <Txt variant="body">뒤로</Txt>
              </Pressable>
            ),
          }}
        />
      )}
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
                {/* '(가상) 클린홈'처럼 앞의 괄호 표시는 빼고 첫 글자를 씁니다. */}
                <Txt variant="h2">{t.name.replace(/^\(.*?\)\s*/, '').slice(0, 1)}</Txt>
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
    cancelAccept,
    completeDeal,
    openRoom,
    sendMessage,
  } = useApp();
  // 수락을 연달아 눌러도 수락·자동 메시지가 한 번만 나가게 합니다.
  const accepting = useRef(false);
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

  /**
   * 업체 제안서 수락 → 그 업체와의 채팅방을 열고(분석 기록 요약을 함께 공유)
   * 수락 안내와 견적서 요약을 바로 보낸 뒤 채팅 화면으로 이동합니다.
   * 자동 메시지가 실패해도 수락은 그대로 두고 채팅 화면만 엽니다.
   */
  const acceptAndChat = async (e: Estimate, p: Proposal) => {
    if (accepting.current) return;
    accepting.current = true;
    try {
      const err = await acceptProposal(e.id, p.id);
      if (err) {
        alertIf(err);
        return;
      }
      const price = p.priceMax && p.priceMax !== p.price ? `${won(p.price)}~${won(p.priceMax)}` : won(p.price);
      const text = [
        `[업체 제안서 수락] ${p.vendorName}님의 제안서를 수락했어요.`,
        '',
        '[견적 요청서]',
        `하자: ${e.defect}`,
        `장소·위치: ${[e.location, e.position].filter(Boolean).join(' · ')}`,
        `AI 심각도: ${e.risk}%`,
        `제안 금액: ${price}`,
        ...(e.memo ? [`요청 메모: ${e.memo}`] : []),
        '',
        '방문 일정 조율 부탁드립니다.',
      ].join('\n');
      const room = await openRoom({ vendorId: p.vendorId, analysisId: e.analysisId || undefined });
      if (room.roomId) await sendMessage(room.roomId, p.vendorId, text);
      router.push({
        pathname: '/dm/[vendorId]',
        params: { vendorId: p.vendorId, name: p.vendorName, ...(room.roomId ? { roomId: room.roomId } : {}) },
      });
    } finally {
      accepting.current = false;
    }
  };

  /** 거래 완료 → 되돌릴 수 없음을 확인한 뒤 완료로 마감하고 업체에게 알립니다. 알림 실패는 완료를 막지 않습니다. */
  const completeAndNotify = async (e: Estimate, p: Proposal) => {
    if (accepting.current) return;
    const ok = await confirmAlert(
      '거래를 완료할까요?',
      `${p.vendorName}님과의 거래를 완료 처리해요. 완료하면 되돌리거나 다시 수락할 수 없어요.`,
      '완료',
    );
    if (!ok) return;
    accepting.current = true;
    try {
      const err = await completeDeal(e.id);
      if (err) {
        alertIf(err);
        return;
      }
      const room = await openRoom({ vendorId: p.vendorId });
      if (room.roomId) {
        await sendMessage(
          room.roomId,
          p.vendorId,
          `[거래 완료] 고객이 ${e.defect} · ${[e.location, e.position].filter(Boolean).join(' · ')} 견적 거래를 완료 처리했어요. 감사합니다.`,
        );
      }
    } finally {
      accepting.current = false;
    }
  };

  /** 수락 취소 → 그 업체에게 고객이 수락을 취소했다고 알립니다. 알림이 실패해도 취소는 그대로 둡니다. */
  const cancelAndNotify = async (e: Estimate, p: Proposal) => {
    if (accepting.current) return;
    accepting.current = true;
    try {
      const err = await cancelAccept(e.id);
      if (err) {
        alertIf(err);
        return;
      }
      const room = await openRoom({ vendorId: p.vendorId });
      if (room.roomId) {
        await sendMessage(
          room.roomId,
          p.vendorId,
          `[업체 제안서 수락 취소] 고객이 ${e.defect} · ${[e.location, e.position].filter(Boolean).join(' · ')} 견적의 수락을 취소했어요.`,
        );
      }
    } finally {
      accepting.current = false;
    }
  };

  return (
    <>
      <Hero
        title={vendor ? '받은 견적 요청서' : '받은 업체 제안서'}
        subtitle={vendor ? '활동지역 유저들이 보낸 견적 요청서예요. 확인하고 업체 제안서를 보내 보세요.' : '받은 업체 제안서를 비교해 보세요.'}
      />
      {vendor && list.length === 0 && (
        <Txt variant="sub" muted>
          아직 받은 견적 요청서가 없어요. 활동지역의 유저가 분석 결과에서 견적 요청서를 보내면 여기에 도착해요.
        </Txt>
      )}
      {!vendor && own.length === 0 && (
        <Txt variant="sub" muted>
          분석 결과 화면에서 견적 요청서를 보내면 여기에 업체 제안서가 도착해요.
        </Txt>
      )}
      {list.map((e) => {
        const mine = proposals.find((p) => p.estimateId === e.id && p.vendorId === me);
        const related = all.filter((p) => p.estimateId === e.id).sort((a, b) => a.price - b.price);
        const done = e.status === 'completed';
        return (
          // 완료된 거래는 회색으로 흐리게 하고 누를 수 없게 합니다.
          <View key={e.id} style={done && s.done} pointerEvents={done ? 'none' : 'auto'}>
            <Card>
              {done && (
                <View style={s.doneBadge}>
                  <Txt variant="label" color={C.onPrimary} style={{ fontFamily: F.bold }}>
                    거래 완료
                  </Txt>
                </View>
              )}
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
                    chat={!done}
                    onDelete={() => removeProposal(p.id)}
                    accept={done ? undefined : !accepted[e.id] ? 'open' : accepted[e.id] === p.id ? 'accepted' : 'closed'}
                    onAccept={() => void acceptAndChat(e, p)}
                    onCancelAccept={() => void cancelAndNotify(e, p)}
                    onComplete={() => void completeAndNotify(e, p)}
                  />
                ))}
              </>
            )}
            </Card>
          </View>
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
  onCancelAccept,
  onComplete,
}: {
  p: Proposal;
  title?: string;
  chat?: boolean;
  onDelete: () => void;
  /** 유저가 받은 업체 제안서일 때: 수락 전 / 이 업체 제안서를 수락함 / 다른 업체 제안서를 수락해서 마감됨 */
  accept?: AcceptState;
  onAccept?: () => void;
  onCancelAccept?: () => void;
  onComplete?: () => void;
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
        {/* 금액 범위가 길면 업체명이 한 글자 폭으로 눌리므로, 금액은 업체 정보 아래 줄에 둡니다. */}
        <View style={{ flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10 }}>
          <View style={{ flex: 1, gap: 2 }}>
            {!!p.vendorName && <Txt variant="bodyStrong">{p.vendorName}</Txt>}
            {(!!p.vendorRegion || !!p.vendorIntro) && (
              <Txt variant="caption" muted>
                {[p.vendorRegion, p.vendorIntro].filter(Boolean).join(' · ')}
              </Txt>
            )}
            <Txt variant="title" color={C.primary}>
              {p.priceMax && p.priceMax !== p.price ? `${won(p.price)}~${won(p.priceMax)}` : won(p.price)}
            </Txt>
          </View>
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
              // 수락 취소: 요청서를 다시 열어 다른 업체 제안서를 수락할 수 있습니다. (GAP-014)
              <View style={{ flexDirection: 'row', gap: 8 }}>
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
                {onComplete && (
                  <Pressable
                    accessibilityRole="button"
                    accessibilityLabel={`${p.vendorName} 거래 완료`}
                    hitSlop={6}
                    onPress={onComplete}
                    style={[s.pill, s.pillGreen]}>
                    <Txt variant="label" color={C.onPrimary} style={{ fontFamily: F.bold }}>
                      완료
                    </Txt>
                  </Pressable>
                )}
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
  back: { flexDirection: 'row', alignItems: 'center', gap: 2, paddingHorizontal: 8, paddingVertical: 6 },
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
  done: { opacity: 0.45 },
  doneBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 999,
    backgroundColor: C.sub,
  },
  ask: { backgroundColor: C.card, borderRadius: 16, padding: 12, gap: 10 },
  pill: { minHeight: 34, paddingHorizontal: 16, borderRadius: 999, alignItems: 'center', justifyContent: 'center' },
  pillGreen: { backgroundColor: C.primary },
  pillGhost: { backgroundColor: C.accentSoft },
  prices: { flexDirection: 'row', gap: 8 },
});
