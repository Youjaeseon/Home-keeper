import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';

import { stackHeader } from '@/constants/navigation';
import { F } from '@/constants/theme';
import { AppProvider } from '@/store/app-store';

SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const [loaded, error] = useFonts({
    [F.light]: require('@/assets/fonts/Pretendard-Light.otf'),
    [F.regular]: require('@/assets/fonts/Pretendard-Regular.otf'),
    [F.medium]: require('@/assets/fonts/Pretendard-Medium.otf'),
    [F.semibold]: require('@/assets/fonts/Pretendard-SemiBold.otf'),
    [F.bold]: require('@/assets/fonts/Pretendard-Bold.otf'),
    [F.extrabold]: require('@/assets/fonts/Pretendard-ExtraBold.otf'),
  });

  useEffect(() => {
    if (loaded || error) SplashScreen.hideAsync();
  }, [loaded, error]);

  // 폰트 로딩 실패 시에도 시스템 폰트로 계속 진행합니다.
  if (!loaded && !error) return null;

  return (
    <AppProvider>
      <StatusBar style="dark" />
      <Stack screenOptions={stackHeader}>
        <Stack.Screen name="index" options={{ headerShown: false }} />
        <Stack.Screen name="signup" options={{ title: '' }} />
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="dm/index" options={{ title: '채팅 목록' }} />
        <Stack.Screen name="dm/[vendorId]" options={{ title: '대화' }} />
      </Stack>
    </AppProvider>
  );
}
