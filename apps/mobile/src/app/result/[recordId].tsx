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
  type DiagnosisResult,
  type RecordDetail,
  getRecord,
  messageOf,
} from '@/lib/api';

const LEVEL_LABELS: Record<DiagnosisResult['severity_level'], string> = {
  low: '낮음',
  medium: '중간',
  high: '높음',
  undetermined: '판단 보류',
};

const ACTION_LABELS: Record<DiagnosisResult['recommended_action'], string> = {
  self_care: '직접 조치',
  inspection: '점검 요청',
  provider_consult: '업체 상담',
};

function Bullets({ items }: { items: string[] }) {
  return (
    <View style={styles.bullets}>
      {items.map((item, index) => (
        <Text key={`${index}-${item}`} style={styles.bullet}>
          • {item}
        </Text>
      ))}
    </View>
  );
}

export default function ResultScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ recordId?: string | string[] }>();
  const recordId = Array.isArray(params.recordId)
    ? params.recordId[0]
    : params.recordId;
  const [detail, setDetail] = useState<RecordDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!recordId) {
      setError('분석 기록 ID가 없어요.');
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    setError(null);
    getRecord(recordId)
      .then((nextDetail) => {
        if (active) setDetail(nextDetail);
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
  }, [recordId, reloadKey]);

  function startNewAnalysis() {
    router.replace({
      pathname: '/analyze',
      params: { session: Date.now().toString() },
    });
  }

  const diagnosis = detail?.diagnosis?.diagnosis ?? null;
  const isSample = diagnosis?.source === 'sample';

  return (
    <SafeAreaView style={styles.screen}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.headerRow}>
          <View style={styles.headerText}>
            <Text style={styles.title}>분석 결과</Text>
            <Text style={styles.subtitle}>사진 분석·입력 기반 진단</Text>
          </View>
          <Pressable
            accessibilityRole="button"
            onPress={() => router.replace('/')}
            style={styles.textButton}
          >
            <Text style={styles.textButtonLabel}>홈</Text>
          </Pressable>
        </View>

        {loading ? (
          <View style={styles.center}>
            <ActivityIndicator />
            <Text style={styles.help}>결과를 불러오는 중…</Text>
          </View>
        ) : error ? (
          <View style={styles.errorCard}>
            <Text style={styles.errorTitle}>결과를 불러오지 못했어요</Text>
            <Text style={styles.error}>{error}</Text>
            <Pressable
              accessibilityRole="button"
              onPress={() => setReloadKey((value) => value + 1)}
              style={styles.primaryButton}
            >
              <Text style={styles.primaryButtonText}>다시 시도</Text>
            </Pressable>
          </View>
        ) : !diagnosis ? (
          <View style={styles.errorCard}>
            <Text style={styles.errorTitle}>분석 결과가 없어요</Text>
            <Text style={styles.help}>
              기록은 저장되었지만 진단 결과가 없습니다. 새 분석을 시작해 주세요.
            </Text>
            <Pressable
              accessibilityRole="button"
              onPress={startNewAnalysis}
              style={styles.primaryButton}
            >
              <Text style={styles.primaryButtonText}>새 분석 시작</Text>
            </Pressable>
          </View>
        ) : (
          <>
            {isSample ? (
              <View style={styles.sampleBanner}>
                <Text style={styles.sampleTitle}>
                  {detail?.photo_observations?.applied
                    ? '사진 탐지 결과 · 진단 안내는 샘플'
                    : '샘플 결과 · 실제 사진 분석 아님'}
                </Text>
                <Text style={styles.sampleText}>
                  {detail?.photo_observations?.notice ??
                    '현재는 실제 사진 분석 모델을 호출하지 않습니다.'}
                </Text>
              </View>
            ) : null}

            {detail?.diagnosis?.is_current === false ? (
              <View style={styles.staleBanner}>
                <Text style={styles.staleTitle}>이전 입력의 분석 결과예요</Text>
                <Text style={styles.staleText}>
                  입력이 바뀌어 최신 결과가 아닙니다. 새 분석을 시작해 주세요.
                </Text>
              </View>
            ) : null}

            <View style={styles.summaryCard}>
              <Text style={styles.cardTitle}>심각도</Text>
              <Text style={styles.severity}>
                {diagnosis.severity_score === null
                  ? '판단 보류'
                  : `${diagnosis.severity_score}%`}
              </Text>
              <Text style={styles.level}>
                {LEVEL_LABELS[diagnosis.severity_level]}
              </Text>
              <Text style={styles.reason}>{diagnosis.reason}</Text>
              <Text style={styles.meta}>
                위치 {detail?.location ?? '미입력'} · 재질 {detail?.material ?? '미입력'}
                {detail?.region_name ? ` · 지역 ${detail.region_name}` : ''}
              </Text>
              {detail?.symptoms ? (
                <Text style={styles.meta}>증상 메모 {detail.symptoms}</Text>
              ) : null}
              <Text style={styles.observations}>{diagnosis.observations}</Text>
            </View>

            <View style={styles.card}>
              <Text style={styles.cardTitle}>추정 원인</Text>
              <Bullets items={diagnosis.causes} />
              <Text style={styles.noticeText}>{diagnosis.estimation_notice}</Text>
              <Text style={styles.subheading}>미확인 정보</Text>
              <Bullets items={diagnosis.unknowns} />
            </View>

            <View style={styles.card}>
              <Text style={styles.cardTitle}>해결방안</Text>
              <Text style={styles.action}>
                권장 대응 · {ACTION_LABELS[diagnosis.recommended_action]}
              </Text>
              <Bullets items={diagnosis.care_steps} />
              <Text style={styles.subheading}>준비물</Text>
              <Text style={styles.bodyText}>{diagnosis.supplies.join(', ')}</Text>
            </View>

            <View style={styles.card}>
              <Text style={styles.cardTitle}>재발 방지책</Text>
              <Bullets items={diagnosis.prevention_tips} />
            </View>

            <View style={styles.card}>
              <Text style={styles.cardTitle}>추천 작업</Text>
              <Text style={styles.bodyText}>{diagnosis.work_type_reason}</Text>
            </View>

            <Pressable
              accessibilityRole="button"
              onPress={startNewAnalysis}
              style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed]}
            >
              <Text style={styles.primaryButtonText}>새 분석 시작</Text>
            </Pressable>
          </>
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
  center: {
    alignItems: 'center',
    gap: 8,
    paddingVertical: 40,
  },
  help: {
    fontSize: 13,
    lineHeight: 19,
    color: '#60646C',
  },
  sampleBanner: {
    borderRadius: 12,
    backgroundColor: '#FFF4D6',
    padding: 14,
    gap: 4,
  },
  sampleTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#6B4E00',
  },
  sampleText: {
    fontSize: 14,
    lineHeight: 20,
    color: '#6B4E00',
  },
  staleBanner: {
    borderRadius: 12,
    backgroundColor: '#FDECEA',
    padding: 14,
    gap: 4,
  },
  staleTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#A93226',
  },
  staleText: {
    fontSize: 14,
    lineHeight: 20,
    color: '#A93226',
  },
  summaryCard: {
    borderRadius: 12,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E2E4E8',
    padding: 16,
    gap: 6,
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
  severity: {
    fontSize: 40,
    fontWeight: '800',
    color: '#15171A',
  },
  level: {
    fontSize: 16,
    fontWeight: '700',
    color: '#208AEF',
  },
  reason: {
    fontSize: 15,
    lineHeight: 22,
    color: '#2A2E35',
  },
  meta: {
    fontSize: 13,
    color: '#60646C',
  },
  observations: {
    marginTop: 4,
    fontSize: 14,
    lineHeight: 21,
    color: '#4E535C',
  },
  subheading: {
    marginTop: 4,
    fontSize: 14,
    fontWeight: '700',
    color: '#15171A',
  },
  bullets: {
    gap: 4,
  },
  bullet: {
    fontSize: 14,
    lineHeight: 21,
    color: '#2A2E35',
  },
  noticeText: {
    fontSize: 13,
    lineHeight: 20,
    color: '#60646C',
  },
  action: {
    fontSize: 15,
    fontWeight: '600',
    color: '#208AEF',
  },
  bodyText: {
    fontSize: 15,
    lineHeight: 22,
    color: '#2A2E35',
  },
  errorCard: {
    borderRadius: 12,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E2E4E8',
    padding: 16,
    gap: 8,
  },
  errorTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#15171A',
  },
  error: {
    fontSize: 14,
    lineHeight: 20,
    color: '#C0392B',
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
  pressed: {
    opacity: 0.75,
  },
});
