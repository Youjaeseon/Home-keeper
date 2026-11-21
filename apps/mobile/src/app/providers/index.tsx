import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import {
  ApiError,
  type Profile,
  type ProviderSummary,
  type Region,
  type WorkType,
  getMyProfile,
  getProviders,
  getRegions,
  getWorkTypes,
  messageOf,
} from '@/lib/api';

export default function ProvidersScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{
    regionId?: string | string[];
    workTypeId?: string | string[];
  }>();
  const initialRegionId = Array.isArray(params.regionId)
    ? params.regionId[0]
    : params.regionId;
  const initialWorkTypeId = Array.isArray(params.workTypeId)
    ? params.workTypeId[0]
    : params.workTypeId;

  const [profile, setProfile] = useState<Profile | null>(null);
  const [regions, setRegions] = useState<Region[]>([]);
  const [workTypes, setWorkTypes] = useState<WorkType[]>([]);
  const [regionId, setRegionId] = useState<string | null>(initialRegionId ?? null);
  const [workTypeId, setWorkTypeId] = useState<string | null>(
    initialWorkTypeId ?? null,
  );
  const [providers, setProviders] = useState<ProviderSummary[]>([]);
  const [isSample, setIsSample] = useState(false);
  const [loadingFilters, setLoadingFilters] = useState(true);
  const [loadingProviders, setLoadingProviders] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    setLoadingFilters(true);
    setError(null);
    Promise.all([
      getRegions(),
      getWorkTypes(),
      getMyProfile().catch((profileError) => {
        if (profileError instanceof ApiError && profileError.status === 404) {
          return null;
        }
        throw profileError;
      }),
    ])
      .then(([nextRegions, nextWorkTypes, nextProfile]) => {
        if (!active) return;
        setRegions(nextRegions);
        setWorkTypes(nextWorkTypes);
        setProfile(nextProfile);
        if (!initialRegionId) {
          setRegionId(nextProfile?.region_id ?? nextRegions[0]?.region_id ?? null);
        }
        if (initialWorkTypeId) {
          setWorkTypeId(initialWorkTypeId);
        }
      })
      .catch((loadError) => {
        if (active) setError(messageOf(loadError));
      })
      .finally(() => {
        if (active) setLoadingFilters(false);
      });
    return () => {
      active = false;
    };
  }, [initialRegionId, initialWorkTypeId]);

  useEffect(() => {
    let active = true;
    if (!regionId) {
      setProviders([]);
      setIsSample(false);
      return () => {
        active = false;
      };
    }
    setLoadingProviders(true);
    setError(null);
    getProviders({ regionId, workTypeId })
      .then((response) => {
        if (!active) return;
        setProviders(response.providers);
        setIsSample(response.is_sample);
      })
      .catch((loadError) => {
        if (active) setError(messageOf(loadError));
      })
      .finally(() => {
        if (active) setLoadingProviders(false);
      });
    return () => {
      active = false;
    };
  }, [regionId, workTypeId, reloadKey]);

  const selectedRegion = regions.find((region) => region.region_id === regionId);

  return (
    <SafeAreaView style={styles.screen}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.headerRow}>
          <View style={styles.headerText}>
            <Text style={styles.title}>업체 찾기</Text>
            <Text style={styles.subtitle}>
              {selectedRegion?.display_name ?? profile?.nickname ?? ''}
            </Text>
          </View>
          <Pressable
            accessibilityRole="button"
            onPress={() => router.back()}
            style={styles.textButton}
          >
            <Text style={styles.textButtonLabel}>뒤로</Text>
          </Pressable>
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>지역 확인</Text>
          {loadingFilters ? (
            <View style={styles.row}>
              <ActivityIndicator />
              <Text style={styles.help}>지역을 불러오는 중…</Text>
            </View>
          ) : regions.length === 0 ? (
            <Text style={styles.error}>선택할 수 있는 지역이 없어요.</Text>
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
          <Text style={styles.cardTitle}>특화 분야</Text>
          <View style={styles.chips}>
            <Pressable
              accessibilityRole="button"
              accessibilityState={{ selected: workTypeId === null }}
              onPress={() => setWorkTypeId(null)}
              style={({ pressed }) => [
                styles.chip,
                workTypeId === null && styles.chipSelected,
                pressed && styles.pressed,
              ]}
            >
              <Text
                style={[
                  styles.chipText,
                  workTypeId === null && styles.chipTextSelected,
                ]}
              >
                전체
              </Text>
            </Pressable>
            {workTypes.map((workType) => {
              const selected = workType.work_type_id === workTypeId;
              return (
                <Pressable
                  key={workType.work_type_id}
                  accessibilityRole="button"
                  accessibilityState={{ selected }}
                  onPress={() => setWorkTypeId(workType.work_type_id)}
                  style={({ pressed }) => [
                    styles.chip,
                    selected && styles.chipSelected,
                    pressed && styles.pressed,
                  ]}
                >
                  <Text
                    style={[styles.chipText, selected && styles.chipTextSelected]}
                  >
                    {workType.name}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>

        {isSample ? (
          <View style={styles.notice}>
            <Text style={styles.noticeTitle}>시연용 샘플 업체</Text>
            <Text style={styles.noticeText}>
              확인된 실제 업체가 없어 연락처가 없는 샘플 후보를 보여드려요.
            </Text>
          </View>
        ) : null}

        {loadingProviders || loadingFilters ? (
          <View style={styles.center}>
            <ActivityIndicator />
            <Text style={styles.help}>업체를 불러오는 중…</Text>
          </View>
        ) : error ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>업체를 불러오지 못했어요</Text>
            <Text style={styles.error}>{error}</Text>
            <Pressable
              accessibilityRole="button"
              onPress={() => setReloadKey((value) => value + 1)}
              style={styles.primaryButton}
            >
              <Text style={styles.primaryButtonText}>다시 시도</Text>
            </Pressable>
          </View>
        ) : providers.length === 0 ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>표시할 업체가 없어요</Text>
            <Text style={styles.help}>지역이나 특화 분야를 바꿔 보세요.</Text>
          </View>
        ) : (
          providers.map((provider) => (
            <Pressable
              key={provider.provider_id}
              accessibilityRole="button"
              disabled={provider.is_sample}
              onPress={() =>
                router.push(`/providers/${provider.provider_id}`)
              }
              style={({ pressed }) => [
                styles.providerCard,
                pressed && styles.pressed,
                provider.is_sample && styles.disabled,
              ]}
            >
              <View style={styles.providerHeader}>
                <Text style={styles.providerName}>{provider.name}</Text>
                <Text style={styles.rating}>
                  ★ {provider.rating.toFixed(1)} (리뷰 {provider.review_count})
                </Text>
              </View>
              {provider.description ? (
                <Text style={styles.help}>{provider.description}</Text>
              ) : null}
              <View style={styles.chips}>
                {provider.specialty_work_types.map((workType) => (
                  <View key={workType.work_type_id} style={styles.badge}>
                    <Text style={styles.badgeText}>{workType.name}</Text>
                  </View>
                ))}
              </View>
              <Text style={styles.chatState}>
                {provider.chat_available ? '채팅 가능' : '채팅 불가 · 전화 문의'}
                {provider.is_sample ? ' · 시연용 샘플' : ''}
              </Text>
            </Pressable>
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: '#F7F7F8',
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
  textButton: {
    paddingVertical: 6,
    paddingHorizontal: 4,
  },
  textButtonLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#208AEF',
  },
  card: {
    borderRadius: 12,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E2E4E8',
    padding: 14,
    gap: 8,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#15171A',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  center: {
    alignItems: 'center',
    gap: 8,
    paddingVertical: 24,
  },
  help: {
    fontSize: 13,
    lineHeight: 19,
    color: '#60646C',
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  chip: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: '#D7D9DE',
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  chipSelected: {
    borderColor: '#208AEF',
    backgroundColor: '#EAF4FE',
  },
  chipText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#4E535C',
  },
  chipTextSelected: {
    color: '#1668B3',
  },
  providerCard: {
    borderRadius: 12,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E2E4E8',
    padding: 16,
    gap: 8,
  },
  providerHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
  providerName: {
    flex: 1,
    fontSize: 18,
    fontWeight: '700',
    color: '#15171A',
  },
  rating: {
    fontSize: 14,
    fontWeight: '700',
    color: '#B36B00',
  },
  badge: {
    borderRadius: 999,
    backgroundColor: '#EEF0F3',
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  badgeText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#4E535C',
  },
  chatState: {
    fontSize: 13,
    color: '#4E535C',
  },
  notice: {
    borderRadius: 12,
    backgroundColor: '#FFF4D6',
    padding: 14,
    gap: 4,
  },
  noticeTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#6B4E00',
  },
  noticeText: {
    fontSize: 14,
    lineHeight: 20,
    color: '#6B4E00',
  },
  primaryButton: {
    alignSelf: 'flex-start',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 10,
    backgroundColor: '#208AEF',
    minHeight: 42,
    paddingHorizontal: 16,
  },
  primaryButtonText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#FFFFFF',
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
