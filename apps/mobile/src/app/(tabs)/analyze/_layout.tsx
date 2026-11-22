import { Stack } from 'expo-router';

import { stackHeader } from '@/constants/navigation';

/** 분석 탭 안의 화면 흐름: 사진 선택 → 정보 기입 → 결과 */
export default function AnalyzeLayout() {
  return (
    <Stack screenOptions={stackHeader}>
      <Stack.Screen name="index" options={{ headerShown: false }} />
      <Stack.Screen name="detail" options={{ title: '분석 정보 기입' }} />
      <Stack.Screen name="result" options={{ title: '분석 결과' }} />
    </Stack>
  );
}
