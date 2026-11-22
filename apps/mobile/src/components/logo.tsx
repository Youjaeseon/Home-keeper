import { Image } from 'expo-image';
import { Text, View } from 'react-native';

import { C, F } from '@/constants/theme';

/** 확정된 마스코트 로고 이미지 (크림 배경 + 초록 집 캐릭터) */
export const LOGO_IMAGE = require('@/assets/images/mascot-logo.png');

/** 로고 이미지. radius는 size 대비 둥글기 비율입니다. */
export function LogoMark({ size = 48, radius = 0.26 }: { size?: number; radius?: number }) {
  return (
    <Image
      source={LOGO_IMAGE}
      accessibilityLabel="집사 로고"
      style={{ width: size, height: size, borderRadius: size * radius }}
      contentFit="cover"
    />
  );
}

/** 로고 + 페이지 제목 (각 탭 상단 바) */
export function LogoWordmark({ size = 28, title }: { size?: number; title: string }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
      <LogoMark size={size} />
      <Text style={{ fontFamily: F.extrabold, fontSize: size * 0.68, color: C.text, letterSpacing: -0.4 }}>{title}</Text>
    </View>
  );
}
