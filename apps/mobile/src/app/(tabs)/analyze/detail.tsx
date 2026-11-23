import { router, useLocalSearchParams } from 'expo-router';
import { Check, Sparkles } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Animated, Easing, Platform, Pressable, StyleSheet, View } from 'react-native';

import { DefectPhoto } from '@/components/defect-photo';
import { Select } from '@/components/select';
import { Button, Card, Field, Screen, Txt } from '@/components/ui';
import { C } from '@/constants/theme';
import { LOCATIONS, MATERIALS, POSITIONS } from '@/data/options';
import { messageOf } from '@/lib/api';
import { ANALYSIS_STEPS, analyzeDefect } from '@/services/analyze';
import { useApp } from '@/store/app-store';
import { today } from '@/utils';

/** 스케치 6: 분석 Page ② — 분석 사진 정보 기입 (장소, 위치, 기타) → 분석 요청 */
export default function AnalyzeDetailScreen() {
  // 샘플 사진에서 오면 장소·위치·재질이 미리 채워져 옵니다.
  const params = useLocalSearchParams<{ photoId: string; location?: string; position?: string; material?: string }>();
  const { photoId } = params;
  const preset = (value: string | undefined, list: string[]) => (value && list.includes(value) ? value : list[0]);
  const { photos, user, saveAnalysis } = useApp();
  const photo = photos.find((p) => p.id === photoId);

  const [location, setLocation] = useState(preset(params.location, LOCATIONS));
  const [position, setPosition] = useState(preset(params.position, POSITIONS));
  // 백엔드 analyze는 재질(material)이 필수입니다. (GAP-006)
  const [material, setMaterial] = useState(preset(params.material, MATERIALS));
  // '기타'를 고르면 직접 입력합니다. (GAP-006, GAP-013)
  const [customLocation, setCustomLocation] = useState('');
  const [customPosition, setCustomPosition] = useState('');
  const [customMaterial, setCustomMaterial] = useState('');
  const [memo, setMemo] = useState('');
  // 분석 요청마다 외부 AI 사진 전송 동의를 받습니다. 기본은 동의하지 않음입니다. (GAP-011)
  const [consent, setConsent] = useState(false);
  const [step, setStep] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!photo || !user) {
    return (
      <Screen>
        <Txt variant="h2">사진을 찾을 수 없습니다.</Txt>
        <Button title="사진 다시 선택" onPress={() => router.replace('/analyze')} />
      </Screen>
    );
  }

  const OTHER = '기타';
  const resolve = (value: string, custom: string) => (value === OTHER ? custom.trim() : value);

  const onAnalyze = async () => {
    setError(null);
    const finalLocation = resolve(location, customLocation);
    const finalPosition = resolve(position, customPosition);
    const finalMaterial = resolve(material, customMaterial);
    if (!finalLocation || !finalPosition || !finalMaterial) {
      setError("'기타'를 고른 칸은 직접 입력해 주세요.");
      return;
    }
    try {
      const result = await analyzeDefect(
        {
          photo,
          location: finalLocation,
          position: finalPosition,
          material: finalMaterial,
          occurredAt: today(),
          memo,
          housing: user.housing,
          regionId: user.regionId,
          consent,
        },
        setStep,
      );
      saveAnalysis(result);
      router.replace({ pathname: '/analyze/result', params: { analysisId: result.id } });
    } catch (e) {
      setError(messageOf(e) || '분석 서버에 연결하지 못했습니다. 네트워크를 확인하고 다시 시도해 주세요.');
    } finally {
      setStep(null);
    }
  };

  const analyzing = step !== null;

  return (
    <Screen>
      <DefectPhoto uri={photo.uri} size={200} />

      <Card>
        <Select label="장소" value={location} options={LOCATIONS} onChange={setLocation} />
        {location === OTHER && (
          <Field label="장소 직접 입력" value={customLocation} onChangeText={setCustomLocation} placeholder="예: 작은방" />
        )}
        <Select label="위치" value={position} options={POSITIONS} onChange={setPosition} />
        {position === OTHER && (
          <Field label="위치 직접 입력" value={customPosition} onChangeText={setCustomPosition} placeholder="예: 문틀 옆" />
        )}
        <Select label="재질" value={material} options={MATERIALS} onChange={setMaterial} />
        {material === OTHER && (
          <Field label="재질 직접 입력" value={customMaterial} onChangeText={setCustomMaterial} placeholder="예: 원목 문틀" />
        )}
        <Field
          label="기타"
          value={memo}
          onChangeText={setMemo}
          placeholder="예: 비 온 다음 날 더 번져요"
          multiline
          style={{ minHeight: 88, paddingTop: 14, textAlignVertical: 'top' }}
        />
        <Pressable
          accessibilityRole="checkbox"
          accessibilityState={{ checked: consent }}
          accessibilityLabel="외부 AI 사진 분석 동의"
          onPress={() => setConsent((v) => !v)}
          style={s.agree}>
          <View style={[s.box, consent && s.boxOn]}>{consent && <Check size={15} color={C.onPrimary} strokeWidth={3} />}</View>
          <Txt variant="sub" color={C.text} style={{ flex: 1 }}>
            이 사진을 외부 AI(비전 LLM·Meta SAM)로 보내 분석하는 데 동의해요. 동의하지 않으면 사진을 외부로 보내지 않아 분석이 제한될 수 있어요.
          </Txt>
        </Pressable>
        {error && (
          <Txt variant="sub" color={C.danger}>
            {error}
          </Txt>
        )}
      </Card>

      {analyzing && (
        <Card style={{ gap: 14, backgroundColor: C.accent }}>
          <Txt variant="h2">AI 분석 중</Txt>
          {ANALYSIS_STEPS.map((label, i) => {
            const done = i < step;
            const now = i === step;
            return (
              <View key={label} style={s.stepRow}>
                <View style={s.stepSlot}>
                  {now && <SpinRing />}
                  <View style={[s.stepDot, (done || now) && { backgroundColor: C.primary }]}>
                    {done ? (
                      <Check size={14} color={C.onPrimary} strokeWidth={2.4} />
                    ) : (
                      <Txt variant="caption" color={now ? C.onPrimary : C.sub}>
                        {i + 1}
                      </Txt>
                    )}
                  </View>
                </View>
                <Txt variant={now ? 'bodyStrong' : 'body'} color={done || now ? C.text : C.sub}>
                  {label}
                </Txt>
              </View>
            );
          })}
        </Card>
      )}

      <Button title={analyzing ? '분석 중...' : '분석 요청'} icon={Sparkles} onPress={onAnalyze} loading={analyzing} />
    </Screen>
  );
}

/** 진행 중인 단계 번호 주변을 도는 로딩 고리 (iOS·Android·웹 공통, Animated) */
function SpinRing() {
  const [spin] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const loop = Animated.loop(
      Animated.timing(spin, {
        toValue: 1,
        duration: 900,
        easing: Easing.linear,
        useNativeDriver: Platform.OS !== 'web',
      }),
    );
    loop.start();
    return () => loop.stop();
  }, [spin]);
  const rotate = spin.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] });
  return <Animated.View pointerEvents="none" style={[s.ring, { transform: [{ rotate }] }]} />;
}

const s = StyleSheet.create({
  stepSlot: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
  ring: {
    position: 'absolute',
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 3,
    borderColor: 'transparent',
    borderTopColor: C.primary,
    borderRightColor: C.primary,
  },
  agree: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  box: {
    width: 24,
    height: 24,
    borderRadius: 8,
    borderWidth: 2,
    borderColor: C.faint,
    backgroundColor: C.card,
    alignItems: 'center',
    justifyContent: 'center',
  },
  boxOn: { backgroundColor: C.primary, borderColor: C.primary },
  stepRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  stepDot: {
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: C.accentCircle,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
