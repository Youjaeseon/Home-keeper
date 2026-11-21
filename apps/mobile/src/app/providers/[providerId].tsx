import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Linking,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import {
  type ProviderDetail,
  getProviderDetail,
  messageOf,
} from '@/lib/api';

export default function ProviderDetailScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ providerId?: string | string[] }>();
  const providerId = Array.isArray(params.providerId)
    ? params.providerId[0]
    : params.providerId;
  const [provider, setProvider] = useState<ProviderDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    if (!providerId) {
      setError('업체 ID가 없어요.');
      setLoading(false);
      return () => {
        active = false;
      };
    }
    setLoading(true);
    setError(null);
    getProviderDetail(providerId)
      .then((nextProvider) => {
        if (active) setProvider(nextProvider);
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
  }, [providerId]);

  function callProvider() {
    if (!provider?.phone) return;
    Linking.openURL(`tel:${provider.phone}`).catch(() => {
      Alert.alert('전화 연결 실패', '전화 앱을 열 수 없어요.');
    });
  }

  function openChat() {
    Alert.alert(
      '채팅 준비 중',
      '요청인과의 1:1 채팅은 채팅 화면에서 이어갈 수 있어요.',
    );
  }

  return (
    <SafeAreaView style={styles.screen}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.headerRow}>
          <View style={styles.headerText}>
            <Text style={styles.title}>업체 상세</Text>
            <Text style={styles.subtitle}>{provider?.name ?? ''}</Text>
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
            <Text style={styles.help}>업체 정보를 불러오는 중…</Text>
          </View>
        ) : error ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>업체 정보를 불러오지 못했어요</Text>
            <Text style={styles.error}>{error}</Text>
          </View>
        ) : provider ? (
          <>
            <View style={styles.card}>
              <Text style={styles.cardTitle}>{provider.name}</Text>
              <Text style={styles.rating}>
                ★ {provider.rating.toFixed(1)} · 리뷰 {provider.review_count}
              </Text>
              {provider.description ? (
                <Text style={styles.bodyText}>{provider.description}</Text>
              ) : null}
              <Text style={styles.meta}>전화 {provider.phone ?? '미확인'}</Text>
              <Text style={styles.meta}>주소 {provider.address ?? '미확인'}</Text>
              <Text style={styles.meta}>
                영업시간 {provider.business_hours ?? '미확인'}
              </Text>
              <Text style={styles.meta}>
                경력{' '}
                {provider.career_years === null
                  ? '미확인'
                  : `${provider.career_years}년`}
              </Text>
              <Text style={styles.meta}>
                채팅 {provider.chat_available ? '가능' : '불가'}
              </Text>
            </View>

            <View style={styles.card}>
              <Text style={styles.cardTitle}>특화 분야</Text>
              <Text style={styles.bodyText}>
                {provider.work_types.map((item) => item.name).join(', ') || '미등록'}
              </Text>
              <Text style={styles.cardTitle}>출장 가능 지역</Text>
              <Text style={styles.bodyText}>
                {provider.regions.map((item) => item.display_name).join(', ') ||
                  '미등록'}
              </Text>
            </View>

            <Pressable
              accessibilityRole="button"
              disabled={!provider.chat_available}
              onPress={openChat}
              style={({ pressed }) => [
                styles.primaryButton,
                !provider.chat_available && styles.disabled,
                pressed && styles.pressed,
              ]}
            >
              <Text style={styles.primaryButtonText}>채팅하기</Text>
            </Pressable>
            {!provider.chat_available ? (
              <Text style={styles.help}>
                앱 채팅 계정이 연결되지 않아 전화로 문의해 주세요.
              </Text>
            ) : null}

            <Pressable
              accessibilityRole="button"
              disabled={!provider.phone}
              onPress={callProvider}
              style={({ pressed }) => [
                styles.secondaryButton,
                !provider.phone && styles.disabled,
                pressed && styles.pressed,
              ]}
            >
              <Text style={styles.secondaryButtonText}>전화하기</Text>
            </Pressable>
          </>
        ) : null}
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
  center: {
    alignItems: 'center',
    gap: 8,
    paddingVertical: 24,
  },
  card: {
    borderRadius: 12,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E2E4E8',
    padding: 16,
    gap: 8,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#15171A',
  },
  rating: {
    fontSize: 16,
    fontWeight: '700',
    color: '#B36B00',
  },
  bodyText: {
    fontSize: 15,
    lineHeight: 22,
    color: '#4E535C',
  },
  meta: {
    fontSize: 13,
    color: '#60646C',
  },
  help: {
    fontSize: 13,
    lineHeight: 19,
    color: '#60646C',
  },
  error: {
    fontSize: 14,
    lineHeight: 20,
    color: '#C0392B',
  },
  primaryButton: {
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
  secondaryButton: {
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 50,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#208AEF',
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 16,
  },
  secondaryButtonText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#208AEF',
  },
  disabled: {
    opacity: 0.45,
  },
  pressed: {
    opacity: 0.75,
  },
});
