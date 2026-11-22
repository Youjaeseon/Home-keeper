import { router } from 'expo-router';
import { ChevronRight, Clock, LogOut } from 'lucide-react-native';
import { Pressable, StyleSheet, View } from 'react-native';

import { Select } from '@/components/select';
import { AppBar, Button, Card, CardHeader, Chip, DeleteButton, Field, Screen, Txt } from '@/components/ui';
import { C, STROKE } from '@/constants/theme';
import { HOUSINGS, REGIONS } from '@/data/options';
import { useApp } from '@/store/app-store';
import type { Role } from '@/types';

const ROLES: Role[] = ['유저', '업체'];

/** 스케치 3: 사용자 정보 — 회원 유형(유저/업체), 별명, 거주지역, 거주형태 */
export default function ProfileScreen() {
  const { user, updateUser, logout, analyses, removeAnalysis } = useApp();
  if (!user) return null;

  const vendor = user.role === '업체';

  return (
    <Screen safeTop>
      <AppBar title="프로필" />

      <View style={s.profile}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          <Txt variant="title">{user.nickname}</Txt>
          <Chip label={user.role} active={vendor} />
        </View>
        <Txt variant="sub" muted>
          {vendor ? `${user.region} · 견적서를 받는 업체` : `${user.region} · ${user.housing}`}
        </Txt>
      </View>

      <Card>
        <Select label="회원 유형" value={user.role} options={ROLES} onChange={(role) => updateUser({ role })} />
        <Field
          label={vendor ? '업체명' : '별명'}
          value={user.nickname}
          onChangeText={(nickname) => updateUser({ nickname })}
        />
        <Select
          label={vendor ? '활동지역' : '거주지역'}
          value={user.region}
          options={REGIONS}
          onChange={(region) => updateUser({ region })}
        />
        {vendor ? (
          <Field
            label="업체 소개"
            value={user.intro ?? ''}
            onChangeText={(intro) => updateUser({ intro })}
            placeholder="예: 욕실 곰팡이 제거 전문"
          />
        ) : (
          <Select label="거주형태" value={user.housing} options={HOUSINGS} onChange={(housing) => updateUser({ housing })} />
        )}
      </Card>

      {analyses.length > 0 && (
        <Card style={{ gap: 4 }}>
          <CardHeader icon={Clock} title="내 분석 기록" />
          {analyses.map((a) => (
            <Pressable
              key={a.id}
              accessibilityRole="button"
              onPress={() => router.push({ pathname: '/analyze/result', params: { analysisId: a.id } })}
              style={({ pressed }) => [s.historyRow, pressed && { opacity: 0.7 }]}>
              <View style={{ flex: 1 }}>
                <Txt variant="bodyStrong">
                  {a.location} · {a.defect}
                </Txt>
                <Txt variant="caption" muted>
                  {a.occurredAt}
                  {a.needsRetake ? ' · 재촬영 필요' : ` · 위험도 ${a.risk}%`}
                </Txt>
              </View>
              <DeleteButton label="분석 기록" onDelete={() => removeAnalysis(a.id)} />
              <ChevronRight size={18} color={C.faint} strokeWidth={STROKE} />
            </Pressable>
          ))}
        </Card>
      )}

      <Button
        title="로그아웃"
        variant="outline"
        icon={LogOut}
        style={{ marginTop: 8 }}
        onPress={() => {
          logout();
          router.replace('/');
        }}
      />
    </Screen>
  );
}

const s = StyleSheet.create({
  profile: { gap: 6, paddingVertical: 12 },
  historyRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    minHeight: 58,
    borderTopWidth: 1,
    borderTopColor: C.border,
  },
});
