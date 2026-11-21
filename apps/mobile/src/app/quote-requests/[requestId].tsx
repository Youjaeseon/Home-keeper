import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import {
  type Profile,
  type QuoteRequestDetail,
  acceptQuoteProposal,
  cancelQuoteRequest,
  createChatRoom,
  getMyProfile,
  getQuoteRequestDetail,
  messageOf,
  submitQuoteProposal,
} from '@/lib/api';

const STATUS_LABELS = {
  open: '진행 중',
  accepted: '수락 완료',
  cancelled: '취소됨',
} as const;

const PROPOSAL_LABELS = {
  pending: '대기 중',
  accepted: '수락됨',
  rejected: '마감됨',
} as const;

function won(value: number): string {
  return `${value.toLocaleString('ko-KR')}원`;
}

export default function QuoteRequestDetailScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ requestId?: string | string[] }>();
  const requestId = Array.isArray(params.requestId)
    ? params.requestId[0]
    : params.requestId;
  const [detail, setDetail] = useState<QuoteRequestDetail | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [minPrice, setMinPrice] = useState('');
  const [maxPrice, setMaxPrice] = useState('');
  const [memo, setMemo] = useState('');

  useEffect(() => {
    let active = true;
    if (!requestId) {
      setError('견적 요청서 ID가 없어요.');
      setLoading(false);
      return () => {
        active = false;
      };
    }
    setLoading(true);
    setError(null);
    Promise.all([getQuoteRequestDetail(requestId), getMyProfile()])
      .then(([nextDetail, nextProfile]) => {
        if (!active) return;
        setDetail(nextDetail);
        setProfile(nextProfile);
      })
      .catch((loadError) => {
        if (active) setError(messageOf(loadError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [requestId]);

  async function openChat(providerId: string) {
    if (!detail || busy) return;
    setBusy(true);
    setError(null);
    try {
      const room = await createChatRoom({
        provider_id: providerId,
        record_id: detail.record_id,
      });
      Alert.alert('채팅방 준비 완료', `채팅방(${room.room_id.slice(0, 8)}…)이 열렸어요.`);
    } catch (chatError) {
      setError(messageOf(chatError));
    } finally {
      setBusy(false);
    }
  }

  function confirmAccept(proposalId: string) {
    Alert.alert(
      '제안서 수락',
      '이 제안서를 수락하면 나머지 제안서는 자동으로 마감돼요.',
      [
        { text: '취소', style: 'cancel' },
        {
          text: '수락',
          onPress: async () => {
            if (!requestId || busy) return;
            setBusy(true);
            setError(null);
            try {
              setDetail(await acceptQuoteProposal(requestId, proposalId));
            } catch (acceptError) {
              setError(messageOf(acceptError));
            } finally {
              setBusy(false);
            }
          },
        },
      ],
    );
  }

  function confirmCancel() {
    Alert.alert('요청서 취소', '대기 중인 제안서도 모두 마감돼요.', [
      { text: '취소', style: 'cancel' },
      {
        text: '요청서 취소',
        style: 'destructive',
        onPress: async () => {
          if (!requestId || busy) return;
          setBusy(true);
          setError(null);
          try {
            setDetail(await cancelQuoteRequest(requestId));
          } catch (cancelError) {
            setError(messageOf(cancelError));
          } finally {
            setBusy(false);
          }
        },
      },
    ]);
  }

  async function submitProposal() {
    if (!requestId || busy) return;
    const min = Number(minPrice);
    const max = Number(maxPrice);
    if (!Number.isInteger(min) || !Number.isInteger(max) || min < 0) {
      setError('금액은 0원 이상의 정수로 입력해 주세요.');
      return;
    }
    if (max < min) {
      setError('최대 금액은 최소 금액 이상이어야 해요.');
      return;
    }
    if (!memo.trim()) {
      setError('제안 메모를 입력해 주세요.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await submitQuoteProposal(requestId, {
        min_price: min,
        max_price: max,
        memo: memo.trim(),
      });
      setDetail(await getQuoteRequestDetail(requestId));
    } catch (proposalError) {
      setError(messageOf(proposalError));
    } finally {
      setBusy(false);
    }
  }

  const isRequester = profile?.role !== 'provider';
  const ownProposal = !isRequester ? detail?.proposals[0] ?? null : null;

  return (
    <SafeAreaView style={styles.screen}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.headerRow}>
          <View style={styles.headerText}>
            <Text style={styles.title}>견적 요청서</Text>
            <Text style={styles.subtitle}>{detail?.region_name ?? ''}</Text>
          </View>
          <Pressable
            accessibilityRole="button"
            onPress={() => router.back()}
            style={styles.textButton}
          >
            <Text style={styles.textButtonLabel}>뒤로</Text>
          </Pressable>
        </View>

        {loading ? (
          <View style={styles.center}>
            <ActivityIndicator />
            <Text style={styles.help}>요청서를 불러오는 중…</Text>
          </View>
        ) : error && !detail ? (
          <View style={styles.card}>
            <Text style={styles.error}>{error}</Text>
          </View>
        ) : detail ? (
          <>
            <View style={styles.card}>
              <View style={styles.statusRow}>
                <Text style={styles.cardTitle}>{detail.work_type_name}</Text>
                <View
                  style={[
                    styles.badge,
                    detail.status === 'open'
                      ? styles.badgeOpen
                      : detail.status === 'accepted'
                        ? styles.badgeAccepted
                        : styles.badgeClosed,
                  ]}
                >
                  <Text style={styles.badgeText}>{STATUS_LABELS[detail.status]}</Text>
                </View>
              </View>
              <Text style={styles.meta}>
                {detail.region_name}
                {detail.address ? ` · ${detail.address}` : ''}
              </Text>
              <Text style={styles.meta}>
                위치 {detail.location}
                {detail.material ? ` · 재질 ${detail.material}` : ''}
              </Text>
              <Text style={styles.meta}>
                AI 위험도{' '}
                {detail.severity_score === null
                  ? '판단 보류'
                  : `${detail.severity_score}% (${detail.severity_level ?? '미확인'})`}
              </Text>
              <Text style={styles.meta}>
                의심 유형 {detail.suspected_types.join(', ') || '미확인'}
              </Text>
              {detail.memo ? (
                <Text style={styles.bodyText}>{detail.memo}</Text>
              ) : null}
            </View>

            {detail.photos.length ? (
              <View style={styles.card}>
                <Text style={styles.cardTitle}>하자 사진</Text>
                <View style={styles.photoRow}>
                  {detail.photos.map((photo) => (
                    <Image
                      key={`${photo.role}-${photo.url}`}
                      source={{ uri: photo.url }}
                      style={styles.photo}
                      accessibilityLabel={
                        photo.role === 'overview' ? '전체 하자 사진' : '근접 하자 사진'
                      }
                    />
                  ))}
                </View>
              </View>
            ) : null}

            {isRequester ? (
              <>
                <View style={styles.card}>
                  <Text style={styles.cardTitle}>
                    도착한 제안서 {detail.proposals.length}
                  </Text>
                  {detail.proposals.length === 0 ? (
                    <Text style={styles.help}>아직 도착한 제안서가 없어요.</Text>
                  ) : (
                    detail.proposals.map((proposal) => (
                      <View key={proposal.proposal_id} style={styles.proposalCard}>
                        <View style={styles.statusRow}>
                          <Text style={styles.providerName}>
                            {proposal.provider.name}
                          </Text>
                          <Text style={styles.rating}>
                            ★ {proposal.provider.rating.toFixed(1)} (
                            {proposal.provider.review_count})
                          </Text>
                        </View>
                        <Text style={styles.price}>
                          {won(proposal.min_price)} ~ {won(proposal.max_price)}
                        </Text>
                        <Text style={styles.meta}>
                          {new Date(proposal.created_at).toLocaleDateString('ko-KR')} ·{' '}
                          {PROPOSAL_LABELS[proposal.status]}
                        </Text>
                        <Text style={styles.bodyText}>{proposal.memo}</Text>
                        <View style={styles.actions}>
                          <Pressable
                            accessibilityRole="button"
                            disabled={busy}
                            onPress={() => openChat(proposal.provider.provider_id)}
                            style={({ pressed }) => [
                              styles.secondaryButton,
                              pressed && styles.pressed,
                            ]}
                          >
                            <Text style={styles.secondaryButtonText}>채팅하기</Text>
                          </Pressable>
                          {detail.status === 'open' &&
                          proposal.status === 'pending' ? (
                            <Pressable
                              accessibilityRole="button"
                              disabled={busy}
                              onPress={() => confirmAccept(proposal.proposal_id)}
                              style={({ pressed }) => [
                                styles.primaryButton,
                                pressed && styles.pressed,
                              ]}
                            >
                              <Text style={styles.primaryButtonText}>수락하기</Text>
                            </Pressable>
                          ) : null}
                        </View>
                      </View>
                    ))
                  )}
                </View>

                {detail.status === 'open' ? (
                  <Pressable
                    accessibilityRole="button"
                    disabled={busy}
                    onPress={confirmCancel}
                    style={({ pressed }) => [
                      styles.dangerButton,
                      pressed && styles.pressed,
                    ]}
                  >
                    <Text style={styles.dangerButtonText}>요청서 취소</Text>
                  </Pressable>
                ) : null}
              </>
            ) : (
              <>
                <View style={styles.card}>
                  <Text style={styles.cardTitle}>내 제안서</Text>
                  {ownProposal ? (
                    <>
                      <Text style={styles.price}>
                        {won(ownProposal.min_price)} ~ {won(ownProposal.max_price)}
                      </Text>
                      <Text style={styles.meta}>
                        {PROPOSAL_LABELS[ownProposal.status]}
                      </Text>
                      <Text style={styles.bodyText}>{ownProposal.memo}</Text>
                    </>
                  ) : detail.status === 'open' ? (
                    <>
                      <Text style={styles.help}>
                        사진과 위험도를 확인하고 제안서를 보내 주세요.
                      </Text>
                      <Text style={styles.label}>최소 금액(원)</Text>
                      <TextInput
                        value={minPrice}
                        onChangeText={setMinPrice}
                        keyboardType="number-pad"
                        style={styles.input}
                        placeholder="예: 150000"
                        placeholderTextColor="#8A8F98"
                      />
                      <Text style={styles.label}>최대 금액(원)</Text>
                      <TextInput
                        value={maxPrice}
                        onChangeText={setMaxPrice}
                        keyboardType="number-pad"
                        style={styles.input}
                        placeholder="예: 300000"
                        placeholderTextColor="#8A8F98"
                      />
                      <Text style={styles.label}>제안 메모</Text>
                      <TextInput
                        value={memo}
                        onChangeText={setMemo}
                        multiline
                        style={[styles.input, styles.multiline]}
                        placeholder="작업 범위와 일정을 적어 주세요."
                        placeholderTextColor="#8A8F98"
                      />
                      <Pressable
                        accessibilityRole="button"
                        disabled={busy}
                        onPress={submitProposal}
                        style={({ pressed }) => [
                          styles.primaryButton,
                          pressed && styles.pressed,
                        ]}
                      >
                        {busy ? (
                          <ActivityIndicator color="#FFFFFF" />
                        ) : (
                          <Text style={styles.primaryButtonText}>제안서 보내기</Text>
                        )}
                      </Pressable>
                    </>
                  ) : (
                    <Text style={styles.help}>제안할 수 없는 요청서예요.</Text>
                  )}
                </View>
              </>
            )}

            {error ? <Text style={styles.error}>{error}</Text> : null}
          </>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#F7F7F8' },
  content: {
    flexGrow: 1,
    gap: 12,
    padding: 24,
    width: '100%',
    maxWidth: 560,
    alignSelf: 'center',
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 12,
  },
  headerText: { flex: 1, gap: 4 },
  title: { fontSize: 28, fontWeight: '700', color: '#15171A' },
  subtitle: { fontSize: 15, color: '#60646C' },
  textButton: { paddingVertical: 6, paddingHorizontal: 4 },
  textButtonLabel: { fontSize: 14, fontWeight: '600', color: '#208AEF' },
  center: { alignItems: 'center', gap: 8, paddingVertical: 24 },
  card: {
    borderRadius: 12,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E2E4E8',
    padding: 16,
    gap: 8,
  },
  cardTitle: { fontSize: 18, fontWeight: '700', color: '#15171A' },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
  badge: { borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 },
  badgeOpen: { backgroundColor: '#EAF4FE' },
  badgeAccepted: { backgroundColor: '#E8F6EC' },
  badgeClosed: { backgroundColor: '#EEF0F3' },
  badgeText: { fontSize: 12, fontWeight: '700', color: '#4E535C' },
  meta: { fontSize: 13, color: '#60646C' },
  bodyText: { fontSize: 15, lineHeight: 22, color: '#4E535C' },
  help: { fontSize: 13, lineHeight: 19, color: '#60646C' },
  label: { marginTop: 4, fontSize: 14, fontWeight: '600', color: '#15171A' },
  input: {
    borderWidth: 1,
    borderColor: '#D7D9DE',
    borderRadius: 10,
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 12,
    paddingVertical: 12,
    fontSize: 16,
    color: '#15171A',
  },
  multiline: { minHeight: 100, textAlignVertical: 'top' },
  proposalCard: {
    borderTopWidth: 1,
    borderTopColor: '#E2E4E8',
    paddingTop: 10,
    gap: 6,
  },
  providerName: { flex: 1, fontSize: 16, fontWeight: '700', color: '#15171A' },
  rating: { fontSize: 13, fontWeight: '700', color: '#B36B00' },
  price: { fontSize: 18, fontWeight: '800', color: '#15171A' },
  actions: { flexDirection: 'row', gap: 8, marginTop: 4 },
  primaryButton: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 10,
    backgroundColor: '#208AEF',
    minHeight: 46,
    paddingHorizontal: 14,
  },
  primaryButtonText: { fontSize: 15, fontWeight: '700', color: '#FFFFFF' },
  secondaryButton: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#208AEF',
    backgroundColor: '#FFFFFF',
    minHeight: 46,
    paddingHorizontal: 14,
  },
  secondaryButtonText: { fontSize: 15, fontWeight: '700', color: '#208AEF' },
  dangerButton: {
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#C0392B',
    minHeight: 46,
  },
  dangerButtonText: { fontSize: 15, fontWeight: '700', color: '#C0392B' },
  photoRow: { flexDirection: 'row', gap: 8 },
  photo: {
    flex: 1,
    aspectRatio: 1,
    borderRadius: 10,
    backgroundColor: '#EEF0F3',
  },
  pressed: { opacity: 0.75 },
  error: { fontSize: 14, lineHeight: 20, color: '#C0392B' },
});
