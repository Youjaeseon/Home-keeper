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
