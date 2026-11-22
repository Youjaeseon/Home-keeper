import { Trash2 } from 'lucide-react-native';
import { type ComponentRef, type ComponentType, type ReactNode, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  type StyleProp,
  type TextInputProps,
  type TextProps,
  type TextStyle,
  type ViewStyle,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { LogoMark, LogoWordmark } from '@/components/logo';
import { C, F, MAX_W, R, STROKE } from '@/constants/theme';

/** lucide 선 아이콘 컴포넌트 타입 */
export type Icon = ComponentType<{ size?: number; color?: string; strokeWidth?: number }>;

/* ───────── 글씨 ───────── */

const VARIANTS = {
  display: { fontFamily: F.extrabold, fontSize: 28, lineHeight: 37, letterSpacing: -0.6 },
  title: { fontFamily: F.extrabold, fontSize: 21, lineHeight: 29, letterSpacing: -0.4 },
  h2: { fontFamily: F.bold, fontSize: 17, lineHeight: 24, letterSpacing: -0.3 },
  body: { fontFamily: F.regular, fontSize: 15, lineHeight: 23 },
  bodyStrong: { fontFamily: F.semibold, fontSize: 15, lineHeight: 23 },
  label: { fontFamily: F.semibold, fontSize: 13, lineHeight: 18 },
  sub: { fontFamily: F.regular, fontSize: 14, lineHeight: 20 },
  caption: { fontFamily: F.medium, fontSize: 12, lineHeight: 16 },
} satisfies Record<string, TextStyle>;

export type TxtVariant = keyof typeof VARIANTS;

/** 모든 글씨는 Txt로 씁니다. muted: 보조 글씨 */
export function Txt({
  variant = 'body',
  muted,
  color,
  style,
  ...props
}: TextProps & { variant?: TxtVariant; muted?: boolean; color?: string }) {
  return <Text {...props} style={[VARIANTS[variant], { color: color ?? (muted ? C.sub : C.text) }, style]} />;
}

/* ───────── 화면 틀 ───────── */

/** safeTop: 헤더 없는 탭 화면에서 상태바 영역만큼 띄웁니다. */
/**
 * scrollKey가 바뀌면(예: 다른 분석 기록 열기) 맨 위로 이동합니다.
 * 입력창을 누르면 키보드에 가리지 않게 화면을 올립니다(iOS automaticallyAdjustKeyboardInsets).
 */
export function Screen({
  children,
  safeTop,
  scrollKey,
  onRefresh,
}: {
  children: ReactNode;
  safeTop?: boolean;
  scrollKey?: string;
  /** 있으면 아래로 당겨서 새로고침합니다. 끝날 때까지 로딩 표시가 돕니다. */
  onRefresh?: () => Promise<unknown>;
}) {
  const insets = useSafeAreaInsets();
  const ref = useRef<ComponentRef<typeof ScrollView>>(null);
  const [refreshing, setRefreshing] = useState(false);
  const pull = onRefresh
    ? () => {
        setRefreshing(true);
        void onRefresh()
          .catch(() => null)
          .finally(() => setRefreshing(false));
      }
    : undefined;
  // scrollKey가 바뀌면 맨 위로 갑니다. 내용(사진·업체 목록 등)이 늦게 그려지며 위치가 바뀔 수 있어
  // 잠깐 동안은 내용 크기가 바뀔 때마다 다시 맨 위로 맞춥니다.
  const pinTop = useRef(false);
  useEffect(() => {
    if (scrollKey === undefined) return;
    pinTop.current = true;
    ref.current?.scrollTo({ y: 0, animated: false });
    const timer = setTimeout(() => {
      pinTop.current = false;
    }, 1200);
    return () => clearTimeout(timer);
  }, [scrollKey]);
  return (
    <ScrollView
      ref={ref}
      refreshControl={
        pull ? <RefreshControl refreshing={refreshing} onRefresh={pull} tintColor={C.primary} colors={[C.primary]} /> : undefined
      }
      automaticallyAdjustKeyboardInsets
      onContentSizeChange={() => {
        if (pinTop.current) ref.current?.scrollTo({ y: 0, animated: false });
      }}
      style={s.root}
      contentContainerStyle={{ flexGrow: 1, paddingBottom: 32, paddingTop: safeTop ? insets.top : 0 }}
      keyboardShouldPersistTaps="handled"
      showsVerticalScrollIndicator={false}>
      <View style={s.inner}>{children}</View>
    </ScrollView>
  );
}

/** 탭 화면 상단: 로고 + 페이지 제목 */
export function AppBar({ title }: { title: string }) {
  return (
    <View style={s.appBar}>
      <LogoWordmark size={28} title={title} />
    </View>
  );
}

/** 큰 제목 블록 */
export function Hero({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <View style={{ gap: 8, paddingTop: 8, paddingBottom: 6 }}>
      <Txt variant="display">{title}</Txt>
      {subtitle && <Txt variant="sub" muted>{subtitle}</Txt>}
    </View>
  );
}

/** 초록 배너: 캐릭터 몸 색 바탕 + 오른쪽에 로고 이미지 */
export function Banner({
  title,
  subtitle,
  icon: IconCmp,
  onPress,
}: {
  title: string;
  subtitle?: string;
  icon: Icon;
  onPress?: () => void;
}) {
  return (
    <Pressable
      accessibilityRole={onPress ? 'button' : undefined}
      onPress={onPress}
      disabled={!onPress}
      style={({ pressed }) => [s.banner, pressed && { opacity: 0.9 }]}>
      <View style={{ flex: 1, gap: 6, paddingRight: 88 }}>
        <View style={s.bannerIcon}>
          <IconCmp size={20} color={C.primary} strokeWidth={STROKE} />
        </View>
        {/* 한 줄 고정: 좁은 폰에서는 글자를 줄여 마지막 글자만 떨어지는 줄바꿈을 막습니다. */}
        <Txt variant="title" color={C.onPrimary} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7}>
          {title}
        </Txt>
        {subtitle && (
          <Txt variant="sub" color={C.onPrimary} style={{ opacity: 0.85 }}>
            {subtitle}
          </Txt>
        )}
      </View>
      <View style={s.bannerMascot} pointerEvents="none">
        <LogoMark size={80} radius={0.28} />
      </View>
    </Pressable>
  );
}

