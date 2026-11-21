import * as ImagePicker from 'expo-image-picker';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import {
  ApiError,
  type Profile,
  type Region,
  analyzeRecord,
  createRecord,
  getMyProfile,
  getRegions,
  messageOf,
  saveMyProfile,
} from '@/lib/api';

export default function AnalyzeScreen() {
  const router = useRouter();
  const { session } = useLocalSearchParams<{ session?: string }>();
  const [photos, setPhotos] = useState<ImagePicker.ImagePickerAsset[]>([]);
  const [location, setLocation] = useState('');
  const [material, setMaterial] = useState('');
  const [symptoms, setSymptoms] = useState('');
  const [consent, setConsent] = useState(false);
  const [recordId, setRecordId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [regions, setRegions] = useState<Region[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [regionId, setRegionId] = useState<string | null>(null);
  const [updateProfileRegion, setUpdateProfileRegion] = useState(false);
  const [regionLoading, setRegionLoading] = useState(true);

  useEffect(() => {
    setPhotos([]);
    setLocation('');
    setMaterial('');
    setSymptoms('');
    setConsent(false);
    setRecordId(null);
    setSubmitting(false);
    setError(null);
    setUpdateProfileRegion(false);
  }, [session]);

  useEffect(() => {
    let active = true;
    setRegionLoading(true);
    setError(null);
    Promise.all([
      getRegions(),
      getMyProfile().catch((loadError) => {
        if (loadError instanceof ApiError && loadError.status === 404) {
          return null;
        }
        throw loadError;
      }),
    ])
      .then(([nextRegions, nextProfile]) => {
        if (!active) return;
        setRegions(nextRegions);
        setProfile(nextProfile);
        setRegionId(nextProfile?.region_id ?? null);
      })
      .catch((loadError) => {
        if (active) setError(messageOf(loadError));
      })
      .finally(() => {
        if (active) setRegionLoading(false);
      });
    return () => {
      active = false;
    };
  }, [session]);

  const regionChanged = Boolean(
    profile && regionId && regionId !== profile.region_id,
  );

  async function pickPhotos() {
    if (submitting) return;
    setError(null);
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      setError('사진을 선택하려면 사진 보관함 접근 권한이 필요해요.');
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsMultipleSelection: true,
      selectionLimit: 2,
      quality: 0.8,
      exif: false,
    });
    if (!result.canceled) {
      setPhotos(result.assets.slice(0, 2));
    }
  }

  function removePhoto(index: number) {
    if (submitting) return;
    setPhotos((current) => current.filter((_, photoIndex) => photoIndex !== index));
  }

  async function submit() {
    if (submitting) return;
    if (photos.length < 1) {
      setError('사진을 1장 이상 선택해 주세요.');
      return;
    }
    if (!location.trim()) {
      setError('하자 위치를 입력해 주세요.');
      return;
    }
    if (!material.trim()) {
      setError('표면 재질을 입력해 주세요.');
      return;
    }
    if (!regionId) {
      setError('분석할 지역을 확인해 주세요.');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      if (updateProfileRegion && regionChanged && profile) {
        const saved = await saveMyProfile({
          nickname: profile.nickname,
          region_id: regionId,
          address: profile.address,
          housing_type: profile.housing_type,
        });
        setProfile(saved);
      }

      let targetRecordId = recordId;
      if (!targetRecordId) {
        const created = await createRecord();
        targetRecordId = created.record_id;
        setRecordId(targetRecordId);
      }

      const response = await analyzeRecord(targetRecordId, {
        photos: photos.map((photo, index) => ({
          uri: photo.uri,
          name: photo.fileName ?? `haja-${index + 1}.jpg`,
          type: photo.mimeType ?? 'image/jpeg',
          role: index === 0 ? 'overview' : 'closeup',
        })),
        location,
        material,
        symptoms,
        region_id: regionId,
        externalAnalysisConsent: consent,
      });

      router.replace({
        pathname: '/result/[recordId]',
        params: { recordId: response.record_id },
      });
    } catch (submitError) {
      setError(messageOf(submitError));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <SafeAreaView style={styles.screen}>
      <ScrollView contentContainerStyle={styles.form} keyboardShouldPersistTaps="handled">
        <View style={styles.headerRow}>
          <View style={styles.headerText}>
            <Text style={styles.title}>하자 분석</Text>
            <Text style={styles.subtitle}>사진과 정보를 한 번에 보내요.</Text>
          </View>
          <Pressable
            accessibilityRole="button"
            onPress={() => router.replace('/')}
            style={styles.textButton}
          >
            <Text style={styles.textButtonLabel}>홈</Text>
          </Pressable>
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>분석 지역 확인</Text>
          <Text style={styles.help}>
            분석 결과와 향후 요청서에 사용할 지역이에요. 현재 거주 지역을
            확인하고, 이번 분석에 다른 지역을 쓸 수 있어요.
          </Text>
          {regionLoading ? (
            <View style={styles.regionLoadingRow}>
              <ActivityIndicator />
              <Text style={styles.help}>지역을 불러오는 중…</Text>
            </View>
          ) : regions.length === 0 ? (
            <Text style={styles.error}>선택할 수 있는 지역이 없어요.</Text>
          ) : (
            <>
              <View style={styles.regionChips}>
                {regions.map((region) => {
                  const selected = region.region_id === regionId;
                  return (
                    <Pressable
                      key={region.region_id}
                      accessibilityRole="button"
                      accessibilityState={{ selected }}
                      disabled={submitting}
                      onPress={() => setRegionId(region.region_id)}
                      style={({ pressed }) => [
                        styles.chip,
                        selected && styles.chipSelected,
                        pressed && styles.pressed,
                      ]}
                    >
                      <Text
                        style={[
                          styles.chipText,
                          selected && styles.chipTextSelected,
                        ]}
                      >
                        {region.display_name}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
              {!profile ? (
                <Text style={styles.help}>
                  등록된 프로필이 없어 이번 분석에만 적용돼요.
                </Text>
              ) : null}
              {regionChanged ? (
                <View style={styles.regionToggleRow}>
                  <View style={styles.regionToggleText}>
                    <Text style={styles.label}>내 기본 거주 지역도 함께 변경</Text>
                    <Text style={styles.help}>
                      끄면 이번 분석에만 적용돼요.
                    </Text>
                  </View>
                  <Switch
                    value={updateProfileRegion}
                    onValueChange={setUpdateProfileRegion}
                    disabled={submitting}
                  />
                </View>
              ) : null}
            </>
          )}
        </View>

        <View style={styles.notice}>
          <Text style={styles.noticeTitle}>샘플 분석 안내</Text>
          <Text style={styles.noticeText}>
            현재는 실제 사진 분석 모델을 호출하지 않아요. 입력한 위치·재질·증상으로
            만든 샘플 결과이며, 실제 사진 평가나 현장 점검 결과가 아닙니다.
          </Text>
        </View>

        <Text style={styles.label}>사진 (1~2장)</Text>
        <Text style={styles.help}>
          첫 번째 사진은 전체, 두 번째 사진은 근접 사진으로 전송돼요.
        </Text>
        <View style={styles.photoRow}>
          {photos.map((photo, index) => (
            <View key={`${photo.uri}-${index}`} style={styles.photoCard}>
              <Image source={{ uri: photo.uri }} style={styles.photo} />
              <Text style={styles.photoRole}>
                {index === 0 ? '전체 사진' : '근접 사진'}
              </Text>
              <Pressable
                accessibilityRole="button"
                disabled={submitting}
                onPress={() => removePhoto(index)}
                style={styles.removeButton}
              >
                <Text style={styles.removeButtonText}>삭제</Text>
              </Pressable>
            </View>
          ))}
        </View>
        <Pressable
          accessibilityRole="button"
          disabled={submitting}
          onPress={pickPhotos}
          style={({ pressed }) => [
            styles.secondaryButton,
            submitting && styles.disabled,
            pressed && styles.pressed,
          ]}
        >
          <Text style={styles.secondaryButtonText}>
            {photos.length === 0 ? '사진 선택' : '사진 다시 선택'}
          </Text>
        </Pressable>

        <Text style={styles.label}>발견 위치 *</Text>
        <TextInput
          value={location}
          onChangeText={setLocation}
          editable={!submitting}
          style={styles.input}
          placeholder="예: 안방 창틀 아래"
          placeholderTextColor="#8A8F98"
        />

        <Text style={styles.label}>표면 재질 *</Text>
        <TextInput
          value={material}
          onChangeText={setMaterial}
          editable={!submitting}
          style={styles.input}
          placeholder="예: 실리콘, 벽지, 도장면"
          placeholderTextColor="#8A8F98"
        />

        <Text style={styles.label}>증상 메모 (선택)</Text>
        <TextInput
          value={symptoms}
          onChangeText={setSymptoms}
          editable={!submitting}
          multiline
          style={[styles.input, styles.multiline]}
          placeholder="예: 닦아도 검은 얼룩이 다시 생겨요"
          placeholderTextColor="#8A8F98"
        />

        <View style={styles.consentRow}>
          <View style={styles.consentText}>
            <Text style={styles.label}>외부 분석 동의</Text>
            <Text style={styles.help}>
              현재 샘플 모드에서는 동의 여부와 관계없이 외부 AI로 사진을 보내지
              않아요.
            </Text>
          </View>
          <Switch
            value={consent}
            onValueChange={setConsent}
            disabled={submitting}
          />
        </View>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Pressable
          accessibilityRole="button"
          disabled={submitting || photos.length === 0 || !regionId || regionLoading}
          onPress={submit}
          style={({ pressed }) => [
            styles.primaryButton,
            (submitting || photos.length === 0 || !regionId || regionLoading) &&
              styles.disabled,
            pressed && styles.pressed,
          ]}
        >
          {submitting ? (
            <View style={styles.submittingRow}>
              <ActivityIndicator color="#FFFFFF" />
              <Text style={styles.primaryButtonText}>분석 중…</Text>
            </View>
          ) : (
            <Text style={styles.primaryButtonText}>분석하기</Text>
          )}
        </Pressable>
        {error ? (
          <Text style={styles.help}>
            같은 기록으로 다시 분석할 수 있어요. 분석 버튼을 다시 눌러 주세요.
          </Text>
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
  form: {
    flexGrow: 1,
    gap: 10,
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
  regionLoadingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  regionChips: {
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
  regionToggleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  regionToggleText: {
    flex: 1,
    gap: 2,
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
  label: {
    marginTop: 6,
    fontSize: 14,
    fontWeight: '600',
    color: '#15171A',
  },
  help: {
    fontSize: 13,
    lineHeight: 19,
    color: '#60646C',
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
  multiline: {
    minHeight: 90,
    textAlignVertical: 'top',
  },
  photoRow: {
    flexDirection: 'row',
    gap: 10,
  },
  photoCard: {
    flex: 1,
    borderRadius: 12,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E2E4E8',
    padding: 8,
    gap: 4,
  },
  photo: {
    width: '100%',
    aspectRatio: 1,
    borderRadius: 8,
    backgroundColor: '#EEF0F3',
  },
  photoRole: {
    fontSize: 13,
    fontWeight: '600',
    color: '#4E535C',
  },
  removeButton: {
    alignSelf: 'flex-start',
    paddingVertical: 2,
  },
  removeButtonText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#C0392B',
  },
  secondaryButton: {
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 46,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#208AEF',
    backgroundColor: '#FFFFFF',
  },
  secondaryButtonText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#208AEF',
  },
  consentRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginTop: 4,
  },
  consentText: {
    flex: 1,
    gap: 2,
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
  submittingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
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
