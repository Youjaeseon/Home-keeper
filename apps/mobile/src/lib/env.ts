function required(name: string, value: string | undefined): string {
  const trimmed = value?.trim();
  if (!trimmed) {
    throw new Error(
      `${name} is not set. Copy apps/mobile/.env.example to apps/mobile/.env and fill it in.`,
    );
  }
  return trimmed.replace(/\/+$/, '');
}

export const apiBaseUrl = required(
  'EXPO_PUBLIC_API_URL',
  process.env.EXPO_PUBLIC_API_URL,
);

export const supabaseUrl = required(
  'EXPO_PUBLIC_SUPABASE_URL',
  process.env.EXPO_PUBLIC_SUPABASE_URL,
);

export const supabaseKey = required(
  'EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY',
  process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
);

/**
 * 심사·시연용 데모 계정. 첫 화면의 "데모 계정으로 둘러보기" 버튼이 이 계정으로 자동 로그인합니다.
 * EXPO_PUBLIC_ 값은 앱 번들에 그대로 들어가므로 다른 곳에서 쓰지 않는 체험 전용 비밀번호만 넣으세요.
 */
export const demoLoginId = process.env.EXPO_PUBLIC_DEMO_LOGIN_ID?.trim() ?? '';
export const demoPassword = process.env.EXPO_PUBLIC_DEMO_PASSWORD ?? '';
