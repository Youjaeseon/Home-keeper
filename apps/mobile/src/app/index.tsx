import type { Session } from '@supabase/supabase-js';
import { useEffect, useState } from 'react';
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

import {
  ApiError,
  type RecordDetail,
  type RecordSummary,
  checkHealth,
  createRecord,
  getRecord,
} from '@/lib/api';
import { apiBaseUrl } from '@/lib/env';
import { supabase } from '@/lib/supabase';

function messageOf(error: unknown): string {
  if (error instanceof ApiError) {
    const revision =
      error.inputRevision === undefined ? '' : ` (input_revision ${error.inputRevision})`;
    return `${error.status} ${error.code}: ${error.message}${revision}`;
  }
  return error instanceof Error ? error.message : String(error);
}

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

  return session ? <Workspace session={session} /> : <LoginScreen />;
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

function Workspace({ session }: { session: Session }) {
  const [health, setHealth] = useState<string | null>(null);
  const [record, setRecord] = useState<RecordSummary | null>(null);
  const [detail, setDetail] = useState<RecordDetail | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(label: string, action: () => Promise<void>) {
    setBusy(label);
    setError(null);
    try {
      await action();
    } catch (actionError) {
      setError(messageOf(actionError));
    } finally {
      setBusy(null);
    }
  }

  return (
    <SafeAreaView style={styles.screen}>
      <ScrollView contentContainerStyle={styles.form}>
        <View style={styles.headerRow}>
          <View style={styles.headerText}>
            <Text style={styles.title}>연결 확인</Text>
            <Text style={styles.subtitle}>{session.user.email}</Text>
          </View>
          <Pressable
            accessibilityRole="button"
            onPress={() => supabase.auth.signOut()}
            style={({ pressed }) => [styles.textButton, pressed && styles.pressed]}
          >
            <Text style={styles.textButtonLabel}>로그아웃</Text>
          </Pressable>
        </View>

        <Text style={styles.meta}>API {apiBaseUrl}</Text>

        <Pressable
          accessibilityRole="button"
          disabled={busy !== null}
          onPress={() =>
            run('health', async () => {
              setHealth(await checkHealth());
            })
          }
          style={({ pressed }) => [
            styles.secondaryButton,
            busy !== null && styles.disabled,
            pressed && styles.pressed,
          ]}
        >
          <Text style={styles.secondaryButtonText}>
            {busy === 'health' ? '확인 중…' : '서버 확인'}
          </Text>
        </Pressable>

        {health ? (
          <Text style={styles.success}>GET /health → {health}</Text>
        ) : null}

        <Pressable
          accessibilityRole="button"
          disabled={busy !== null}
          onPress={() =>
            run('create', async () => {
              const created = await createRecord();
              setRecord(created);
              setDetail(null);
            })
          }
          style={({ pressed }) => [
            styles.primaryButton,
            busy !== null && styles.disabled,
            pressed && styles.pressed,
          ]}
        >
          <Text style={styles.primaryButtonText}>
            {busy === 'create' ? '만드는 중…' : '새 기록 만들기'}
          </Text>
        </Pressable>

        {record ? (
          <View style={styles.card}>
            <Text style={styles.cardLabel}>record_id</Text>
            <Text selectable style={styles.mono}>
              {record.record_id}
            </Text>
            <Text style={styles.meta}>input_revision {detail?.input_revision ?? record.input_revision}</Text>

            <Pressable
              accessibilityRole="button"
              disabled={busy !== null}
              onPress={() =>
                run('detail', async () => {
                  setDetail(await getRecord(record.record_id));
                })
              }
              style={({ pressed }) => [
                styles.secondaryButton,
                busy !== null && styles.disabled,
                pressed && styles.pressed,
              ]}
            >
              <Text style={styles.secondaryButtonText}>
                {busy === 'detail' ? '조회 중…' : '기록 조회'}
              </Text>
            </Pressable>
          </View>
        ) : null}

        {detail ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>GET /records/{detail.record_id.slice(0, 8)}…</Text>
            <Text style={styles.meta}>위치: {detail.location ?? '미입력'}</Text>
            <Text style={styles.meta}>증상: {detail.symptoms ?? '미입력'}</Text>
            <Text style={styles.meta}>
              질문 {detail.questions.length}개 · 메시지 {detail.messages.length}개
            </Text>
          </View>
        ) : null}

        {error ? <Text style={styles.error}>{error}</Text> : null}
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
  primaryButton: {
    marginTop: 8,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 10,
    backgroundColor: '#1F6FEB',
    paddingVertical: 14,
    minHeight: 48,
  },
  primaryButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  secondaryButton: {
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#C9CDD4',
    backgroundColor: '#FFFFFF',
    paddingVertical: 12,
    minHeight: 46,
  },
  secondaryButtonText: {
    color: '#15171A',
    fontSize: 15,
    fontWeight: '600',
  },
  textButton: {
    paddingVertical: 8,
    paddingHorizontal: 4,
  },
  textButtonLabel: {
    color: '#1F6FEB',
    fontSize: 15,
    fontWeight: '600',
  },
  disabled: {
    opacity: 0.5,
  },
  pressed: {
    opacity: 0.7,
  },
  card: {
    gap: 8,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E1E3E7',
    backgroundColor: '#FFFFFF',
    padding: 16,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#15171A',
  },
  cardLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: '#60646C',
    textTransform: 'uppercase',
  },
  mono: {
    fontFamily: 'monospace',
    fontSize: 13,
    color: '#15171A',
  },
  meta: {
    fontSize: 13,
    color: '#60646C',
  },
  success: {
    fontSize: 13,
    color: '#1A7F37',
  },
  error: {
    fontSize: 13,
    color: '#C62828',
  },
});
