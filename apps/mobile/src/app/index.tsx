import type { Session } from '@supabase/supabase-js';
import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ApiError, getMyProfile, messageOf } from '@/lib/api';
import { supabase } from '@/lib/supabase';

export default function IndexScreen() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
    });
    return () => subscription.unsubscribe();
  }, []);

  if (loading) {
    return (
      <SafeAreaView style={styles.center}>
        <ActivityIndicator />
      </SafeAreaView>
    );
  }

  return session ? <HomeScreen session={session} /> : <LoginScreen />;
}

function LoginScreen() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function signIn() {
    setSubmitting(true);
    setError(null);
    const { error: signInError } = await supabase.auth.signInWithPassword({
      email: email.trim(),
      password,
    });
    if (signInError) {
      setError(signInError.message);
    }
    setSubmitting(false);
  }

  return (
    <SafeAreaView style={styles.screen}>
      <ScrollView contentContainerStyle={styles.form}>
        <Text style={styles.title}>Career Pair</Text>
        <Text style={styles.subtitle}>준비된 Supabase 계정으로 로그인해요.</Text>

        <Text style={styles.label}>이메일</Text>
        <TextInput
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="email-address"
          textContentType="emailAddress"
          style={styles.input}
          placeholder="you@example.com"
          placeholderTextColor="#8A8F98"
        />

        <Text style={styles.label}>비밀번호</Text>
        <TextInput
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          textContentType="password"
          style={styles.input}
          placeholder="비밀번호"
          placeholderTextColor="#8A8F98"
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Pressable
          accessibilityRole="button"
          disabled={submitting || !email.trim() || !password}
          onPress={signIn}
          style={({ pressed }) => [
            styles.primaryButton,
            (submitting || !email.trim() || !password) && styles.disabled,
            pressed && styles.pressed,
          ]}
        >
          {submitting ? (
            <ActivityIndicator color="#FFFFFF" />
          ) : (
            <Text style={styles.primaryButtonText}>로그인</Text>
          )}
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

function HomeScreen({ session }: { session: Session }) {
  const router = useRouter();
  const [profileStatus, setProfileStatus] = useState<'loading' | 'ready' | 'error'>(
    'loading',
  );
  const [profileError, setProfileError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useFocusEffect(
    useCallback(() => {
      let active = true;
      setProfileStatus('loading');
      setProfileError(null);
      getMyProfile()
        .then(() => {
          if (active) setProfileStatus('ready');
        })
        .catch((error: unknown) => {
          if (!active) return;
          if (error instanceof ApiError && error.status === 404) {
            router.replace('/profile');
            return;
          }
          setProfileError(messageOf(error));
          setProfileStatus('error');
        });
      return () => {
        active = false;
      };
    }, [reloadKey, router, session.user.id]),
  );

  function startAnalysis() {
    if (profileStatus !== 'ready') return;
    router.push({
      pathname: '/analyze',
      params: { session: Date.now().toString() },
    });
  }

  return (
    <SafeAreaView style={styles.screen}>
      <ScrollView contentContainerStyle={styles.form}>
        <View style={styles.headerRow}>
          <View style={styles.headerText}>
            <Text style={styles.title}>하자 분석</Text>
            <Text style={styles.subtitle}>{session.user.email}</Text>
          </View>
          <View style={styles.headerActions}>
            <Pressable
              accessibilityRole="button"
              onPress={() => router.push('/profile')}
              style={({ pressed }) => [styles.textButton, pressed && styles.pressed]}
            >
              <Text style={styles.textButtonLabel}>내 정보</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              onPress={() => supabase.auth.signOut()}
              style={({ pressed }) => [styles.textButton, pressed && styles.pressed]}
            >
              <Text style={styles.textButtonLabel}>로그아웃</Text>
            </Pressable>
          </View>
        </View>

        {profileStatus === 'loading' ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>프로필을 확인하는 중…</Text>
          </View>
        ) : null}

        {profileStatus === 'error' ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>프로필을 불러오지 못했어요</Text>
            <Text style={styles.error}>{profileError}</Text>
            <Pressable
              accessibilityRole="button"
              onPress={() => setReloadKey((value) => value + 1)}
              style={({ pressed }) => [styles.retryButton, pressed && styles.pressed]}
            >
              <Text style={styles.textButtonLabel}>다시 시도</Text>
            </Pressable>
          </View>
        ) : null}

        <View style={styles.card}>
          <Text style={styles.cardTitle}>사진으로 하자 상태를 확인해요</Text>
          <Text style={styles.bodyText}>
            같은 하자의 전체 사진과 근접 사진을 1~2장 선택하고, 발견 위치와 표면
            재질을 입력해 주세요. 증상 메모는 선택입니다.
          </Text>
          <Text style={styles.bodyText}>
            현재는 실제 사진 분석 모델 없이 입력값으로 만든 샘플 결과를
            보여드려요. 결과 화면의 샘플 안내를 꼭 확인해 주세요.
          </Text>
        </View>

        <Pressable
          accessibilityRole="button"
          disabled={profileStatus !== 'ready'}
          onPress={startAnalysis}
          style={({ pressed }) => [
            styles.primaryButton,
            profileStatus !== 'ready' && styles.disabled,
            pressed && styles.pressed,
          ]}
        >
          <Text style={styles.primaryButtonText}>
            {profileStatus === 'loading' ? '프로필 확인 중…' : '새 분석 시작'}
          </Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: '#F7F7F8',
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  form: {
    flexGrow: 1,
    justifyContent: 'center',
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
  headerText: {
    flex: 1,
    gap: 4,
  },
  headerActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  retryButton: {
    alignSelf: 'flex-start',
    paddingVertical: 4,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: '#15171A',
  },
  subtitle: {
    fontSize: 15,
    color: '#60646C',
  },
  label: {
    marginTop: 8,
    fontSize: 14,
    fontWeight: '600',
    color: '#15171A',
  },
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
  card: {
    borderWidth: 1,
    borderColor: '#E2E4E8',
    borderRadius: 12,
    backgroundColor: '#FFFFFF',
    padding: 16,
    gap: 8,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#15171A',
  },
  bodyText: {
    fontSize: 15,
    lineHeight: 22,
    color: '#4E535C',
  },
  primaryButton: {
    marginTop: 8,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 10,
    backgroundColor: '#208AEF',
    minHeight: 50,
    paddingHorizontal: 16,
  },
  primaryButtonText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  textButton: {
    paddingVertical: 6,
    paddingHorizontal: 4,
  },
  textButtonLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#208AEF',
  },
  disabled: {
    opacity: 0.45,
  },
  pressed: {
    opacity: 0.75,
  },
  error: {
    fontSize: 14,
    lineHeight: 20,
    color: '#C0392B',
  },
});
