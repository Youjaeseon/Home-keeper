import { C, F } from '@/constants/theme';

/** 아이보리 헤더 공통 옵션 (Stack 화면용) */
export const stackHeader = {
  headerStyle: { backgroundColor: C.bg },
  headerTintColor: C.text,
  headerTitleStyle: { fontFamily: F.bold, fontSize: 17 },
  headerShadowVisible: false,
  headerTitleAlign: 'center',
  headerBackTitle: '뒤로',
  contentStyle: { backgroundColor: C.bg },
} as const;