/* ───────── 카드 ───────── */

export function Card({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[s.card, style]}>{children}</View>;
}

export function CardHeader({ icon: IconCmp, title }: { icon: Icon; title: string }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
      <View style={s.iconBadge}>
        <IconCmp size={17} color={C.primary} strokeWidth={STROKE} />
      </View>
      <Txt variant="h2" style={{ flex: 1 }}>
        {title}
      </Txt>
    </View>
  );
}

/** 크림 둥근 사각 아이콘 + 아래 라벨 (빠른 메뉴) */
export function IconTile({ icon: IconCmp, label, onPress }: { icon: Icon; label: string; onPress?: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={onPress}
      style={({ pressed }) => [{ alignItems: 'center', gap: 8, flex: 1 }, pressed && { opacity: 0.7 }]}>
      <View style={s.tile}>
        <IconCmp size={22} color={C.text} strokeWidth={STROKE} />
      </View>
      <Txt variant="sub" color={C.text}>
        {label}
      </Txt>
    </Pressable>
  );
}

/* ───────── 버튼 ───────── */

export function Button({
  title,
  onPress,
  variant = 'primary',
  icon: IconCmp,
  disabled,
  loading,
  style,
}: {
  title: string;
  onPress: () => void;
  variant?: 'primary' | 'outline' | 'soft' | 'ghost';
  icon?: Icon;
  disabled?: boolean;
  loading?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  const v = BTN[variant];
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={title}
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        s.btn,
        v.box,
        (disabled || loading) && { opacity: 0.55 },
        pressed && { opacity: 0.88 },
        style,
      ]}>
      {loading ? (
        <ActivityIndicator color={v.fg} />
      ) : (
        <>
          {IconCmp && <IconCmp size={19} color={v.fg} strokeWidth={STROKE} />}
          <Text style={[s.btnText, { color: v.fg }]}>{title}</Text>
        </>
      )}
    </Pressable>
  );
}

const BTN: Record<string, { box: ViewStyle; fg: string }> = {
  primary: { box: { backgroundColor: C.primary }, fg: C.onPrimary },
  outline: { box: { borderWidth: 2, borderColor: C.primary, backgroundColor: C.card }, fg: C.primary },
  soft: { box: { backgroundColor: C.accentSoft }, fg: C.primary },
  ghost: { box: {}, fg: C.primary },
};

/* ───────── 입력 ───────── */

export function Field({ label, style, ...props }: { label: string } & TextInputProps) {
  return (
    <View style={{ gap: 8 }}>
      <Txt variant="label" muted>
        {label}
      </Txt>
      <TextInput placeholderTextColor={C.faint} style={[s.input, style]} {...props} />
    </View>
  );
}

