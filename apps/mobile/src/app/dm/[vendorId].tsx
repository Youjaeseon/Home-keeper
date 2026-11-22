import { Stack, useLocalSearchParams } from 'expo-router';
import { ArrowUp, MessagesSquare } from 'lucide-react-native';
import { useEffect, useRef, useState } from 'react';
import { FlatList, KeyboardAvoidingView, Platform, Pressable, StyleSheet, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Txt } from '@/components/ui';
import { C, F, MAX_W, STROKE } from '@/constants/theme';
import { useApp } from '@/store/app-store';

/** 업체와의 1:1 실시간 채팅 (POST /chat/rooms, GET/POST /chat/rooms/{id}/messages, WebSocket /chat/ws) */
export default function ChatScreen() {
  const { vendorId, analysisId, name, roomId: roomParam } = useLocalSearchParams<{
    vendorId: string;
    analysisId?: string;
    name?: string;
    roomId?: string;
  }>();
  const { messages, analyses, threads, openRoom, loadMessages, sendMessage } = useApp();
  const [roomId, setRoomId] = useState<string | null>(roomParam ?? null);
  const [error, setError] = useState<string | null>(null);
  const vendorName = name ?? threads.find((t) => t.vendorId === vendorId)?.name;
  const vendor = vendorId ? { id: vendorId, name: vendorName ?? '대화' } : undefined;
  const analysis = analyses.find((a) => a.id === analysisId);

  // 방을 열고(분석 결과에서 왔으면 기록 요약을 함께 공유) 이력을 불러옵니다.
  useEffect(() => {
    if (!vendorId) return;
    let alive = true;
    openRoom({ vendorId, roomId: roomParam, analysisId }).then(async (res) => {
      if (!alive) return;
      if (res.error || !res.roomId) {
        setError(res.error ?? '채팅방을 열지 못했습니다.');
        return;
      }
      setRoomId(res.roomId);
      const err = await loadMessages(res.roomId);
      if (alive) setError(err);
    });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vendorId, roomParam, analysisId]);

  // 분석 결과에서 들어오면 견적서 내용을 미리 채워 둡니다.
  const [text, setText] = useState(
    analysis
      ? `[견적서]\n하자: ${analysis.defect}\nAI 위험도: ${analysis.risk}%\n장소: ${analysis.location}\n위치: ${analysis.position}\n\n위 내용으로 견적 부탁드립니다.`
      : '',
  );
  const listRef = useRef<FlatList>(null);
  const thread = messages.filter((m) => m.roomId === roomId);

  if (!vendor) {
    return (
      <View style={{ flex: 1, backgroundColor: C.bg, padding: 24 }}>
        <Txt variant="h2">업체를 찾을 수 없습니다.</Txt>
      </View>
    );
  }

  const onSend = async () => {
    const t = text.trim();
    if (!t || !roomId) return;
    setText('');
    const err = await sendMessage(roomId, vendor.id, t);
    if (err) {
      setError(err);
      setText(t);
    } else setError(null);
  };

  return (
    <SafeAreaView edges={['bottom']} style={{ flex: 1, backgroundColor: C.bg }}>
      <Stack.Screen options={{ title: vendor.name }} />
      <KeyboardAvoidingView
        style={s.container}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={100}>
        <FlatList
          ref={listRef}
          data={thread}
          keyExtractor={(m) => m.id}
          contentContainerStyle={{ padding: 24, gap: 10, flexGrow: 1 }}
          onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
          ListEmptyComponent={
            <View style={s.empty}>
              <View style={s.emptyIcon}>
                <MessagesSquare size={28} color={C.text} strokeWidth={STROKE} />
              </View>
              <Txt variant="sub" muted style={{ textAlign: 'center' }}>
                {error ?? `${vendor.name}에 문의를 남겨 보세요.`}
              </Txt>
            </View>
          }
          renderItem={({ item }) => {
            const mine = item.from === 'me';
            return (
              <View style={[s.bubble, mine ? s.mine : s.theirs]}>
                <Txt variant="body" color={mine ? C.onPrimary : C.text}>
                  {item.text}
                </Txt>
              </View>
            );
          }}
        />
        {error && thread.length > 0 && (
          <Txt variant="caption" color={C.danger} style={{ marginHorizontal: 24 }}>
            {error}
          </Txt>
        )}
        <View style={s.inputRow}>
          <TextInput
            value={text}
            onChangeText={setText}
            placeholder="메시지 입력"
            placeholderTextColor={C.faint}
            multiline
            style={s.input}
          />
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="보내기"
            onPress={onSend}
            style={({ pressed }) => [s.send, pressed && { opacity: 0.8 }]}>
            <ArrowUp size={21} color={C.onPrimary} strokeWidth={2.6} />
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, width: '100%', maxWidth: MAX_W, alignSelf: 'center' },
  empty: { alignItems: 'center', gap: 14, marginTop: 64 },
  emptyIcon: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: C.accent,
    alignItems: 'center',
    justifyContent: 'center',
  },
  bubble: { maxWidth: '80%', paddingHorizontal: 16, paddingVertical: 12, borderRadius: 22 },
  mine: { alignSelf: 'flex-end', backgroundColor: C.primary, borderBottomRightRadius: 8 },
  theirs: { alignSelf: 'flex-start', backgroundColor: C.card, borderBottomLeftRadius: 8 },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 10,
    margin: 16,
    padding: 6,
    paddingLeft: 18,
    borderRadius: 999,
    backgroundColor: C.card,
  },
  input: {
    flex: 1,
    minHeight: 44,
    maxHeight: 120,
    paddingTop: 12,
    fontSize: 15,
    fontFamily: F.medium,
    color: C.text,
  },
  send: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: C.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
