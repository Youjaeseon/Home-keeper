import type { Session } from '@supabase/supabase-js';
import { Redirect, useRouter } from 'expo-router';
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
  type HousingType,
  type Profile,
  type RecordListItem,
  type Region,
  getMyProfile,
  getRecords,
  getRegions,
  messageOf,
  saveMyProfile,
} from '@/lib/api';
import { supabase } from '@/lib/supabase';

const HOUSING_OPTIONS: { value: HousingType; label: string }[] = [
  { value: 'monthly_rent', label: '월세' },
  { value: 'jeonse', label: '전세' },
  { value: 'semi_jeonse', label: '반전세' },
  { value: 'owned', label: '자가' },
  { value: 'other', label: '기타' },
];

const LEVEL_LABELS: Record<NonNullable<RecordListItem['severity_level']>, string> = {
  low: '낮음',
  medium: '중간',
  high: '높음',
  undetermined: '판단 보류',
};

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}.${month}.${day}`;
}

export default function ProfileScreen() {
  const [session, setSession] = useState<Session | null>(null);
  const [authLoading, setAuthLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setAuthLoading(false);
    });
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      setAuthLoading(false);
    });
    return () => subscription.unsubscribe();
  }, []);

  if (authLoading) {
    return (
      <SafeAreaView style={styles.center}>
        <ActivityIndicator />
      </SafeAreaView>
    );
  }
  if (!session) {
    return <Redirect href="/" />;
  }
  return <ProfileContent session={session} />;
}

function ProfileContent({ session }: { session: Session }) {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [regions, setRegions] = useState<Region[]>([]);
  const [records, setRecords] = useState<RecordListItem[]>([]);
  const [nickname, setNickname] = useState('');
  const [address, setAddress] = useState('');
  const [regionId, setRegionId] = useState<string | null>(null);
  const [housingType, setHousingType] = useState<HousingType | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setLoadError(null);
    setFormError(null);

    async function load() {
      try {
        const [nextRegions, nextRecords] = await Promise.all([
          getRegions(),
          getRecords(),
        ]);
        if (!active) return;
        setRegions(nextRegions);
        setRecords(nextRecords);

        let nextProfile: Profile | null = null;
        try {
          nextProfile = await getMyProfile();
        } catch (error) {
          if (!(error instanceof ApiError && error.status === 404)) {
            throw error;
          }
        }
        if (!active) return;
        setProfile(nextProfile);
        setNickname(nextProfile?.nickname ?? '');
        setAddress(nextProfile?.address ?? '');
        setRegionId(nextProfile?.region_id ?? null);
        setHousingType(nextProfile?.housing_type ?? null);
      } catch (error) {
        if (active) setLoadError(messageOf(error));
      } finally {
        if (active) setLoading(false);
      }
    }

    load();
    return () => {
      active = false;
    };
  }, [session.user.id, reloadKey]);

  function goHome() {
    if (router.canGoBack()) {
      router.back();
    } else {
      router.replace('/');
    }
  }

  async function save() {
    if (!nickname.trim()) {
      setFormError('닉네임을 입력해 주세요.');
      return;
    }
    if (!regionId) {
      setFormError('거주 지역을 선택해 주세요.');
      return;
    }
    if (!housingType) {
      setFormError('거주 형태를 선택해 주세요.');
      return;
    }

    setSaving(true);
    setFormError(null);
    try {
      const saved = await saveMyProfile({
        nickname: nickname.trim(),
        region_id: regionId,
        address: address.trim() || null,
        housing_type: housingType,
      });
      setProfile(saved);
      goHome();
    } catch (error) {
      setFormError(messageOf(error));
    } finally {
      setSaving(false);
    }
  }

  const canSave =
    !saving &&
    Boolean(nickname.trim()) &&
    Boolean(regionId) &&
    Boolean(housingType);

  if (loading) {
    return (
      <SafeAreaView style={styles.center}>
        <ActivityIndicator />
        <Text style={styles.help}>내 정보를 불러오는 중…</Text>
      </SafeAreaView>
    );
  }

  if (loadError) {
    return (
      <SafeAreaView style={styles.screen}>
        <ScrollView contentContainerStyle={styles.content}>
          <Text style={styles.title}>내 정보</Text>
          <View style={styles.card}>
            <Text style={styles.cardTitle}>내 정보를 불러오지 못했어요</Text>
            <Text style={styles.error}>{loadError}</Text>
            <Pressable
              accessibilityRole="button"
              onPress={() => setReloadKey((value) => value + 1)}
              style={styles.primaryButton}
            >
              <Text style={styles.primaryButtonText}>다시 시도</Text>
            </Pressable>
          </View>
          <Pressable
            accessibilityRole="button"
            onPress={() => supabase.auth.signOut()}
            style={styles.textButton}
          >
            <Text style={styles.textButtonLabel}>로그아웃</Text>
          </Pressable>
        </ScrollView>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.screen}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.headerRow}>
          <View style={styles.headerText}>
            <Text style={styles.title}>{profile ? '내 정보' : '내 정보 등록'}</Text>
            <Text style={styles.subtitle}>{session.user.email}</Text>
          </View>
          {profile ? (
            <Pressable
              accessibilityRole="button"
              onPress={goHome}
              style={({ pressed }) => [styles.textButton, pressed && styles.pressed]}
            >
              <Text style={styles.textButtonLabel}>홈으로</Text>
            </Pressable>
          ) : null}
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>기본 정보</Text>
          <Text style={styles.label}>닉네임</Text>
          <TextInput
            value={nickname}
            onChangeText={setNickname}
            maxLength={80}
            accessibilityLabel="닉네임"
            style={styles.input}
            placeholder="예: 하자탐정"
            placeholderTextColor="#8A8F98"
          />
          <Text style={styles.label}>주소 (선택)</Text>
          <TextInput
            value={address}
            onChangeText={setAddress}
            accessibilityLabel="주소"
            style={styles.input}
            placeholder="예: 용인시 수지구"
            placeholderTextColor="#8A8F98"
          />
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>거주 지역</Text>
          {regions.length === 0 ? (
            <Text style={styles.help}>선택할 수 있는 지역이 없어요.</Text>
          ) : (
            <View style={styles.chips}>
              {regions.map((region) => {
                const selected = region.region_id === regionId;
                return (
                  <Pressable
                    key={region.region_id}
                    accessibilityRole="button"
                    accessibilityState={{ selected }}
                    onPress={() => setRegionId(region.region_id)}
                    style={({ pressed }) => [
                      styles.chip,
                      selected && styles.chipSelected,
                      pressed && styles.pressed,
                    ]}
                  >
                    <Text
                      style={[styles.chipText, selected && styles.chipTextSelected]}
                    >
                      {region.display_name}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          )}
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>거주 형태</Text>
          <View style={styles.chips}>
            {HOUSING_OPTIONS.map((option) => {
              const selected = option.value === housingType;
              return (
                <Pressable
                  key={option.value}
                  accessibilityRole="button"
                  accessibilityState={{ selected }}
                  onPress={() => setHousingType(option.value)}
                  style={({ pressed }) => [
                    styles.chip,
                    selected && styles.chipSelected,
                    pressed && styles.pressed,
                  ]}
                >
                  <Text
                    style={[styles.chipText, selected && styles.chipTextSelected]}
                  >
                    {option.label}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>

        {formError ? <Text style={styles.error}>{formError}</Text> : null}

        <Pressable
          accessibilityRole="button"
          disabled={!canSave}
          onPress={save}
          style={({ pressed }) => [
            styles.primaryButton,
            !canSave && styles.disabled,
            pressed && styles.pressed,
          ]}
        >
          {saving ? (
            <ActivityIndicator color="#FFFFFF" />
          ) : (
            <Text style={styles.primaryButtonText}>
              {profile ? '저장' : '저장하고 시작'}
            </Text>
          )}
        </Pressable>

        <View style={styles.historySection}>
          <View style={styles.sectionHeaderRow}>
            <Text style={styles.cardTitle}>내 분석 기록</Text>
            <Text style={styles.count}>{records.length}</Text>
          </View>
          {records.length === 0 ? (
            <Text style={styles.help}>아직 분석 기록이 없어요.</Text>
          ) : (
            records.map((record) => {
              const headline =
                record.suspected_types.join(', ') ||
                record.symptoms ||
                '하자 기록';
              const where = [record.location, record.material]
                .filter(Boolean)
                .join(' · ');
              const level = record.severity_level
                ? LEVEL_LABELS[record.severity_level]
                : '진단 전';
              const score =
                record.severity_score === null ? '' : ` · ${record.severity_score}%`;

              return (
                <Pressable
                  key={record.record_id}
                  accessibilityRole="button"
                  onPress={() =>
                    router.push({
                      pathname: '/result/[recordId]',
                      params: { recordId: record.record_id },
                    })
                  }
                  style={({ pressed }) => [
                    styles.recordCard,
                    pressed && styles.pressed,
                  ]}
                >
                  <View style={styles.recordHeader}>
                    <Text style={styles.recordTitle} numberOfLines={1}>
                      {headline}
                    </Text>
                    <Text style={styles.recordDate}>
                      {formatDate(record.updated_at)}
                    </Text>
                  </View>
                  {where ? (
                    <Text style={styles.recordMeta} numberOfLines={1}>
                      {where}
                    </Text>
                  ) : null}
                  <Text style={styles.recordMeta}>
                    심각도 {level}
                    {score}
                  </Text>
                </Pressable>
              );
            })
          )}
        </View>

        <Pressable
          accessibilityRole="button"
          onPress={() => supabase.auth.signOut()}
          style={({ pressed }) => [styles.textButton, pressed && styles.pressed]}
        >
          <Text style={styles.textButtonLabel}>로그아웃</Text>
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
    gap: 8,
  },
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
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  chip: {
    borderWidth: 1,
    borderColor: '#D7D9DE',
    borderRadius: 999,
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 14,
    paddingVertical: 9,
  },
  chipSelected: {
    borderColor: '#208AEF',
    backgroundColor: '#EAF4FF',
  },
  chipText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#4E535C',
  },
  chipTextSelected: {
    color: '#1668B3',
  },
  primaryButton: {
    marginTop: 4,
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
    alignSelf: 'flex-start',
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
  help: {
    fontSize: 15,
    lineHeight: 22,
    color: '#60646C',
  },
  historySection: {
    gap: 8,
    marginTop: 8,
  },
  sectionHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  count: {
    fontSize: 14,
    fontWeight: '700',
    color: '#60646C',
  },
  recordCard: {
    borderWidth: 1,
    borderColor: '#E2E4E8',
    borderRadius: 12,
    backgroundColor: '#FFFFFF',
    padding: 14,
    gap: 4,
  },
  recordHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
  recordTitle: {
    flex: 1,
    fontSize: 16,
    fontWeight: '700',
    color: '#15171A',
  },
  recordDate: {
    fontSize: 12,
    color: '#8A8F98',
  },
  recordMeta: {
    fontSize: 14,
    lineHeight: 20,
    color: '#60646C',
  },
});
