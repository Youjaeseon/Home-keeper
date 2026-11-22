import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, TextInput, useWindowDimensions, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { LogoMark } from '@/components/logo';
import { Txt } from '@/components/ui';
import { C, F, MAX_W } from '@/constants/theme';
import { useApp } from '@/store/app-store';

/* ═══════════════════════════════════════════════════════════
 *  ✏️ 직접 수정하는 곳 — 값을 바꾸고 저장(Cmd+S)하면 화면에 바로 반영됩니다.
 * ═══════════════════════════════════════════════════════════ */
const LOGIN_DESIGN = {
  /** 로고 위치: 화면 높이 비율 (0 = 맨 위, 0.5 = 가운데) */
  logoTop: 0.07,
  /** 로고 크기 (px). 화면이 작은 폰에서는 입력칸과 겹치지 않게 자동으로 줄어듭니다. */
  logoSize: 148,

  /** 로고 아래 한 줄 문구 ('' 로 두면 표시 안 함) */
  tagline: '우리집 관리사',

  /** 입력칸·로그인 버튼 묶음을 화면 아래에서 얼마나 띄울지 (px). 작은 폰에서는 겹치지 않게 자동으로 줄어듭니다. */
  formBottom: 220,
};
/* ═══════════════════════════════════════════════════════════ */

/** 스케치 1: 로그인 — 크림 단색 배경 + 로고 + 흰 둥근 입력칸 + 글씨 버튼 */
export default function LoginScreen() {
  const { login, loginAsGuest } = useApp();
  const { height } = useWindowDimensions();
  const [loginId, setLoginId] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const d = LOGIN_DESIGN;

  const onLogin = () => {
    if (!loginId.trim() || !password) {
      setError('ID와 PW를 입력해 주세요.');
      return;
    }
    const err = login(loginId.trim(), password);
    setError(err);
    if (!err) router.replace('/news');
  };

  return (
    <View style={s.root}>
      <SafeAreaView style={s.safe}>
        <View style={[s.logo, { marginTop: height * d.logoTop }]}>
          <LogoMark size={Math.min(d.logoSize, height * 0.17)} radius={0.24} />
          {d.tagline !== '' && (
            <Txt style={[s.taglineChar, { marginTop: 14 }]}>
              {/* '집'과 '사'만 로고 캐릭터의 초록색으로 */}
              {[...d.tagline].map((ch, i) => (
                <Txt key={i} style={s.taglineChar} color={ch === '집' || ch === '사' ? C.primary : C.text}>
                  {ch}
                </Txt>
              ))}
            </Txt>
          )}
        </View>

        <View style={s.spacer} />
        <View style={s.form}>
          <LineField label="ID" value={loginId} onChangeText={setLoginId} autoCapitalize="none" />
          <LineField label="PW" value={password} onChangeText={setPassword} secureTextEntry onSubmitEditing={onLogin} />
          {error && (
            <Txt variant="sub" color={C.danger}>
              {error}
            </Txt>
          )}
          <View style={s.actions}>
            <TextButton title="로그인" onPress={onLogin} color={C.primary} weight={F.bold} />
            <Txt variant="body" color={C.faint} style={{ fontFamily: F.light }}>
              /
            </Txt>
            <TextButton title="회원가입" onPress={() => router.push('/signup')} color={C.text} weight={F.semibold} />
          </View>

          {/* 대회 규정: 심사위원이 로그인 없이 체험할 수 있어야 함 */}
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="로그인 없이 둘러보기"
            hitSlop={10}
            onPress={() => {
              loginAsGuest();
              router.replace('/news');
            }}
            style={({ pressed }) => [s.guest, pressed && { opacity: 0.6 }]}>
            <Txt variant="sub" muted style={{ textDecorationLine: 'underline', fontFamily: F.light }}>
              로그인 없이 둘러보기
            </Txt>
          </Pressable>
        </View>

        <View style={{ height: d.formBottom, flexShrink: 1 }} />
      </SafeAreaView>
    </View>
  );
}

/** 흰색 둥근 입력칸 (왼쪽에 ID/PW 라벨) */
function LineField({ label, ...props }: { label: string } & React.ComponentProps<typeof TextInput>) {
  const [focused, setFocused] = useState(false);
  return (
    <View style={[s.line, focused && { borderColor: C.primary }]}>
      <Txt variant="body" style={s.lineLabel}>
        {label}
      </Txt>
      <TextInput
        accessibilityLabel={label}
        style={s.lineInput}
        placeholderTextColor={C.faint}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        {...props}
      />
    </View>
  );
}

function TextButton({ title, onPress, color, weight }: { title: string; onPress: () => void; color: string; weight: string }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={title}
      hitSlop={12}
      onPress={onPress}
      style={({ pressed }) => pressed && { opacity: 0.6 }}>
      <Txt variant="body" color={color} style={{ fontFamily: weight, fontSize: 16 }}>
        {title}
      </Txt>
    </Pressable>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  safe: { flex: 1, width: '100%', maxWidth: MAX_W, alignSelf: 'center' },
  logo: { alignItems: 'center' },
  taglineChar: { fontFamily: F.bold, fontSize: 22, lineHeight: 26 },
  guest: { alignItems: 'center', marginTop: 10 },
  spacer: { flex: 1, minHeight: 20 },
  form: { marginHorizontal: 32, gap: 12 },
  line: {
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 54,
    paddingHorizontal: 20,
    borderRadius: 999,
    backgroundColor: '#FFFFFF',
    borderWidth: 2,
    borderColor: '#FFFFFF',
  },
  lineLabel: { width: 40, fontFamily: F.bold },
  lineInput: {
    flex: 1,
    fontSize: 16,
    fontFamily: F.regular,
    color: C.text,
    paddingVertical: 8,
    outlineStyle: 'none',
  } as object,
  actions: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 14, marginTop: 8 },
});
