import { Stack, useLocalSearchParams } from 'expo-router';
import { ArrowUp, MessagesSquare } from 'lucide-react-native';
import { useRef, useState } from 'react';
import { FlatList, KeyboardAvoidingView, Platform, Pressable, StyleSheet, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Txt } from '@/components/ui';
import { C, F, MAX_W, STROKE } from '@/constants/theme';
import { getVendor } from '@/data/vendors';
import { useApp } from '@/store/app-store';

/** 업체와의 1:1 대화 (가상 업체 자동 응답) */
export default function ChatScreen() {
  const { vendorId, analysisId, name } = useLocalSearchParams<{ vendorId: string; analysisId?: string; name?: string }>();
  const { messages, analyses, sendMessage } = useApp();
  // 목록에 있는 가상 업체가 아니면(제안서를 보낸 업체 회원) 넘겨받은 이름으로 대화방을 엽니다.
  const vendor = getVendor(vendorId) ?? (name ? { id: vendorId, name } : undefined);
  const analysis = analyses.find((a) => a.id === analysisId);

  // 분석 결과에서 들어오면 견적서 내용을 미리 채워 둡니다.
  const [text, setText] = useState(
    analysis
      ? `[견적서]\n하자: ${analysis.defect}\nAI 위험도: ${analysis.risk}%\n장소: ${analysis.location}\n위치: ${analysis.position}\n\n위 내용으로 견적 부탁드립니다.`
      : '',
  );
  const listRef = useRef<FlatList>(null);
  const thread = messages.filter((m) => m.vendorId === vendorId);

  if (!vendor) {
    return (
      <View style={{ flex: 1, backgroundColor: C.bg, padding: 24 }}>
        <Txt variant="h2">업체를 찾을 수 없습니다.</Txt>
      </View>
    );
  }

  const onSend = () => {
    const t = text.trim();
    if (!t) return;
    sendMessage(vendor.id, t);
    setText('');
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
                {vendor.name}에 문의를 남겨 보세요.{'\n'}가상 업체가 자동으로 답변합니다.
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
