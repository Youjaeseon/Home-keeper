import { router, useLocalSearchParams } from 'expo-router';
import { Check, Sparkles } from 'lucide-react-native';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { DefectPhoto } from '@/components/defect-photo';
import { Select } from '@/components/select';
import { Button, Card, Field, Screen, Txt } from '@/components/ui';
import { C } from '@/constants/theme';
import { LOCATIONS, POSITIONS } from '@/data/options';
import { ANALYSIS_STEPS, analyzeDefect } from '@/services/analyze';
import { useApp } from '@/store/app-store';
import { today } from '@/utils';

/** 스케치 6: 분석 Page ② — 분석 사진 정보 기입 (장소, 위치, 기타) → 분석 요청 */
export default function AnalyzeDetailScreen() {
  const { photoId } = useLocalSearchParams<{ photoId: string }>();
  const { photos, user, saveAnalysis } = useApp();
  const photo = photos.find((p) => p.id === photoId);

  const [location, setLocation] = useState(LOCATIONS[0]);
  const [position, setPosition] = useState(POSITIONS[0]);
  const [memo, setMemo] = useState('');
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

  const onAnalyze = async () => {
    setError(null);
    try {
      const result = await analyzeDefect(
        { photo, location, position, occurredAt: today(), memo, housing: user.housing },
        setStep,
      );
      saveAnalysis(result);
      router.replace({ pathname: '/analyze/result', params: { analysisId: result.id } });
    } catch {
      setError('분석 서버에 연결하지 못했습니다. 네트워크를 확인하고 다시 시도해 주세요.');
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
        <Select label="위치" value={position} options={POSITIONS} onChange={setPosition} />
        <Field
          label="기타"
          value={memo}
          onChangeText={setMemo}
          placeholder="예: 비 온 다음 날 더 번져요"
          multiline
          style={{ minHeight: 88, paddingTop: 14, textAlignVertical: 'top' }}
        />
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
                <View style={[s.stepDot, (done || now) && { backgroundColor: C.primary }]}>
                  {done ? (
                    <Check size={14} color={C.onPrimary} strokeWidth={2.4} />
                  ) : (
                    <Txt variant="caption" color={now ? C.onPrimary : C.sub}>
                      {i + 1}
                    </Txt>
                  )}
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

const s = StyleSheet.create({
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
