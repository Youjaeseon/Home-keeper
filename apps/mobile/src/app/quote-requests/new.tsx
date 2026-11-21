import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import {
  type Profile,
  type RecordDetail,
  type Region,
  type WorkType,
  createQuoteRequest,
  getDraftTemplate,
  getMyProfile,
  getRecord,
  getRegions,
  getWorkTypes,
  messageOf,
} from '@/lib/api';

const LEVEL_LABELS = {
  low: '낮음',
  medium: '중간',
  high: '높음',
  undetermined: '판단 보류',
} as const;

export default function NewQuoteRequestScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ recordId?: string | string[] }>();
  const recordId = Array.isArray(params.recordId)
    ? params.recordId[0]
    : params.recordId;

  const [record, setRecord] = useState<RecordDetail | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [regions, setRegions] = useState<Region[]>([]);
  const [workTypes, setWorkTypes] = useState<WorkType[]>([]);
  const [regionId, setRegionId] = useState<string | null>(null);
  const [workTypeId, setWorkTypeId] = useState<string | null>(null);
  const [address, setAddress] = useState('');
  const [memo, setMemo] = useState('');
  const [loadingDraft, setLoadingDraft] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    if (!recordId) {
      setError('기록 ID가 없어요.');
      setLoading(false);
      return () => {
        active = false;
      };
    }
    setLoading(true);
    setError(null);
    Promise.all([
      getRecord(recordId),
      getRegions(),
      getWorkTypes(),
      getMyProfile().catch(() => null),
    ])
      .then(([nextRecord, nextRegions, nextWorkTypes, nextProfile]) => {
        if (!active) return;
        setRecord(nextRecord);
        setRegions(nextRegions);
        setWorkTypes(nextWorkTypes);
        setProfile(nextProfile);
        setRegionId(nextRecord.region_id ?? nextProfile?.region_id ?? null);
        setWorkTypeId(
          nextRecord.diagnosis?.diagnosis.work_type_id ??
            nextWorkTypes.find((item) => item.name === '원인 점검')?.work_type_id ??
            null,
        );
        setMemo(nextRecord.symptoms ?? '');
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
  }, [recordId]);

  async function loadDraft() {
    if (!recordId) return;
    setLoadingDraft(true);
    setError(null);
    try {
      const draft = await getDraftTemplate(recordId);
      setMemo(draft.text);
    } catch (draftError) {
      setError(messageOf(draftError));
    } finally {
      setLoadingDraft(false);
    }
  }

  async function submit() {
    if (!recordId || submitting) return;
    if (!regionId) {
      setError('지역을 선택해 주세요.');
      return;
    }
    if (!workTypeId) {
      setError('희망 특화 분야를 선택해 주세요.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const created = await createQuoteRequest({
        record_id: recordId,
        region_id: regionId,
        work_type_id: workTypeId,
        address: address.trim() || null,
        memo: memo.trim() || null,
      });
      router.replace(`/quote-requests/${created.request_id}`);
    } catch (submitError) {
      setError(messageOf(submitError));
    } finally {
      setSubmitting(false);
    }
  }

  const diagnosis = record?.diagnosis?.diagnosis ?? null;
  const isProvider = profile?.role === 'provider';

  return (
    <SafeAreaView style={styles.screen}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.headerRow}>
          <View style={styles.headerText}>
            <Text style={styles.title}>견적 요청서</Text>
            <Text style={styles.subtitle}>지역·특화 분야가 맞는 업체에 공개해요.</Text>
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
            <Text style={styles.help}>요청서를 준비하는 중…</Text>
          </View>
        ) : isProvider ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>업체 계정은 요청서를 만들 수 없어요</Text>
            <Text style={styles.help}>요청인 계정에서 견적을 요청해 주세요.</Text>
          </View>
        ) : error && !record ? (
          <View style={styles.card}>
            <Text style={styles.error}>{error}</Text>
          </View>
        ) : record && !diagnosis ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>진단 결과가 없어요</Text>
            <Text style={styles.help}>먼저 분석을 완료해 주세요.</Text>
          </View>
        ) : record && diagnosis ? (
          <>
            {record.photos.length ? (
              <View style={styles.card}>
                <Text style={styles.cardTitle}>하자 사진</Text>
                <View style={styles.photoRow}>
                  {record.photos.map((photo) => (
                    <Image
                      key={`${photo.role}-${photo.url}`}
                      source={{ uri: photo.url }}
                      style={styles.photo}
                      accessibilityLabel={
                        photo.role === 'overview' ? '전체 하자 사진' : '근접 하자 사진'
                      }
                    />
                  ))}
                </View>
              </View>
            ) : null}

            <View style={styles.card}>
              <Text style={styles.cardTitle}>AI 위험도</Text>
              <Text style={styles.severity}>
                {diagnosis.severity_score === null
                  ? '판단 보류'
                  : `${diagnosis.severity_score}%`}
              </Text>
              <Text style={styles.meta}>
                {LEVEL_LABELS[diagnosis.severity_level]} · 의심 유형{' '}
                {diagnosis.suspected_types.join(', ') || '미확인'}
              </Text>
              <Text style={styles.meta}>
                위치 {record.location ?? '미입력'} · 재질 {record.material ?? '미입력'}
              </Text>
            </View>

            <View style={styles.card}>
              <Text style={styles.cardTitle}>지역</Text>
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
              <Text style={styles.label}>상세 주소·장소 (선택)</Text>
              <TextInput
                value={address}
                onChangeText={setAddress}
                style={styles.input}
                placeholder="예: 용인시 수지구"
                placeholderTextColor="#8A8F98"
              />
            </View>

            <View style={styles.card}>
              <Text style={styles.cardTitle}>희망 특화 분야</Text>
              <View style={styles.chips}>
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

            <View style={styles.card}>
              <Text style={styles.cardTitle}>요청 메모</Text>
              <TextInput
                value={memo}
                onChangeText={setMemo}
                multiline
                style={[styles.input, styles.multiline]}
                placeholder="요청 사항이나 희망 일정을 적어 주세요."
                placeholderTextColor="#8A8F98"
              />
              <Pressable
                accessibilityRole="button"
                disabled={loadingDraft}
                onPress={loadDraft}
                style={({ pressed }) => [styles.textButton, pressed && styles.pressed]}
              >
                <Text style={styles.textButtonLabel}>
                  {loadingDraft ? '초안 불러오는 중…' : '견적 요청문 초안 불러오기'}
                </Text>
              </Pressable>
            </View>

            {error ? <Text style={styles.error}>{error}</Text> : null}

            <Pressable
              accessibilityRole="button"
              disabled={submitting || !regionId || !workTypeId}
              onPress={submit}
              style={({ pressed }) => [
                styles.primaryButton,
                (submitting || !regionId || !workTypeId) && styles.disabled,
                pressed && styles.pressed,
              ]}
            >
              {submitting ? (
                <ActivityIndicator color="#FFFFFF" />
              ) : (
                <Text style={styles.primaryButtonText}>견적 요청서 보내기</Text>
              )}
            </Pressable>
          </>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#F7F7F8' },
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
  headerText: { flex: 1, gap: 4 },
  title: { fontSize: 28, fontWeight: '700', color: '#15171A' },
  subtitle: { fontSize: 15, color: '#60646C' },
  textButton: { paddingVertical: 6, paddingHorizontal: 4 },
  textButtonLabel: { fontSize: 14, fontWeight: '600', color: '#208AEF' },
  center: { alignItems: 'center', gap: 8, paddingVertical: 24 },
  card: {
    borderRadius: 12,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E2E4E8',
    padding: 16,
    gap: 8,
  },
  cardTitle: { fontSize: 18, fontWeight: '700', color: '#15171A' },
  severity: { fontSize: 34, fontWeight: '800', color: '#15171A' },
  meta: { fontSize: 13, color: '#60646C' },
  help: { fontSize: 13, lineHeight: 19, color: '#60646C' },
  label: { marginTop: 4, fontSize: 14, fontWeight: '600', color: '#15171A' },
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
  multiline: { minHeight: 110, textAlignVertical: 'top' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: '#D7D9DE',
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  chipSelected: { borderColor: '#208AEF', backgroundColor: '#EAF4FE' },
  chipText: { fontSize: 14, fontWeight: '600', color: '#4E535C' },
  chipTextSelected: { color: '#1668B3' },
  photoRow: { flexDirection: 'row', gap: 8 },
  photo: {
    flex: 1,
    aspectRatio: 1,
    borderRadius: 10,
    backgroundColor: '#EEF0F3',
  },
  primaryButton: {
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 10,
    backgroundColor: '#208AEF',
    minHeight: 50,
    paddingHorizontal: 16,
  },
  primaryButtonText: { fontSize: 16, fontWeight: '700', color: '#FFFFFF' },
  disabled: { opacity: 0.45 },
  pressed: { opacity: 0.75 },
  error: { fontSize: 14, lineHeight: 20, color: '#C0392B' },
});
