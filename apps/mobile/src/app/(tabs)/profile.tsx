import { router } from 'expo-router';
import { ChevronRight, Clock, LogOut } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { Select } from '@/components/select';
import { AppBar, Button, Card, CardHeader, Chip, DeleteButton, Field, Screen, Txt } from '@/components/ui';
import { C, STROKE } from '@/constants/theme';
import { HOUSINGS } from '@/data/options';
import { useApp } from '@/store/app-store';

/** 스케치 3: 사용자 정보 — 회원 유형(유저/업체), 별명, 거주지역, 거주형태 */
export default function ProfileScreen() {
  const { user, regions, updateUser, logout, analyses, removeAnalysis } = useApp();
  const [nickname, setNickname] = useState(user?.nickname ?? '');
  const [error, setError] = useState<string | null>(null);
  useEffect(() => setNickname(user?.nickname ?? ''), [user?.nickname]);
  if (!user) return null;

  const save = async (patch: Parameters<typeof updateUser>[0]) => setError(await updateUser(patch));

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
        {/* 회원 유형은 서버가 정합니다(가입 시 유저, 업체는 사전 등록). TODO(integration-gap): GAP-003 */}
        <Field label="회원 유형" value={user.role} editable={false} />
        <Field
          label={vendor ? '업체명' : '별명'}
          value={nickname}
          onChangeText={setNickname}
          onEndEditing={() => nickname.trim() !== user.nickname && save({ nickname })}
          onSubmitEditing={() => nickname.trim() !== user.nickname && save({ nickname })}
        />
        <Select
          label={vendor ? '활동지역' : '거주지역'}
          value={user.region}
          options={regions.map((r) => r.display_name)}
          onChange={(region) => save({ region })}
        />
        {vendor ? (
          // TODO(integration-gap): GAP-010 업체 소개 수정 API가 없어 표시만 합니다.
          <Field label="업체 소개" value={user.intro ?? ''} editable={false} placeholder="업체 소개는 운영팀이 등록합니다" />
        ) : (
          <Select label="거주형태" value={user.housing} options={HOUSINGS} onChange={(housing) => save({ housing })} />
        )}
        {error && (
          <Txt variant="sub" color={C.danger}>
            {error}
          </Txt>
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
        onPress={async () => {
          await logout();
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