/* ───────── 안내 박스 ───────── */

export function Notice({ children, icon: IconCmp, tone = 'soft' }: { children: ReactNode; icon: Icon; tone?: 'soft' | 'warn' }) {
  const t = tone === 'warn' ? { bg: C.warnSoft, fg: C.warnText } : { bg: C.accentSoft, fg: C.text };
  return (
    <View style={[s.notice, { backgroundColor: t.bg }]}>
      <IconCmp size={17} color={t.fg} strokeWidth={STROKE} />
      <Txt variant="sub" color={t.fg} style={{ flex: 1 }}>
        {children}
      </Txt>
    </View>
  );
}

export function Chip({
  label,
  active,
  onPress,
}: {
  label: string;
  active?: boolean;
  onPress?: () => void;
}) {
  const chipStyle = [s.chip, active && { backgroundColor: C.primary }];
  const content = (
    <Txt variant="caption" color={active ? C.onPrimary : C.primary}>
      {label}
    </Txt>
  );
  if (!onPress) return <View style={chipStyle}>{content}</View>;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected: !!active }}
      hitSlop={6}
      onPress={onPress}
      style={({ pressed }) => [...chipStyle, pressed && { opacity: 0.7 }]}>
      {content}
    </Pressable>
  );
}

/** 지우기 버튼: 한 번 누르면 "삭제"로 바뀌고, 한 번 더 눌러야 지워집니다. 3초 안에 안 누르면 원래대로 돌아갑니다. */
export function DeleteButton({ onDelete, label }: { onDelete: () => void; label: string }) {
  const [armed, setArmed] = useState(false);
  useEffect(() => {
    if (!armed) return;
    const t = setTimeout(() => setArmed(false), 3000);
    return () => clearTimeout(t);
  }, [armed]);
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={armed ? `${label} 삭제 확인` : `${label} 삭제`}
      hitSlop={10}
      onPress={() => (armed ? onDelete() : setArmed(true))}
      style={[s.del, armed && { backgroundColor: C.danger, paddingHorizontal: 12 }]}>
      {armed ? (
        <Txt variant="caption" color={C.onPrimary} style={{ fontFamily: F.bold }}>
          삭제
        </Txt>
      ) : (
        <Trash2 size={16} color={C.faint} strokeWidth={STROKE} />
      )}
    </Pressable>
  );
}

/** 캐릭터처럼 납작한 스타일이라 그림자는 쓰지 않습니다. (기존 코드 호환용으로 남겨 둠) */
export const shadow = {} as const;

export const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  del: { minWidth: 30, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center' },
  inner: { flex: 1, width: '100%', maxWidth: MAX_W, alignSelf: 'center', paddingHorizontal: 24, paddingTop: 8, gap: 16 },
  appBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingTop: 8, paddingBottom: 4 },
  banner: {
    backgroundColor: C.primary,
    borderRadius: R.card,
    padding: 24,
    minHeight: 160,
    flexDirection: 'row',
    alignItems: 'center',
    overflow: 'hidden',
  },
  bannerIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: C.onPrimary,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 4,
  },
  bannerMascot: { position: 'absolute', right: 20, top: 0, bottom: 0, justifyContent: 'center' },
  card: { backgroundColor: C.card, borderRadius: R.card, padding: 22, gap: 12 },
  iconBadge: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: C.accentSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tile: {
    width: 56,
    height: 56,
    borderRadius: R.tile,
    backgroundColor: C.card,
    alignItems: 'center',
    justifyContent: 'center',
  },
  btn: {
    minHeight: 56,
    borderRadius: R.button,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    gap: 8,
    paddingHorizontal: 18,
  },
  btnText: { fontFamily: F.bold, fontSize: 16, letterSpacing: -0.2 },
  input: {
    minHeight: 52,
    borderRadius: R.field,
    paddingHorizontal: 16,
    fontSize: 16,
    fontFamily: F.medium,
    color: C.text,
    backgroundColor: C.field,
    borderWidth: 1.5,
    borderColor: C.border,
  },
  notice: { flexDirection: 'row', gap: 10, borderRadius: R.tile, padding: 16, alignItems: 'flex-start' },
  chip: {
    backgroundColor: C.accentSoft,
    borderRadius: R.pill,
    paddingHorizontal: 12,
    paddingVertical: 5,
    alignSelf: 'flex-start',
  },
});
