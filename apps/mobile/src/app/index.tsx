import { Redirect, router } from 'expo-router';
import { Sparkles } from 'lucide-react-native';
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, TextInput, useWindowDimensions, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { LogoMark } from '@/components/logo';
import { Button, Txt } from '@/components/ui';
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
  const { ready, session, user, needsProfile, skipAutoGuest, login, loginAsGuest } = useApp();
  const { height } = useWindowDimensions();
  const [loginId, setLoginId] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<'login' | 'guest' | null>(null);
  const [autoTried, setAutoTried] = useState(false);
  const mountedRef = useRef(true);
  const autoStartedRef = useRef(false);
  const d = LOGIN_DESIGN;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const shouldAutoGuest = ready && !session && !skipAutoGuest && !autoTried;

  // 최초 비로그인 접속 시 자동 익명 체험 진입 (로그인 화면을 먼저 보여 주려면 이 블록만 제거하면 됩니다.)
  useEffect(() => {
    if (!shouldAutoGuest || autoStartedRef.current) return;
    autoStartedRef.current = true;
    void loginAsGuest().then((err) => {
      if (!mountedRef.current) return;
      setAutoTried(true);
      if (err) setError(err);
    });
  }, [shouldAutoGuest, loginAsGuest]);

  // 세션 복원 결과에 따라 이동합니다. 프로필이 없으면(GET /me/profile 404) 프로필 등록으로 보냅니다.
  if (ready && session && user) return <Redirect href="/news" />;
  if (ready && session && needsProfile) return <Redirect href="/profile-setup" />;

  const preparingGuest = !ready || shouldAutoGuest || (Boolean(session) && !user && !needsProfile && !error);

  const logoBlock = (
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
  );

  if (preparingGuest) {
    return (
      <View style={s.root}>
        <SafeAreaView style={s.safe}>
          {logoBlock}
          <View style={s.loadingBox}>
            <ActivityIndicator size="large" color={C.primary} />
            <Txt variant="bodyStrong" muted>
              체험 환경 준비 중...
            </Txt>
          </View>
        </SafeAreaView>
      </View>
    );
  }

  const onLogin = async () => {
    if (busy) return;
    if (!loginId.trim() || !password) {
      setError('ID(이메일)와 PW를 입력해 주세요.');
      return;
    }
    setError(null);
    setBusy('login');
    const err = await login(loginId.trim(), password);
    if (!mountedRef.current) return;
    setBusy(null);
    setError(err);
  };

  const onGuest = async () => {
    if (busy) return;
    autoStartedRef.current = true;
    setAutoTried(true);
    setError(null);
    setBusy('guest');
    const err = await loginAsGuest();
    if (!mountedRef.current) return;
    setBusy(null);
    setError(err);
  };

  return (
    <View style={s.root}>
      <SafeAreaView style={s.safe}>
        {logoBlock}

        <View style={s.spacer} />
        <View style={s.form}>
          <LineField
            label="ID"
            value={loginId}
            onChangeText={setLoginId}
            autoCapitalize="none"
            keyboardType="email-address"
            placeholder="이메일"
          />
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
          <Button
            title="로그인 없이 바로 체험하기"
            icon={Sparkles}
            loading={busy === 'guest'}
            disabled={busy !== null}
            onPress={onGuest}
            style={{ marginTop: 12 }}
          />
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
  loadingBox: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 16, paddingBottom: 80 },
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
