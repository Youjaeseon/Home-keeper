import { router } from 'expo-router';
import { MessageCircle } from 'lucide-react-native';
import { Pressable } from 'react-native';

import { C, STROKE } from '@/constants/theme';

/** 스케치 우측 상단의 "DM" 버튼 (크림 원형, 그림자 없음) */
export function DmButton() {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="DM 메시지함"
      hitSlop={8}
      onPress={() => router.push('/dm')}
      style={({ pressed }) => [
        {
          width: 46,
          height: 46,
          borderRadius: 23,
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: C.card,
        },
        pressed && { opacity: 0.7 },
      ]}>
      <MessageCircle size={21} color={C.text} strokeWidth={STROKE} />
    </Pressable>
  );
}
